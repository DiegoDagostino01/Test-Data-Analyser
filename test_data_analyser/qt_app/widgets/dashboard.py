"""Compact no-data dashboard using shared application commands."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..command_manager import CommandManager


_PATH_ROLE = int(Qt.ItemDataRole.UserRole) + 1
_COMMAND_ICONS = {
    "session.create": QStyle.StandardPixmap.SP_FileIcon,
    "data.open": QStyle.StandardPixmap.SP_DialogOpenButton,
    "session.open": QStyle.StandardPixmap.SP_DialogOpenButton,
    "recent.open": QStyle.StandardPixmap.SP_DirOpenIcon,
}


class Dashboard(QWidget):
    recentFileRequested = Signal(str)
    recentSessionRequested = Signal(str)
    recoveryRequested = Signal(str)
    recoveryDismissed = Signal(str)

    def __init__(self, command_manager: CommandManager, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.command_manager = command_manager
        self._command_buttons: dict[str, QToolButton] = {}
        self._recovery_path = ""
        self.setObjectName("Dashboard")
        self.setAccessibleName("Start analysis dashboard")

        root = QVBoxLayout(self)
        root.setContentsMargins(36, 28, 36, 28)
        root.setSpacing(18)

        heading = QLabel("Start an analysis")
        heading.setObjectName("DashboardTitle")
        root.addWidget(heading)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        for command_id in ("session.create", "data.open", "session.open", "recent.open"):
            button = self._build_command_button(command_id)
            self._command_buttons[command_id] = button
            actions.addWidget(button)
        actions.addStretch(1)
        root.addLayout(actions)

        recent_grid = QGridLayout()
        recent_grid.setHorizontalSpacing(18)
        recent_grid.setVerticalSpacing(6)
        recent_grid.addWidget(self._section_label("Recent data files"), 0, 0)
        recent_grid.addWidget(self._section_label("Recent sessions"), 0, 1)
        self.recent_files = self._recent_list("DashboardRecentFiles")
        self.recent_sessions = self._recent_list("DashboardRecentSessions")
        self.recent_files.setAccessibleName("Recent data files")
        self.recent_sessions.setAccessibleName("Recent sessions")
        self.recent_files.itemActivated.connect(self._request_recent_file)
        self.recent_sessions.itemActivated.connect(self._request_recent_session)
        recent_grid.addWidget(self.recent_files, 1, 0)
        recent_grid.addWidget(self.recent_sessions, 1, 1)
        recent_grid.setColumnStretch(0, 1)
        recent_grid.setColumnStretch(1, 1)
        root.addLayout(recent_grid, 1)

        self.recovery_banner = QFrame()
        self.recovery_banner.setObjectName("DashboardRecoveryBanner")
        self.recovery_banner.setAccessibleName("Recovery auto-save available")
        recovery_layout = QHBoxLayout(self.recovery_banner)
        recovery_layout.setContentsMargins(14, 10, 14, 10)
        self.recovery_label = QLabel()
        self.recovery_label.setObjectName("DashboardRecoveryLabel")
        self.recovery_label.setWordWrap(True)
        recovery_layout.addWidget(self.recovery_label, 1)
        self.recover_button = QPushButton("Recover Auto-save")
        self.recover_button.setObjectName("DashboardRecoverButton")
        self.recover_button.setAccessibleName("Recover auto-save")
        self.recover_button.clicked.connect(self._request_recovery)
        self.dismiss_recovery_button = QPushButton("Dismiss")
        self.dismiss_recovery_button.setObjectName("DashboardDismissRecoveryButton")
        self.dismiss_recovery_button.setAccessibleName("Dismiss recovery")
        self.dismiss_recovery_button.clicked.connect(self._dismiss_recovery)
        recovery_layout.addWidget(self.recover_button)
        recovery_layout.addWidget(self.dismiss_recovery_button)
        self.recovery_banner.hide()
        root.addWidget(self.recovery_banner)

        shortcuts = QLabel(
            "Ctrl+N  Create Session     Ctrl+O  Open Excel     Ctrl+L  Load Session     Ctrl+Shift+P  Commands"
        )
        shortcuts.setObjectName("DashboardShortcuts")
        shortcuts.setWordWrap(True)
        root.addWidget(shortcuts)

        focus_order = [
            *(self._command_buttons[command_id] for command_id in (
                "session.create", "data.open", "session.open", "recent.open"
            )),
            self.recent_files,
            self.recent_sessions,
            self.recover_button,
            self.dismiss_recovery_button,
        ]
        for current, following in zip(focus_order, focus_order[1:]):
            QWidget.setTabOrder(current, following)
        self.setFocusProxy(self._command_buttons["session.create"])

    def command_button(self, command_id: str) -> QToolButton:
        return self._command_buttons[command_id]

    def set_recent_items(self, recent_files: list[str], recent_sessions: list[str]) -> None:
        self._populate_recent_list(self.recent_files, recent_files)
        self._populate_recent_list(self.recent_sessions, recent_sessions)

    def set_recovery(self, path: str, modified_text: str = "") -> None:
        self._recovery_path = path
        if not path:
            self.recovery_banner.hide()
            self.recovery_label.clear()
            return
        suffix = f" - saved {modified_text}" if modified_text else ""
        self.recovery_label.setText(f"Recovery available in {Path(path).parent}{suffix}")
        self.recovery_label.setToolTip(path)
        self.recovery_banner.show()

    def _build_command_button(self, command_id: str) -> QToolButton:
        action = self.command_manager.action(command_id)
        button = QToolButton()
        button.setObjectName("DashboardCommandButton")
        button.setDefaultAction(action)
        button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        button.setMinimumHeight(38)
        button.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        standard_icon = _COMMAND_ICONS.get(command_id)
        if action.icon().isNull() and standard_icon is not None:
            button.setIcon(self.style().standardIcon(standard_icon))
        return button

    @staticmethod
    def _section_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("DashboardSectionTitle")
        return label

    @staticmethod
    def _recent_list(object_name: str) -> QListWidget:
        widget = QListWidget()
        widget.setObjectName(object_name)
        widget.setAlternatingRowColors(True)
        widget.setUniformItemSizes(True)
        widget.setMinimumHeight(150)
        return widget

    @staticmethod
    def _populate_recent_list(widget: QListWidget, paths: list[str]) -> None:
        widget.clear()
        if not paths:
            empty = QListWidgetItem("No recent items")
            empty.setFlags(Qt.ItemFlag.NoItemFlags)
            widget.addItem(empty)
            return
        for path in paths:
            exists = Path(path).exists()
            label = Path(path).name or path
            item = QListWidgetItem(label if exists else f"{label} (missing)")
            item.setData(_PATH_ROLE, path)
            item.setToolTip(path)
            if not exists:
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEnabled)
            widget.addItem(item)

    def _request_recent_file(self, item: QListWidgetItem) -> None:
        path = str(item.data(_PATH_ROLE) or "")
        if path:
            self.recentFileRequested.emit(path)

    def _request_recent_session(self, item: QListWidgetItem) -> None:
        path = str(item.data(_PATH_ROLE) or "")
        if path:
            self.recentSessionRequested.emit(path)

    def _request_recovery(self) -> None:
        if self._recovery_path:
            self.recoveryRequested.emit(self._recovery_path)

    def _dismiss_recovery(self) -> None:
        if self._recovery_path:
            self.recoveryDismissed.emit(self._recovery_path)