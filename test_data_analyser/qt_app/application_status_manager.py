"""Central transient and durable application status presentation."""
from __future__ import annotations

from enum import Enum

from PySide6.QtGui import QAccessible, QAccessibleAnnouncementEvent
from PySide6.QtWidgets import QLabel, QStatusBar


class PlotStatus(str, Enum):
    NO_PLOT = "No plot"
    CURRENT = "Up to date"
    STALE = "Needs regeneration"
    ERROR = "Error"


class SessionStatus(str, Enum):
    SAVED = "Saved"
    UNSAVED = "Unsaved"


class ApplicationStatusManager:
    """Own operation messages and persistent status-bar indicators."""

    def __init__(self, status_bar: QStatusBar) -> None:
        self.status_bar = status_bar
        self._last_announcement_event: QAccessibleAnnouncementEvent | None = None
        self.operation_label = self._label("OperationStatus", "Ready")
        self.plot_label = self._label("PlotStatus", "Plot: No plot")
        self.session_label = self._label("SessionStatus", "Session: Saved")
        self.autosave_label = self._label("AutosaveStatus", "")
        self.workspace_label = self._label("WorkspaceStatus", "Analysis")
        status_bar.addWidget(self.operation_label, 1)
        for label in (
            self.plot_label,
            self.session_label,
            self.autosave_label,
            self.workspace_label,
        ):
            status_bar.addPermanentWidget(label)

    @staticmethod
    def _label(object_name: str, text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName(object_name)
        label.setAccessibleName(text)
        label.setMinimumWidth(0)
        return label

    def show_message(self, message: object, timeout_ms: int = 0) -> None:
        text = str(message or "").strip()
        self._set_label_text(self.operation_label, text)
        self.status_bar.showMessage(text, timeout_ms)
        if text:
            event = QAccessibleAnnouncementEvent(self.status_bar, text)
            event.setPoliteness(QAccessible.AnnouncementPoliteness.Polite)
            self._last_announcement_event = event
            QAccessible.updateAccessibility(event)

    def set_plot_status(self, status: PlotStatus, detail: str = "") -> None:
        suffix = f" - {detail}" if detail else ""
        self._set_label_text(self.plot_label, f"Plot: {status.value}{suffix}")
        self.plot_label.setProperty("state", status.name.casefold())
        self.plot_label.style().unpolish(self.plot_label)
        self.plot_label.style().polish(self.plot_label)

    def set_session_dirty(self, dirty: bool) -> None:
        status = SessionStatus.UNSAVED if dirty else SessionStatus.SAVED
        self._set_label_text(self.session_label, f"Session: {status.value}")
        self.session_label.setProperty("state", status.name.casefold())
        self.session_label.style().unpolish(self.session_label)
        self.session_label.style().polish(self.session_label)

    def set_autosave(self, text: str = "", *, failed: bool = False) -> None:
        self._set_label_text(self.autosave_label, text)
        self.autosave_label.setProperty("state", "error" if failed else "saved")

    def set_workspace(self, text: str) -> None:
        visible_text = str(text)
        self.workspace_label.setText(visible_text)
        self.workspace_label.setAccessibleName(f"Workspace: {visible_text}")

    @staticmethod
    def _set_label_text(label: QLabel, text: str) -> None:
        label.setText(text)
        label.setAccessibleName(text)
