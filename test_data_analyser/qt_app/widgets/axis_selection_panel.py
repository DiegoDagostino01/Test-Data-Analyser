"""Axis / channel selection panel.

Lets the user choose the X column, the Y channels, and an optional analysis
window, then request a plot or FFT. Holds no analysis logic; it only gathers the
selection for the plot workspace.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

PLOT_KINDS = ("Line", "Scatter", "Line + Markers")


class AxisSelectionPanel(QFrame):
    generateRequested = Signal()
    fftRequested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("EatonPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)

        heading = QLabel("Axes & Channels")
        heading.setObjectName("PanelHeading")
        layout.addWidget(heading)

        layout.addWidget(QLabel("X-axis column:"))
        self.x_combo = QComboBox()
        layout.addWidget(self.x_combo)

        layout.addWidget(QLabel("Y-axis channels:"))
        self.y_list = QListWidget()
        self.y_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        layout.addWidget(self.y_list, stretch=2)

        layout.addWidget(QLabel("Secondary Y-axis channels (right):"))
        self.secondary_y_list = QListWidget()
        self.secondary_y_list.setSelectionMode(QListWidget.SelectionMode.NoSelection)
        self.secondary_y_list.setMaximumHeight(110)
        layout.addWidget(self.secondary_y_list, stretch=1)

        kind_row = QHBoxLayout()
        kind_row.addWidget(QLabel("Plot kind:"))
        self.plot_kind_combo = QComboBox()
        self.plot_kind_combo.addItems(PLOT_KINDS)
        kind_row.addWidget(self.plot_kind_combo, stretch=1)
        layout.addLayout(kind_row)

        window_row = QHBoxLayout()
        window_row.addWidget(QLabel("Analysis window X:"))
        self.xmin_edit = QLineEdit()
        self.xmin_edit.setPlaceholderText("min")
        self.xmax_edit = QLineEdit()
        self.xmax_edit.setPlaceholderText("max")
        window_row.addWidget(self.xmin_edit)
        window_row.addWidget(self.xmax_edit)
        layout.addLayout(window_row)

        filter_row = QHBoxLayout()
        self.filter_check = QCheckBox("Low-pass filter")
        filter_row.addWidget(self.filter_check)
        filter_row.addWidget(QLabel("Cutoff Hz:"))
        self.cutoff_edit = QLineEdit()
        self.cutoff_edit.setPlaceholderText("e.g. 50")
        self.cutoff_edit.setFixedWidth(70)
        filter_row.addWidget(self.cutoff_edit)
        filter_row.addWidget(QLabel("Order:"))
        self.order_edit = QLineEdit("4")
        self.order_edit.setFixedWidth(40)
        filter_row.addWidget(self.order_edit)
        filter_row.addStretch(1)
        layout.addLayout(filter_row)

        button_row = QHBoxLayout()
        self.generate_button = QPushButton("Generate Plot")
        self.generate_button.setObjectName("PrimaryButton")
        self.generate_button.clicked.connect(self.generateRequested)
        self.fft_button = QPushButton("FFT")
        self.fft_button.clicked.connect(self.fftRequested)
        button_row.addWidget(self.generate_button)
        button_row.addWidget(self.fft_button)
        layout.addLayout(button_row)

        self.setMinimumWidth(280)

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------
    @staticmethod
    def _populate_checklist(widget: QListWidget, columns: list[str], skip: str, checked: set[str]) -> None:
        widget.clear()
        for column in columns:
            if column == skip:
                continue
            item = QListWidgetItem(column)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if column in checked else Qt.CheckState.Unchecked)
            widget.addItem(item)

    def set_columns(self, columns: list[str], suggested_x: str) -> None:
        self.x_combo.blockSignals(True)
        self.x_combo.clear()
        self.x_combo.addItems(columns)
        if suggested_x in columns:
            self.x_combo.setCurrentText(suggested_x)
        self.x_combo.blockSignals(False)

        self._populate_checklist(self.y_list, columns, suggested_x, set())
        self._populate_checklist(self.secondary_y_list, columns, suggested_x, set())

    def update_columns(self, columns: list[str]) -> None:
        """Refresh the available columns, preserving the current X and checked Y.

        Used when calculated channels add or remove columns so the user's current
        axis selection survives the refresh.
        """
        current_x = self.x_column()
        checked = set(self.selected_y())
        secondary = set(self.selected_secondary_y())

        self.x_combo.blockSignals(True)
        self.x_combo.clear()
        self.x_combo.addItems(columns)
        if current_x in columns:
            self.x_combo.setCurrentText(current_x)
        self.x_combo.blockSignals(False)
        new_x = self.x_combo.currentText()

        self._populate_checklist(self.y_list, columns, new_x, checked)
        self._populate_checklist(self.secondary_y_list, columns, new_x, secondary)

    def apply_selection(
        self,
        columns: list[str],
        x_column: str,
        y_columns: list[str],
        secondary_y_columns: list[str],
    ) -> None:
        """Populate the columns and restore a saved X / Y / secondary-Y selection."""
        skip_x = x_column or (columns[0] if columns else "")
        self.x_combo.blockSignals(True)
        self.x_combo.clear()
        self.x_combo.addItems(columns)
        if skip_x in columns:
            self.x_combo.setCurrentText(skip_x)
        self.x_combo.blockSignals(False)
        self._populate_checklist(self.y_list, columns, skip_x, set(y_columns))
        self._populate_checklist(self.secondary_y_list, columns, skip_x, set(secondary_y_columns))

    # ------------------------------------------------------------------
    # Selection accessors
    # ------------------------------------------------------------------
    def x_column(self) -> str:
        return self.x_combo.currentText()

    @staticmethod
    def _checked_items(widget: QListWidget) -> list[str]:
        return [
            widget.item(row).text()
            for row in range(widget.count())
            if widget.item(row).checkState() == Qt.CheckState.Checked
        ]

    def selected_y(self) -> list[str]:
        return self._checked_items(self.y_list)

    def selected_secondary_y(self) -> list[str]:
        return self._checked_items(self.secondary_y_list)

    def all_selected_y(self) -> list[str]:
        """Return primary + secondary Y channels (secondary appended, de-duplicated)."""
        primary = self.selected_y()
        return primary + [column for column in self.selected_secondary_y() if column not in primary]

    def plot_kind(self) -> str:
        return self.plot_kind_combo.currentText()

    def filter_settings(self) -> tuple[bool, Optional[float], int]:
        """Return ``(use_filter, cutoff_hz, order)`` for the low-pass filter."""
        cutoff = self._parse(self.cutoff_edit.text())
        try:
            order = int(float(self.order_edit.text())) if self.order_edit.text().strip() else 4
        except ValueError:
            order = 4
        return self.filter_check.isChecked(), cutoff, max(1, order)

    def analysis_window(self) -> tuple[Optional[float], Optional[float]]:
        return self._parse(self.xmin_edit.text()), self._parse(self.xmax_edit.text())

    @staticmethod
    def _parse(text: str) -> Optional[float]:
        text = text.strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None
