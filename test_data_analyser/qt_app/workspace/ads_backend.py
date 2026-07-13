"""Qt Advanced Docking System adapter for registered workspace panels."""
from __future__ import annotations

from PySide6.QtCore import QByteArray, QEvent, QObject, QTimer
from PySide6.QtWidgets import QWidget
import PySide6QtAds as QtAds

from .workspace_registry import DockArea, PanelDescriptor, SideBarLocation, WorkspaceRegistry


_ADS_AREAS = {
    DockArea.LEFT: QtAds.LeftDockWidgetArea,
    DockArea.RIGHT: QtAds.RightDockWidgetArea,
    DockArea.TOP: QtAds.TopDockWidgetArea,
    DockArea.BOTTOM: QtAds.BottomDockWidgetArea,
    DockArea.CENTER: QtAds.CenterDockWidgetArea,
}

_ADS_SIDE_BARS = {
    SideBarLocation.LEFT: QtAds.SideBarLeft,
    SideBarLocation.RIGHT: QtAds.SideBarRight,
    SideBarLocation.TOP: QtAds.SideBarTop,
    SideBarLocation.BOTTOM: QtAds.SideBarBottom,
}


class AdsDockBackend:
    """Translate app-owned panel metadata into ADS dock widgets."""

    _configured = False

    def __init__(self, parent: QWidget, registry: WorkspaceRegistry) -> None:
        self._configure_once()
        self.registry = registry
        self.manager = QtAds.CDockManager(parent)
        self._docks: dict[str, QtAds.CDockWidget] = {}
        self.is_shutting_down = False
        self._floating_close_filter = _RequiredPanelCloseFilter(self)
        self.manager.floatingWidgetCreated.connect(self._watch_floating_widget)

    @classmethod
    def _configure_once(cls) -> None:
        if cls._configured:
            return
        QtAds.CDockManager.setConfigFlags(QtAds.CDockManager.DefaultOpaqueConfig)
        QtAds.CDockManager.setAutoHideConfigFlags(QtAds.CDockManager.DefaultAutoHideConfig)
        cls._configured = True

    def add_panel(
        self,
        panel_id: str,
        *,
        area: DockArea | None = None,
        tab_with: str | None = None,
    ) -> QtAds.CDockWidget:
        if panel_id in self._docks:
            raise ValueError(f"Workspace panel is already docked: {panel_id}")
        descriptor = self.registry.descriptor(panel_id)
        dock = self.manager.createDockWidget(descriptor.title)
        dock.setObjectName(descriptor.panel_id)
        dock.setFeatures(self._features(descriptor))
        dock.setWidget(descriptor.widget, QtAds.CDockWidget.ForceNoScrollArea)

        if tab_with is not None:
            target_area = self.dock_widget(tab_with).dockAreaWidget()
            if target_area is None:
                raise ValueError(f"Workspace tab target has no dock area: {tab_with}")
            self.manager.addDockWidgetTabToArea(dock, target_area)
        else:
            self.manager.addDockWidget(_ADS_AREAS[area or descriptor.default_area], dock)
        self._docks[panel_id] = dock
        return dock

    def add_auto_hide_panel(
        self,
        panel_id: str,
        location: SideBarLocation,
    ) -> QtAds.CDockWidget:
        if panel_id in self._docks:
            raise ValueError(f"Workspace panel is already docked: {panel_id}")
        descriptor = self.registry.descriptor(panel_id)
        if not descriptor.pinnable:
            raise ValueError(f"Workspace panel cannot be auto-hidden: {panel_id}")
        dock = self.manager.createDockWidget(descriptor.title)
        dock.setObjectName(descriptor.panel_id)
        dock.setFeatures(self._features(descriptor))
        dock.setWidget(descriptor.widget, QtAds.CDockWidget.ForceNoScrollArea)
        self.manager.addAutoHideDockWidget(_ADS_SIDE_BARS[location], dock)
        self._docks[panel_id] = dock
        return dock

    def dock_widget(self, panel_id: str) -> QtAds.CDockWidget:
        try:
            return self._docks[panel_id]
        except KeyError as exc:
            raise KeyError(f"Workspace panel is not docked: {panel_id}") from exc

    def show_panel(self, panel_id: str) -> None:
        dock = self.dock_widget(panel_id)
        if dock.isClosed():
            dock.toggleViewAction().trigger()
        else:
            dock.toggleView(True)
        dock.setAsCurrentTab()
        dock_area = dock.dockAreaWidget()
        if dock_area is not None:
            dock_area.setCurrentDockWidget(dock)
        self.manager.setDockWidgetFocused(dock)
        dock.raise_()

    def hide_panel(self, panel_id: str) -> None:
        descriptor = self.registry.descriptor(panel_id)
        if descriptor.required:
            raise ValueError(f"Required workspace panel cannot be hidden: {panel_id}")
        self.dock_widget(panel_id).toggleView(False)

    def float_panel(self, panel_id: str) -> None:
        dock = self.dock_widget(panel_id)
        if not self.registry.descriptor(panel_id).floatable:
            raise ValueError(f"Workspace panel cannot float: {panel_id}")
        if not dock.isInFloatingContainer():
            self.manager.addDockWidgetFloating(dock)

    def dock_panel(self, panel_id: str, area: DockArea | None = None) -> None:
        descriptor = self.registry.descriptor(panel_id)
        self.manager.addDockWidget(_ADS_AREAS[area or descriptor.default_area], self.dock_widget(panel_id))

    def set_auto_hide(
        self,
        panel_id: str,
        enabled: bool,
        location: SideBarLocation,
    ) -> None:
        descriptor = self.registry.descriptor(panel_id)
        if not descriptor.pinnable:
            raise ValueError(f"Workspace panel cannot be auto-hidden: {panel_id}")
        self.dock_widget(panel_id).setAutoHide(enabled, _ADS_SIDE_BARS[location])

    def save_state(self, version: int) -> QByteArray:
        return self.manager.saveState(version)

    def restore_state(self, state: QByteArray, version: int) -> bool:
        return bool(self.manager.restoreState(state, version))

    def floating_widgets(self) -> tuple[QWidget, ...]:
        return tuple(self.manager.floatingWidgets())

    def begin_shutdown(self) -> None:
        self.is_shutting_down = True

    def _watch_floating_widget(self, floating: QWidget) -> None:
        floating.installEventFilter(self._floating_close_filter)

    @staticmethod
    def _features(descriptor: PanelDescriptor):
        features = QtAds.CDockWidget.NoDockWidgetFeatures
        if descriptor.closable:
            features |= QtAds.CDockWidget.DockWidgetClosable
        if descriptor.movable:
            features |= QtAds.CDockWidget.DockWidgetMovable
        if descriptor.floatable:
            features |= QtAds.CDockWidget.DockWidgetFloatable
        if descriptor.pinnable:
            features |= QtAds.CDockWidget.DockWidgetPinnable
        return features


class _RequiredPanelCloseFilter(QObject):
    def __init__(self, backend: AdsDockBackend) -> None:
        super().__init__(backend.manager)
        self.backend = backend

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if self.backend.is_shutting_down or event.type() != QEvent.Type.Close:
            return False
        dock_widgets = getattr(watched, "dockWidgets", lambda: [])()
        required_ids = [
            dock.objectName()
            for dock in dock_widgets
            if dock.objectName() in self.backend.registry
            and self.backend.registry.descriptor(dock.objectName()).required
        ]
        if not required_ids:
            return False
        for panel_id in required_ids:
            QTimer.singleShot(0, lambda panel_id=panel_id: self.backend.dock_panel(panel_id))
        event.ignore()
        return True

