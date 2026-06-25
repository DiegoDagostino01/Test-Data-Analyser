"""Editable full-dataset Qt table model.

Backs the Raw Data panel's *Edit dataset* mode with the complete dataset (every
column and row), mapping each cell to a stable channel ID + row index and
routing edits through :class:`DatasetViewModel`. Structural changes are driven
by Raw Data panel gestures (header double-click, header context menus, and
header-only ``+`` controls), which call the viewmodel and then :meth:`refresh`
this model.

This adapter is the boundary between pandas/Qt and the viewmodel; it holds no
business logic of its own.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal

from ...viewmodels.dataset_vm import DatasetViewModel


class EditableDatasetModel(QAbstractTableModel):
    """Expose ``AppState``'s full dataframe + channel registry for editing."""

    cellEdited = Signal()
    cellWarning = Signal(str)
    editFailed = Signal(str)

    def __init__(self, dataset_vm: DatasetViewModel, parent=None) -> None:
        super().__init__(parent)
        self._vm = dataset_vm
        self._columns: list[dict[str, str]] = []

    # ------------------------------------------------------------------
    # Data management
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self.beginResetModel()
        self._columns = self._vm.editable_columns()
        self.endResetModel()

    @property
    def _df(self) -> Optional[pd.DataFrame]:
        return self._vm.state.df

    def channel_id_at(self, column: int) -> Optional[str]:
        if 0 <= column < len(self._columns):
            return self._columns[column]["id"]
        return None

    def data_row_count(self) -> int:
        return int(len(self._df)) if self._df is not None else 0

    def data_column_count(self) -> int:
        return len(self._columns)

    def is_add_row(self, row: int) -> bool:
        return row == self.data_row_count()

    def is_add_column(self, column: int) -> bool:
        return column == self.data_column_count()

    def is_data_index(self, index: QModelIndex) -> bool:
        return (
            index.isValid()
            and not self.is_add_row(index.row())
            and not self.is_add_column(index.column())
        )

    # ------------------------------------------------------------------
    # QAbstractTableModel interface
    # ------------------------------------------------------------------
    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid() or self._df is None:
            return 0
        return int(len(self._df)) + 1

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        if parent.isValid():
            return 0
        return len(self._columns) + 1

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid() or self._df is None:
            return None
        if self.is_add_row(index.row()) or self.is_add_column(index.column()):
            return None
        if role not in (Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole, Qt.ItemDataRole.ToolTipRole):
            return None
        column = self._columns[index.column()]
        name = column["display_name"]
        if name not in self._df.columns:
            return None
        value = self._df[name].iloc[index.row()]
        if role == Qt.ItemDataRole.EditRole:
            return "" if _is_blank(value) else str(value)
        return _format_value(value)

    def headerData(
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            if section == self.data_column_count():
                return "+"
            if 0 <= section < len(self._columns):
                column = self._columns[section]
                suffix = "" if column["data_type"] == "numeric" else "  (text)"
                return f"{column['display_name']}{suffix}"
            return None
        if section == self.data_row_count():
            return "+"
        return str(section + 1)

    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        if not index.isValid():
            return Qt.ItemFlag.NoItemFlags
        if self.is_add_row(index.row()) or self.is_add_column(index.column()):
            return Qt.ItemFlag.NoItemFlags
        return Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable | Qt.ItemFlag.ItemIsEditable

    def setData(self, index: QModelIndex, value, role: int = Qt.ItemDataRole.EditRole) -> bool:
        if not index.isValid() or role != Qt.ItemDataRole.EditRole or not self.is_data_index(index):
            return False
        channel_id = self.channel_id_at(index.column())
        if channel_id is None:
            return False
        result = self._vm.set_cell(channel_id, index.row(), value)
        if not result.ok:
            self.editFailed.emit(result.message)
            return False
        top_left = self.index(index.row(), index.column())
        self.dataChanged.emit(top_left, top_left, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])
        if result.warnings:
            self.cellWarning.emit(" ".join(result.warnings))
        self.cellEdited.emit()
        return True


def _is_blank(value: object) -> bool:
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return value is None


def _format_value(value: object) -> str:
    if _is_blank(value):
        return ""
    if isinstance(value, (float, np.floating)):
        return f"{float(value):.6g}"
    return str(value)
