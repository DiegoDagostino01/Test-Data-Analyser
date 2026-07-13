"""Registry and metadata for singleton Qt workspace panels."""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import re

from PySide6.QtWidgets import QWidget


class DockArea(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"
    CENTER = "center"


class SideBarLocation(str, Enum):
    LEFT = "left"
    RIGHT = "right"
    TOP = "top"
    BOTTOM = "bottom"


_PANEL_ID_PATTERN = re.compile(r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*$")


@dataclass(frozen=True)
class PanelDescriptor:
    panel_id: str
    title: str
    widget: QWidget
    default_area: DockArea
    allowed_areas: frozenset[DockArea] = field(default_factory=lambda: frozenset(DockArea))
    closable: bool = True
    movable: bool = True
    floatable: bool = True
    pinnable: bool = True
    serializable: bool = True
    required: bool = False

    def __post_init__(self) -> None:
        panel_id = self.panel_id.strip()
        title = self.title.strip()
        if not _PANEL_ID_PATTERN.fullmatch(panel_id):
            raise ValueError(f"Invalid workspace panel ID: {self.panel_id!r}")
        if not title:
            raise ValueError("Workspace panel title cannot be empty.")
        if self.default_area not in self.allowed_areas:
            raise ValueError(
                f"Default area {self.default_area.value!r} is not allowed for {panel_id!r}."
            )
        if self.required and self.closable:
            raise ValueError(f"Required workspace panel {panel_id!r} cannot be closable.")
        object.__setattr__(self, "panel_id", panel_id)
        object.__setattr__(self, "title", title)


class WorkspaceRegistry:
    """Own stable metadata for each singleton panel widget."""

    def __init__(self) -> None:
        self._descriptors: dict[str, PanelDescriptor] = {}
        self._widget_ids: set[int] = set()

    def register(self, descriptor: PanelDescriptor) -> None:
        if descriptor.panel_id in self._descriptors:
            raise ValueError(f"Duplicate workspace panel ID: {descriptor.panel_id}")
        widget_id = id(descriptor.widget)
        if widget_id in self._widget_ids:
            raise ValueError(
                f"Workspace widget is already registered: {descriptor.widget.objectName() or descriptor.title}"
            )
        self._descriptors[descriptor.panel_id] = descriptor
        self._widget_ids.add(widget_id)

    def descriptor(self, panel_id: str) -> PanelDescriptor:
        try:
            return self._descriptors[panel_id]
        except KeyError as exc:
            raise KeyError(f"Unknown workspace panel: {panel_id}") from exc

    def widget(self, panel_id: str) -> QWidget:
        return self.descriptor(panel_id).widget

    def descriptors(self) -> tuple[PanelDescriptor, ...]:
        return tuple(self._descriptors.values())

    def panel_ids(self) -> tuple[str, ...]:
        return tuple(self._descriptors)

    def __contains__(self, panel_id: object) -> bool:
        return panel_id in self._descriptors

    def __len__(self) -> int:
        return len(self._descriptors)
