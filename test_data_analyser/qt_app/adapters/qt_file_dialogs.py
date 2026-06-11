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
IMAGE_FILTER = "PNG image (*.png);;SVG image (*.svg);;PDF document (*.pdf);;All files (*.*)"


def open_data_file(parent: QWidget | None = None, initial_dir: str = "") -> Optional[str]:
    filename, _ = QFileDialog.getOpenFileName(
        parent, "Select test data file", initial_dir or "", DATA_FILE_FILTER
    )
    return filename or None


def locate_data_file(
    parent: QWidget | None = None,
    initial_dir: str = "",
    expected_filename: str = "",
) -> Optional[str]:
    caption = "Locate moved data file"
    if expected_filename:
        caption = f"Locate moved data file: {expected_filename}"
    filename, _ = QFileDialog.getOpenFileName(parent, caption, initial_dir or "", DATA_FILE_FILTER)
    return filename or None


def open_session_file(parent: QWidget | None = None, initial_dir: str = "") -> Optional[str]:
    filename, _ = QFileDialog.getOpenFileName(
        parent, "Load analysis session", initial_dir or "", SESSION_FILTER
    )
    return filename or None


def save_session_file(parent: QWidget | None = None, initial_dir: str = "") -> Optional[str]:
    filename, _ = QFileDialog.getSaveFileName(
        parent, "Save analysis session", initial_dir or "", SESSION_FILTER
    )
    return filename or None


def save_export_file(parent: QWidget | None = None) -> Optional[str]:
    filename, _ = QFileDialog.getSaveFileName(parent, "Export selected data", "", EXPORT_FILTER)
    return filename or None


def save_image_file(parent: QWidget | None = None, initial_dir: str = "") -> Optional[str]:
    filename, _ = QFileDialog.getSaveFileName(
        parent, "Save plot image", initial_dir or "", IMAGE_FILTER
    )
    return filename or None
