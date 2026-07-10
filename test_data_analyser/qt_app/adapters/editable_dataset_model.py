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

#: Number of dataframe rows loaded into the live editable window at once. Editing
#: binds rows to a real ``QTableView``; loading only a window of this size and
#: sliding it as the user scrolls keeps very large datasets responsive instead of
#: binding millions of rows at once. Datasets at or below this size load fully.
MAX_EDITABLE_ROWS = 1_000


class EditableDatasetModel(QAbstractTableModel):
    """Expose ``AppState``'s full dataframe + channel registry for editing."""

    cellEdited = Signal()
    cellWarning = Signal(str)
    editFailed = Signal(str)

    def __init__(self, dataset_vm: DatasetViewModel, parent=None) -> None:
        super().__init__(parent)
        self._vm = dataset_vm
        self._columns: list[dict[str, str]] = []
        self._window_start = 0

    # ------------------------------------------------------------------
    # Data management
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self.beginResetModel()
        self._columns = self._vm.editable_columns()
        self._window_start = self._clamp_window_start(self._window_start)
        self.endResetModel()

    @property
    def _df(self) -> Optional[pd.DataFrame]:
        return self._vm.state.df

    def channel_id_at(self, column: int) -> Optional[str]:
        if 0 <= column < len(self._columns):
            return self._columns[column]["id"]
        return None

    def data_row_count(self) -> int:
        """Number of editable data rows currently loaded (the window size)."""
        return self.window_row_count()

    def total_data_row_count(self) -> int:
        """Total rows in the dataframe, ignoring the loaded-window size."""
        return int(len(self._df)) if self._df is not None else 0

    def window_start(self) -> int:
        """First dataframe row currently loaded into the editable window."""
        return self._window_start

    def window_row_count(self) -> int:
        """Number of dataframe rows loaded in the current window (<= cap)."""
        total = self.total_data_row_count()
        if total <= 0:
            return 0
        return min(MAX_EDITABLE_ROWS, total - self._window_start)

    def is_row_capped(self) -> bool:
        """Whether the dataframe has more rows than one window can load at once."""
        return self.total_data_row_count() > MAX_EDITABLE_ROWS

    def is_window_at_end(self) -> bool:
        """Whether the loaded window reaches the final dataframe row."""
        return self._window_start + self.window_row_count() >= self.total_data_row_count()

    def can_load_more_below(self) -> bool:
        return self._window_start + self.window_row_count() < self.total_data_row_count()

    def can_load_more_above(self) -> bool:
        return self._window_start > 0

    def df_row_for_view(self, view_row: int) -> int:
        """Map a view row to its dataframe row using the window offset."""
        return self._window_start + int(view_row)

    def view_row_for_df(self, df_row: int) -> Optional[int]:
        """Map a dataframe row to its view row, or ``None`` if outside the window."""
        view_row = int(df_row) - self._window_start
        return view_row if 0 <= view_row < self.window_row_count() else None

    def _clamp_window_start(self, value: int) -> int:
        max_start = max(0, self.total_data_row_count() - MAX_EDITABLE_ROWS)
        return max(0, min(int(value), max_start))

    def reset_window(self) -> None:
        """Move the window back to the top without emitting a model reset."""
        self._window_start = 0

    def set_window_start(self, value: int) -> bool:
        """Slide the loaded window to start at ``value`` (clamped).

        Returns ``True`` when the window actually moved, emitting a model reset so
        the view reloads the new block of rows.
        """
        new_start = self._clamp_window_start(value)
        if new_start == self._window_start:
            return False
        self.beginResetModel()
        self._window_start = new_start
        self.endResetModel()
        return True

    def data_column_count(self) -> int:
        return len(self._columns)

    def is_add_row(self, row: int) -> bool:
        return self.is_window_at_end() and row == self.window_row_count()

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
        count = self.window_row_count()
        if self.is_window_at_end():
            count += 1  # trailing add-row, only when the dataset end is loaded
        return count

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
        value = self._df[name].iloc[self._window_start + index.row()]
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
        if self.is_add_row(section):
            return "+"
        return str(self._window_start + section + 1)

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
        result = self._vm.set_cell(channel_id, self._window_start + index.row(), value)
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
