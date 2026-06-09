"""Qt file-dialog adapter.

Thin wrappers around ``QFileDialog`` so panels do not construct dialog filter
strings inline. Returns ``None`` when the user cancels.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtWidgets import QFileDialog, QWidget

DATA_FILE_FILTER = "Data files (*.csv *.xlsx *.xls);;CSV (*.csv);;Excel (*.xlsx *.xls);;All files (*.*)"
SESSION_FILTER = "JSON session (*.json);;All files (*.*)"
EXPORT_FILTER = "Excel workbook (*.xlsx);;CSV (*.csv);;All files (*.*)"


def open_data_file(parent: QWidget | None = None) -> Optional[str]:
    filename, _ = QFileDialog.getOpenFileName(parent, "Select test data file", "", DATA_FILE_FILTER)
    return filename or None


def open_session_file(parent: QWidget | None = None) -> Optional[str]:
    filename, _ = QFileDialog.getOpenFileName(parent, "Load analysis session", "", SESSION_FILTER)
    return filename or None


def save_session_file(parent: QWidget | None = None) -> Optional[str]:
    filename, _ = QFileDialog.getSaveFileName(parent, "Save analysis session", "", SESSION_FILTER)
    return filename or None


def save_export_file(parent: QWidget | None = None) -> Optional[str]:
    filename, _ = QFileDialog.getSaveFileName(parent, "Export selected data", "", EXPORT_FILTER)
    return filename or None
