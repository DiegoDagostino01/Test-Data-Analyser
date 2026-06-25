"""Batch Run Import dialog.

Collects a folder, file glob patterns, an optional run-name regex, an optional
sheet name, and a recursive flag. Pure UI: the panel reads :meth:`settings` and
hands them to :meth:`RunsComparisonViewModel.add_runs_from_folder`.
"""
from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ..adapters import qt_file_dialogs


class BatchImportDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, *, initial_dir: str = "") -> None:
        super().__init__(parent)
        self.setObjectName("BatchImportDialog")
        self.setWindowTitle("Batch Import Runs")

        top = parent.window() if parent is not None else None
        if top is not None and top.styleSheet():
            self.setStyleSheet(top.styleSheet())

        layout = QVBoxLayout(self)
        form = QGridLayout()

        form.addWidget(QLabel("Folder:"), 0, 0)
        folder_row = QHBoxLayout()
        self.folder_edit = QLineEdit(initial_dir)
        folder_row.addWidget(self.folder_edit, stretch=1)
        browse = QPushButton("Browse\u2026")
        browse.clicked.connect(self._browse)
        folder_row.addWidget(browse)
        form.addLayout(folder_row, 0, 1)

        form.addWidget(QLabel("File patterns:"), 1, 0)
        self.glob_edit = QLineEdit("*.csv;*.xlsx")
        self.glob_edit.setToolTip("Semicolon-separated glob patterns, e.g. *.csv;*.xlsx")
        form.addWidget(self.glob_edit, 1, 1)

        form.addWidget(QLabel("Name regex (optional):"), 2, 0)
        self.regex_edit = QLineEdit()
        self.regex_edit.setPlaceholderText(r"e.g. SN(\d+)")
        form.addWidget(self.regex_edit, 2, 1)

        form.addWidget(QLabel("Sheet (optional):"), 3, 0)
        self.sheet_edit = QLineEdit()
        self.sheet_edit.setPlaceholderText("First sheet")
        form.addWidget(self.sheet_edit, 3, 1)

        layout.addLayout(form)

        self.recursive_check = QCheckBox("Search subfolders")
        layout.addWidget(self.recursive_check)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _browse(self) -> None:
        folder = qt_file_dialogs.select_folder(self, self.folder_edit.text())
        if folder:
            self.folder_edit.setText(folder)

    def settings(self) -> dict:
        return {
            "folder": self.folder_edit.text().strip(),
            "glob": self.glob_edit.text().strip() or "*.csv;*.xlsx",
            "recursive": self.recursive_check.isChecked(),
            "name_regex": self.regex_edit.text().strip() or None,
            "sheet_name": self.sheet_edit.text().strip() or None,
        }
