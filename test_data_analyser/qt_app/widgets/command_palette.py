"""Keyboard-first command search dialog."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..command_manager import CommandDefinition, CommandManager


_COMMAND_ID_ROLE = int(Qt.ItemDataRole.UserRole) + 1


class CommandPalette(QDialog):
    """Search and execute registered commands without duplicating handlers."""

    def __init__(
        self,
        command_manager: CommandManager,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.command_manager = command_manager
        self._return_focus: QWidget | None = None
        self.setWindowTitle("Command Palette")
        self.setModal(False)
        self.resize(620, 420)

        layout = QVBoxLayout(self)
        self.search_edit = QLineEdit()
        self.search_edit.setObjectName("CommandPaletteSearch")
        self.search_edit.setPlaceholderText("Type a command or panel name")
        self.search_edit.setClearButtonEnabled(True)
        self.search_edit.textChanged.connect(self.refresh)
        layout.addWidget(self.search_edit)

        self.results = QListWidget()
        self.results.setObjectName("CommandPaletteResults")
        self.results.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.results.itemActivated.connect(self._activate_item)
        layout.addWidget(self.results, 1)

        self.reason_label = QLabel("")
        self.reason_label.setObjectName("CommandDisabledReason")
        self.reason_label.setWordWrap(True)
        layout.addWidget(self.reason_label)
        self.results.currentItemChanged.connect(self._show_disabled_reason)
        self.refresh()

    def open_palette(self) -> None:
        focused = self.window().focusWidget() if self.window() is not None else None
        self._return_focus = focused if focused is not self else None
        self.command_manager.refresh_availability()
        self.search_edit.clear()
        self.refresh()
        self.show()
        self.raise_()
        self.activateWindow()
        self.search_edit.setFocus()

    def refresh(self, *_args) -> None:
        current_id = self.current_command_id()
        self.results.clear()
        for definition in self.command_manager.search(self.search_edit.text()):
            self.results.addItem(self._item(definition))
        if self.results.count():
            row = 0
            if current_id:
                for index in range(self.results.count()):
                    if self.results.item(index).data(_COMMAND_ID_ROLE) == current_id:
                        row = index
                        break
            self.results.setCurrentRow(row)

    def current_command_id(self) -> str:
        item = self.results.currentItem()
        return str(item.data(_COMMAND_ID_ROLE)) if item is not None else ""

    def execute_current(self) -> bool:
        item = self.results.currentItem()
        if item is None:
            return False
        command_id = str(item.data(_COMMAND_ID_ROLE))
        action = self.command_manager.action(command_id)
        if not action.isEnabled():
            self._show_disabled_reason(item)
            return False
        action.trigger()
        self.close()
        return True

    def closeEvent(self, event) -> None:
        super().closeEvent(event)
        if self._return_focus is not None:
            self._return_focus.setFocus()
        self._return_focus = None

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in {Qt.Key.Key_Down, Qt.Key.Key_Up}:
            delta = 1 if event.key() == Qt.Key.Key_Down else -1
            count = self.results.count()
            if count:
                self.results.setCurrentRow((self.results.currentRow() + delta) % count)
            event.accept()
            return
        if event.key() in {Qt.Key.Key_Return, Qt.Key.Key_Enter}:
            self.execute_current()
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self.close()
            event.accept()
            return
        super().keyPressEvent(event)

    def _item(self, definition: CommandDefinition) -> QListWidgetItem:
        text = definition.title
        if definition.action.shortcut().toString():
            text = f"{text}    {definition.action.shortcut().toString()}"
        item = QListWidgetItem(text)
        item.setData(_COMMAND_ID_ROLE, definition.command_id)
        item.setToolTip(definition.tooltip)
        if not definition.action.isEnabled():
            item.setForeground(self.palette().color(self.foregroundRole()).darker(150))
        return item

    def _activate_item(self, _item: QListWidgetItem) -> None:
        self.execute_current()

    def _show_disabled_reason(
        self,
        item: QListWidgetItem | None,
        _previous: QListWidgetItem | None = None,
    ) -> None:
        if item is None:
            self.reason_label.clear()
            return
        command_id = str(item.data(_COMMAND_ID_ROLE))
        self.reason_label.setText(self.command_manager.disabled_reason(command_id))
