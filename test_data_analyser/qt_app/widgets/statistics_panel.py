"""Statistics panel.

Displays per-channel statistics in a ``QTableView`` backed by the reusable
:class:`PandasTableModel`. The statistics themselves come from the
framework-independent :class:`PlotWorkspaceViewModel`.
"""
from __future__ import annotations

import pandas as pd
from PySide6.QtWidgets import QHeaderView, QTableView, QVBoxLayout, QWidget

from ..adapters.pandas_table_model import PandasTableModel


class StatisticsPanel(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.model = PandasTableModel(index_header="Signal")
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table)

    def set_statistics(self, stats: pd.DataFrame) -> None:
        self.model.set_dataframe(stats)
