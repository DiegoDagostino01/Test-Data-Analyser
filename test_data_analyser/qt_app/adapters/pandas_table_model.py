"""Reusable Qt table model backed by a pandas DataFrame.

A single :class:`QAbstractTableModel` implementation that backs the raw-data
view, the statistics view, and the comparison-statistics view. Using Qt's
model/view here means large tables are rendered lazily instead of inserting
thousands of widget rows.

This adapter is the boundary between pandas and Qt; it imports both but contains
no business logic.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt


class PandasTableModel(QAbstractTableModel):
    """Expose a :class:`pandas.DataFrame` to Qt item views.

    When ``index_header`` is provided, the DataFrame index is shown as the first
    column under that header (used by the statistics view, which is indexed by
    channel name).
    """

    def __init__(self, df: Optional[pd.DataFrame] = None, index_header: Optional[str] = None) -> None:
        super().__init__()
        self._index_header = index_header
        self._df = pd.DataFrame() if df is None else df

    # ------------------------------------------------------------------
    # Data management
    # ------------------------------------------------------------------
    def set_dataframe(self, df: Optional[pd.DataFrame]) -> None:
        self.beginResetModel()
        self._df = pd.DataFrame() if df is None else df
        self.endResetModel()

    @property
    def dataframe(self) -> pd.DataFrame:
        return self._df

    def _has_index_column(self) -> bool:
        return self._index_header is not None

    # ------------------------------------------------------------------
    # QAbstractTableModel interface
    # ------------------------------------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return int(len(self._df))

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return int(self._df.shape[1]) + (1 if self._has_index_column() else 0)

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if not index.isValid():
            return None
        if role not in (Qt.DisplayRole, Qt.ToolTipRole):
            return None
        row = index.row()
        col = index.column()
        if self._has_index_column():
            if col == 0:
                return str(self._df.index[row])
            col -= 1
        value = self._df.iat[row, col]
        return self._format_value(value)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.DisplayRole):
        if role != Qt.DisplayRole:
            return None
        if orientation == Qt.Horizontal:
            if self._has_index_column():
                if section == 0:
                    return self._index_header
                section -= 1
            if 0 <= section < self._df.shape[1]:
                return str(self._df.columns[section])
            return None
        return str(section + 1)

    @staticmethod
    def _format_value(value: object) -> str:
        if value is None:
            return ""
        try:
            if pd.isna(value):
                return ""
        except (TypeError, ValueError):
            pass
        if isinstance(value, (float, np.floating)):
            return f"{float(value):.6g}"
        return str(value)
