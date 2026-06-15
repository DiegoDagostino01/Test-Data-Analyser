"""Best-fit formula display panel."""
from __future__ import annotations

from PySide6.QtWidgets import QAbstractItemView, QHeaderView, QLabel, QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget


class BestFitFormulasPanel(QWidget):
    """Display generated best-fit equations for the active plot."""

    COLUMNS = ("Channel", "Fit", "Order", "Formula")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)

        self.table = QTableWidget(0, len(self.COLUMNS))
        self.table.setHorizontalHeaderLabels(self.COLUMNS)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.table, stretch=1)

        self.status_label = QLabel("Enable formula display in Edit Axis > Best Fits to show equations here.")
        self.status_label.setObjectName("PlaceholderText")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

    def set_rows(self, rows: list[dict[str, object]]) -> None:
        self.table.setRowCount(0)
        for row_data in rows:
            row = self.table.rowCount()
            self.table.insertRow(row)
            for column, key in enumerate(self.COLUMNS):
                item = QTableWidgetItem(str(row_data.get(key, "")))
                self.table.setItem(row, column, item)
        if rows:
            self.status_label.setText(f"Showing {len(rows)} best-fit formula(s) for the active plot.")
        else:
            self.status_label.setText("Enable formula display in Edit Axis > Best Fits to show equations here.")