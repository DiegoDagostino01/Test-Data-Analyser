"""Render registered application commands into the V1.03 ribbon."""
from __future__ import annotations

from collections.abc import Callable, Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMenu,
    QPushButton,
    QSizePolicy,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from .command_manager import CommandManager


RibbonLayout = Sequence[tuple[str, Sequence[str]]]


_STANDARD_ICONS = {
    "data.open": QStyle.StandardPixmap.SP_DialogOpenButton,
    "session.open": QStyle.StandardPixmap.SP_DialogOpenButton,
    "session.save": QStyle.StandardPixmap.SP_DialogSaveButton,
    "session.create": QStyle.StandardPixmap.SP_FileIcon,
    "recent.open": QStyle.StandardPixmap.SP_DirOpenIcon,
    "plot.generate": QStyle.StandardPixmap.SP_BrowserReload,
    "plot.saveImage": QStyle.StandardPixmap.SP_DialogSaveButton,
    "plot.clear": QStyle.StandardPixmap.SP_DialogDiscardButton,
    "requirements.refresh": QStyle.StandardPixmap.SP_BrowserReload,
    "app.settings": QStyle.StandardPixmap.SP_FileDialogDetailedView,
    "app.help": QStyle.StandardPixmap.SP_DialogHelpButton,
}


class RibbonManager:
    """Build ribbon groups from the same QActions used by menus and palette."""

    def __init__(
        self,
        parent: QWidget,
        command_manager: CommandManager,
        layout: RibbonLayout,
        *,
        menu_populators: dict[str, Callable[[QMenu], None]] | None = None,
    ) -> None:
        self.parent = parent
        self.command_manager = command_manager
        self.layout = layout
        self.menu_populators = menu_populators or {}
        self.buttons: dict[str, QPushButton] = {}
        self._buttons_by_command: dict[str, QPushButton] = {}
        self._group_frames: dict[str, QFrame] = {}
        self._command_groups: dict[str, str] = {}

    def build(self) -> QFrame:
        ribbon = QFrame()
        ribbon.setObjectName("RibbonBar")
        ribbon.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(ribbon)
        layout.setContentsMargins(12, 5, 12, 5)
        layout.setSpacing(8)
        for group, command_ids in self.layout:
            layout.addWidget(self._group(group, command_ids))
        layout.addStretch(1)
        return ribbon

    def button_for(self, command_id: str) -> QPushButton:
        return self._buttons_by_command[command_id]

    def _group(self, title: str, command_ids: Sequence[str]) -> QFrame:
        group = QFrame()
        group.setObjectName("RibbonGroup")
        self._group_frames[title] = group
        outer = QVBoxLayout(group)
        outer.setContentsMargins(6, 3, 6, 4)
        outer.setSpacing(3)
        label = QLabel(title)
        label.setObjectName("RibbonGroupLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(label)

        grid = QGridLayout()
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(4)
        grid.setVerticalSpacing(3)
        column_count = 3 if len(command_ids) > 4 else 2
        for index, command_id in enumerate(command_ids):
            self._command_groups[command_id] = title
            button = self._button(command_id)
            grid.addWidget(button, index // column_count, index % column_count)
            definition = self.command_manager.definition(command_id)
            self.buttons[f"{title.upper()}:{definition.title}"] = button
            self._buttons_by_command[command_id] = button
        outer.addLayout(grid)
        self._sync_group_visibility(title)
        return group

    def _button(self, command_id: str) -> QPushButton:
        definition = self.command_manager.definition(command_id)
        action = definition.action
        button = QPushButton(definition.title)
        button.setObjectName("RibbonButton")
        button.setFixedHeight(27)
        button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        button.setToolTip(definition.tooltip)
        standard_icon = _STANDARD_ICONS.get(command_id)
        if not action.icon().isNull():
            button.setIcon(action.icon())
        elif standard_icon is not None:
            button.setIcon(self.parent.style().standardIcon(standard_icon))
        if command_id == "plot.generate":
            button.setProperty("ribbonPrimary", "true")
        populator = self.menu_populators.get(command_id)
        if populator is not None:
            menu = QMenu(button)
            menu.aboutToShow.connect(
                lambda menu=menu, populator=populator: self._populate_menu(
                    menu, populator
                )
            )
            button.setMenu(menu)
        else:
            button.clicked.connect(action.trigger)
        action.changed.connect(
            lambda action=action, button=button, command_id=command_id: self._sync_command_button(
                command_id, action, button
            )
        )
        self._sync_button(action, button)
        return button

    @staticmethod
    def _sync_button(action, button: QPushButton) -> None:
        button.setVisible(action.isVisible())
        button.setEnabled(action.isEnabled())
        if action.isCheckable():
            button.setCheckable(True)
            button.setChecked(action.isChecked())

    def _sync_command_button(self, command_id: str, action, button: QPushButton) -> None:
        self._sync_button(action, button)
        group_title = self._command_groups.get(command_id)
        if group_title is not None:
            self._sync_group_visibility(group_title)

    def _sync_group_visibility(self, title: str) -> None:
        frame = self._group_frames[title]
        command_ids = (
            command_id
            for command_id, group_title in self._command_groups.items()
            if group_title == title
        )
        frame.setVisible(
            any(not self._buttons_by_command[command_id].isHidden() for command_id in command_ids)
        )

    @staticmethod
    def _populate_menu(menu: QMenu, populator: Callable[[QMenu], None]) -> None:
        menu.clear()
        populator(menu)
