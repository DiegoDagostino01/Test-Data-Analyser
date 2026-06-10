"""Data file panel.

Open a data file and (for Excel) select a sheet, loading through the
framework-independent :class:`DataLoadingViewModel`. Emits the loaded column
names so other panels can refresh.
"""
from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from ...viewmodels.data_loading_vm import DataLoadingViewModel
from ..adapters import qt_file_dialogs, qt_widget_helpers


class DataFilePanel(QFrame):
    fileLoaded = Signal(list)  # column names
    statusMessage = Signal(str)

    def __init__(self, view_model: DataLoadingViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("EatonPanel")
        self.vm = view_model
        self._current_path: str | None = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        heading = QLabel("Data File")
        heading.setObjectName("PanelHeading")
        layout.addWidget(heading)

        open_button = QPushButton("Open Data File…")
        open_button.setObjectName("PrimaryButton")
        open_button.clicked.connect(self.open_file)
        layout.addWidget(open_button)

        self.file_label = QLabel("No file loaded.")
        self.file_label.setObjectName("PlaceholderText")
        self.file_label.setWordWrap(True)
        layout.addWidget(self.file_label)

        self.sheet_row = QWidget()
        sheet_layout = QHBoxLayout(self.sheet_row)
        sheet_layout.setContentsMargins(0, 0, 0, 0)
        sheet_layout.addWidget(QLabel("Sheet:"))
        self.sheet_combo = QComboBox()
        self.sheet_combo.activated.connect(self._on_sheet_selected)
        sheet_layout.addWidget(self.sheet_combo, stretch=1)
        self.sheet_row.setVisible(False)
        layout.addWidget(self.sheet_row)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def open_file(self) -> None:
        manager = getattr(getattr(self.vm, "state", None), "settings_manager", None)
        filename = qt_file_dialogs.open_data_file(self, qt_widget_helpers.last_data_directory(manager))
        if not filename:
            return
        qt_widget_helpers.remember_data_directory(manager, filename)
        self._current_path = filename
        sheets = self.vm.get_sheets(filename)
        if sheets:
            self.sheet_combo.blockSignals(True)
            self.sheet_combo.clear()
            self.sheet_combo.addItems(sheets)
            self.sheet_combo.setCurrentIndex(0)
            self.sheet_combo.blockSignals(False)
            self.sheet_row.setVisible(True)
            self._load(filename, sheets[0])
        else:
            self.sheet_row.setVisible(False)
            self._load(filename, None)

    def _on_sheet_selected(self, _index: int) -> None:
        if self._current_path:
            self._load(self._current_path, self.sheet_combo.currentText())

    def _load(self, path: str, sheet_name: str | None) -> None:
        result = self.vm.load_file(path, sheet_name)
        self.statusMessage.emit(result.message)
        if not result.ok:
            self.file_label.setText(f"Could not load file:\n{result.message}")
            return
        self.file_label.setText(str(self.vm.state.filepath))
        self.fileLoaded.emit(result.payload or [])
