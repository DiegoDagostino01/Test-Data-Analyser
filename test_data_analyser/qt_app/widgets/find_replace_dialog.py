"""Non-modal Find / Find & Replace dialog for the Raw Data table.

A thin Qt view over :class:`RawDataViewModel` ``find`` / ``replace_all`` /
``replace_match``; all search and replacement logic stays framework-independent
in the viewmodel and ``find_replace_service``. The dialog only collects options,
drives navigation, and reports results on its own status line.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)


class FindReplaceDialog(QDialog):
    def __init__(self, panel, *, replace_enabled: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.panel = panel
        self.vm = panel.vm
        self._matches: list = []
        self._match_index = -1

        self.setObjectName("FindReplaceDialog")
        self.setModal(False)
        self.setWindowTitle("Find and Replace" if replace_enabled else "Find")

        top = parent.window() if parent is not None else None
        if top is not None and top.styleSheet():
            self.setStyleSheet(top.styleSheet())

        layout = QVBoxLayout(self)

        form = QGridLayout()
        form.addWidget(QLabel("Find:"), 0, 0)
        self.query_edit = QLineEdit()
        self.query_edit.textChanged.connect(self._reset_matches)
        form.addWidget(self.query_edit, 0, 1)
        form.addWidget(QLabel("Replace:"), 1, 0)
        self.replacement_edit = QLineEdit()
        form.addWidget(self.replacement_edit, 1, 1)
        layout.addLayout(form)

        options = QHBoxLayout()
        self.regex_check = QCheckBox("Regex")
        self.case_check = QCheckBox("Match case")
        self.full_dataset_check = QCheckBox("Search full dataset")
        self.full_dataset_check.setChecked(True)
        for box in (self.regex_check, self.case_check, self.full_dataset_check):
            box.toggled.connect(self._reset_matches)
            options.addWidget(box)
        options.addStretch(1)
        layout.addLayout(options)

        buttons = QHBoxLayout()
        self.find_button = QPushButton("Find Next")
        self.find_button.clicked.connect(self._on_find_next)
        self.replace_button = QPushButton("Replace")
        self.replace_button.clicked.connect(self._on_replace)
        self.replace_all_button = QPushButton("Replace All")
        self.replace_all_button.clicked.connect(self._on_replace_all)
        self.close_button = QPushButton("Close")
        self.close_button.clicked.connect(self.close)
        for button in (self.find_button, self.replace_button, self.replace_all_button):
            buttons.addWidget(button)
        buttons.addStretch(1)
        buttons.addWidget(self.close_button)
        layout.addLayout(buttons)

        self.status_label = QLabel("")
        self.status_label.setObjectName("PlaceholderText")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.set_replace_enabled(replace_enabled)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def set_replace_enabled(self, enabled: bool) -> None:
        self._replace_enabled = enabled
        self.replacement_edit.setEnabled(enabled)
        self.replace_button.setEnabled(enabled)
        self.replace_all_button.setEnabled(enabled)

    def focus_query(self) -> None:
        self.query_edit.setFocus()
        self.query_edit.selectAll()

    def closeEvent(self, event) -> None:
        self._reset_matches()
        super().closeEvent(event)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _search_kwargs(self) -> dict:
        return dict(
            columns=None,
            regex=self.regex_check.isChecked(),
            case_sensitive=self.case_check.isChecked(),
            search_full_dataset=self.full_dataset_check.isChecked(),
            display_frame=self.panel.current_display_frame(),
        )

    def _reset_matches(self, *_args) -> None:
        self._matches = []
        self._match_index = -1

    def _ensure_matches(self) -> bool:
        if self._matches:
            return True
        query = self.query_edit.text()
        if not query:
            self.status_label.setText("Enter text to find.")
            return False
        result = self.vm.find(query, **self._search_kwargs())
        if not result.ok:
            self.status_label.setText(result.message)
            return False
        self._matches = result.payload or []
        self._match_index = -1
        if not self._matches:
            self.status_label.setText("No matches found.")
            return False
        return True

    def _on_find_next(self) -> None:
        if not self._ensure_matches():
            return
        self._match_index = (self._match_index + 1) % len(self._matches)
        match = self._matches[self._match_index]
        self.panel.focus_source_cell(match.row, match.column)
        self.status_label.setText(f"Match {self._match_index + 1} of {len(self._matches)}.")

    def _on_replace(self) -> None:
        if not self._replace_enabled:
            return
        if not (0 <= self._match_index < len(self._matches)):
            self._on_find_next()
            return
        match = self._matches[self._match_index]
        result = self.vm.replace_match(
            match.row,
            match.column,
            self.query_edit.text(),
            self.replacement_edit.text(),
            regex=self.regex_check.isChecked(),
            case_sensitive=self.case_check.isChecked(),
        )
        self.panel.after_find_replace()
        self.status_label.setText(result.message)
        self._reset_matches()
        self._on_find_next()

    def _on_replace_all(self) -> None:
        if not self._replace_enabled:
            return
        query = self.query_edit.text()
        if not query:
            self.status_label.setText("Enter text to find.")
            return
        result = self.vm.replace_all(query, self.replacement_edit.text(), **self._search_kwargs())
        self.panel.after_find_replace()
        self.status_label.setText(result.message)
        self._reset_matches()
