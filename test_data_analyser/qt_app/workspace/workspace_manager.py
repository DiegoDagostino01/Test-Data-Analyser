"""Workspace orchestration for registered Qt panels."""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QRect, QTimer
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QMainWindow, QWidget

from ...core.settings_manager import SettingsManager
from .ads_backend import AdsDockBackend
from .workspace_presets import (
    BUILT_IN_PRESETS,
    PLOT_PANEL_ID,
    WorkspacePreset,
    parse_workspace_preset,
)
from .workspace_registry import DockArea, SideBarLocation, WorkspaceRegistry
from .workspace_serializer import WORKSPACE_LAYOUT_VERSION, WorkspaceSerializer


class WorkspaceManager:
    """The only application component that coordinates workspace behavior."""

    def __init__(
        self,
        window: QMainWindow,
        registry: WorkspaceRegistry,
        settings_manager: SettingsManager,
    ) -> None:
        self.window = window
        self.registry = registry
        self.settings_manager = settings_manager
        self.backend = AdsDockBackend(window, registry)
        self.serializer = WorkspaceSerializer()
        self.active_preset = WorkspacePreset.ANALYSIS
        self._custom_layout: QByteArray | None = None
        self._built = False
        self._preset_generation = 0
        self._visibility_mask: frozenset[str] = frozenset()
        self._unmasked_layout: QByteArray | None = None
        application = QGuiApplication.instance()
        if isinstance(application, QGuiApplication):
            application.screenRemoved.connect(
                lambda _screen: QTimer.singleShot(0, self.recover_floating_windows)
            )

    @property
    def widget(self) -> QWidget:
        return self.backend.manager

    def build(self) -> None:
        if self._built:
            raise RuntimeError("Workspace has already been built.")
        previous_by_area: dict[DockArea, str] = {}
        for descriptor in self.registry.descriptors():
            tab_with = previous_by_area.get(descriptor.default_area)
            self.backend.add_panel(descriptor.panel_id, tab_with=tab_with)
            previous_by_area.setdefault(descriptor.default_area, descriptor.panel_id)
        self._built = True
        if not self.restore():
            self.apply_preset(WorkspacePreset.ANALYSIS)

    def apply_preset(self, preset: WorkspacePreset | str) -> None:
        if self._visibility_mask:
            raise RuntimeError("Workspace presets are unavailable while a visibility mask is active.")
        resolved = parse_workspace_preset(preset)
        self._preset_generation += 1
        generation = self._preset_generation
        if resolved is WorkspacePreset.CUSTOM:
            if self._custom_layout is None:
                raise ValueError("No Custom workspace layout has been saved.")
            if not self.backend.restore_state(self._custom_layout, WORKSPACE_LAYOUT_VERSION):
                raise ValueError("The Custom workspace layout could not be restored.")
            self.active_preset = resolved
            return
        definition = BUILT_IN_PRESETS[resolved]
        for descriptor in self.registry.descriptors():
            if not descriptor.required and descriptor.panel_id not in definition.visible_panels:
                self.backend.hide_panel(descriptor.panel_id)
        visible_ids = tuple(
            descriptor.panel_id
            for descriptor in self.registry.descriptors()
            if descriptor.required or descriptor.panel_id in definition.visible_panels
        )
        QTimer.singleShot(
            0,
            lambda: self._complete_preset(generation, visible_ids),
        )
        self.active_preset = resolved

    def _complete_preset(self, generation: int, visible_ids: tuple[str, ...]) -> None:
        if generation != self._preset_generation:
            return
        for panel_id in visible_ids:
            self.backend.show_panel(panel_id)

    def show_panel(self, panel_id: str) -> None:
        if panel_id in self._visibility_mask:
            return
        self.backend.show_panel(panel_id)

    def hide_panel(self, panel_id: str) -> None:
        self.backend.hide_panel(panel_id)

    def float_panel(self, panel_id: str) -> None:
        if panel_id in self._visibility_mask:
            return
        self.backend.float_panel(panel_id)

    def dock_panel(self, panel_id: str) -> None:
        if panel_id in self._visibility_mask:
            return
        self.backend.dock_panel(panel_id)

    def set_auto_hide(
        self,
        panel_id: str,
        enabled: bool,
        location: SideBarLocation,
    ) -> None:
        if panel_id in self._visibility_mask:
            return
        self.backend.set_auto_hide(panel_id, enabled, location)

    def save_custom_layout(self) -> None:
        if self._visibility_mask:
            raise RuntimeError("Custom layouts cannot be overwritten while a visibility mask is active.")
        self._custom_layout = self.backend.save_state(WORKSPACE_LAYOUT_VERSION)
        self.active_preset = WorkspacePreset.CUSTOM
        self.save()

    @property
    def visibility_mask(self) -> frozenset[str]:
        return self._visibility_mask

    def set_visibility_mask(self, panel_ids: set[str] | frozenset[str]) -> None:
        """Hide panels temporarily without changing their persisted arrangement."""
        requested = frozenset(panel_ids)
        unknown = requested.difference(
            descriptor.panel_id for descriptor in self.registry.descriptors()
        )
        if unknown:
            raise KeyError(f"Unknown workspace panels in visibility mask: {sorted(unknown)!r}")
        required = {
            panel_id
            for panel_id in requested
            if self.registry.descriptor(panel_id).required
        }
        if required:
            raise ValueError(f"Required workspace panels cannot be masked: {sorted(required)!r}")
        if requested == self._visibility_mask:
            return

        if self._visibility_mask and self._unmasked_layout is not None:
            self.backend.restore_state(self._unmasked_layout, WORKSPACE_LAYOUT_VERSION)
        self._visibility_mask = frozenset()
        self._unmasked_layout = None

        if not requested:
            return
        self._unmasked_layout = self.backend.save_state(WORKSPACE_LAYOUT_VERSION)
        self._visibility_mask = requested
        for panel_id in requested:
            self.backend.hide_panel(panel_id)

    def save(self) -> None:
        if self.settings_manager.is_read_only:
            return
        dock_state = self._unmasked_layout or self.backend.save_state(WORKSPACE_LAYOUT_VERSION)
        payload = self.serializer.serialize(
            dock_state=dock_state,
            main_geometry=self.window.saveGeometry(),
            active_preset=self.active_preset,
            custom_layout=self._custom_layout,
        )
        self.settings_manager.set("workspace", "payload", payload)
        self.settings_manager.save()

    def restore(self) -> bool:
        try:
            payload = self.settings_manager.get("workspace", "payload")
        except KeyError:
            return False
        restored = self.serializer.restore(payload)
        if restored is None:
            return False
        if not self.backend.restore_state(restored.dock_state, WORKSPACE_LAYOUT_VERSION):
            return False
        if not restored.main_geometry.isEmpty():
            self.window.restoreGeometry(restored.main_geometry)
        self.active_preset = restored.active_preset
        self._custom_layout = restored.custom_layout
        QTimer.singleShot(0, self.recover_floating_windows)
        return True

    def recover_floating_windows(self) -> None:
        application = QGuiApplication.instance()
        if not isinstance(application, QGuiApplication):
            return
        available = [screen.availableGeometry() for screen in application.screens()]
        primary = application.primaryScreen()
        if not available or primary is None:
            return
        primary_geometry = primary.availableGeometry()
        for floating in self.backend.floating_widgets():
            current = floating.frameGeometry()
            if any(screen.intersects(current) for screen in available):
                continue
            recovered = self.recover_geometry(current, primary_geometry)
            floating.setGeometry(recovered)

    def begin_shutdown(self) -> None:
        self.backend.begin_shutdown()

    @staticmethod
    def recover_geometry(rect: QRect, available: QRect) -> QRect:
        width = max(240, min(rect.width(), available.width()))
        height = max(160, min(rect.height(), available.height()))
        left = min(max(rect.left(), available.left()), available.right() - width + 1)
        top = min(max(rect.top(), available.top()), available.bottom() - height + 1)
        return QRect(left, top, width, height)
