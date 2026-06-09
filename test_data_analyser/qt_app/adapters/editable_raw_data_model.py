"""Editable Qt table model for the Raw Data view.

A thin subclass of :class:`PandasTableModel` that adds inline cell editing. The
model owns only the *displayed* (selected/limited) copy of the data; edits are
validated through an injected ``coerce`` callback (the framework-independent
:class:`RawDataViewModel`) and a committed edit is announced via the
``cellEdited`` signal so the panel/viewmodel can write it back to the source
dataframe and manage undo. No business logic lives here.
"""
from __future__ import annotations

from typing import Any, Callable

import pandas as pd
from PySide6.QtCore import QModelIndex, Qt, Signal

from ...services.results import OperationResult
from .pandas_table_model import PandasTableModel


class EditableRawDataTableModel(PandasTableModel):
    """Pandas-backed model whose cells can be edited and validated inline.

    ``coerce`` maps ``(column_name, text)`` to an :class:`OperationResult` whose
    payload is the coerced value. Rejected edits leave the cell unchanged and
    raise :attr:`editFailed`; accepted edits update the displayed copy and raise
    :attr:`cellEdited` with ``(df_index, column_name, coerced_value)``.
    """

    cellEdited = Signal(object, str, object)
    editFailed = Signal(str)

    def __init__(self, coerce: Callable[[str, str], OperationResult], df: pd.DataFrame | None = None) -> None:
        super().__init__(df)
        self._coerce = coerce

    # ------------------------------------------------------------------
    # QAbstractTableModel editing interface
    # ------------------------------------------------------------------
    def flags(self, index: QModelIndex) -> Qt.ItemFlags:
        base = super().flags(index)
        if index.isValid():
            return base | Qt.ItemIsEditable
        return base

    def data(self, index: QModelIndex, role: int = Qt.DisplayRole):
        if role == Qt.EditRole and index.isValid():
            value = self._df.iat[index.row(), index.column()]
            try:
                if pd.isna(value):
                    return ""
            except (TypeError, ValueError):
                pass
            return str(value)
        return super().data(index, role)

    def setData(self, index: QModelIndex, value: Any, role: int = Qt.EditRole) -> bool:
        if role != Qt.EditRole or not index.isValid():
            return False
        column_name = str(self._df.columns[index.column()])
        result = self._coerce(column_name, "" if value is None else str(value))
        if not result.ok:
            self.editFailed.emit(result.message)
            return False
        coerced = result.payload
        old_value = self._df.iat[index.row(), index.column()]
        if self._values_equal(old_value, coerced):
            return False
        df_index = self._df.index[index.row()]
        if pd.api.types.is_integer_dtype(self._df[column_name]) and pd.isna(coerced):
            self._df[column_name] = self._df[column_name].astype(float)
        self._df.iat[index.row(), index.column()] = coerced
        self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])
        self.cellEdited.emit(df_index, column_name, coerced)
        return True

    @staticmethod
    def _values_equal(first: Any, second: Any) -> bool:
        if pd.isna(first) and pd.isna(second):
            return True
        try:
            return bool(first == second)
        except Exception:
            return False
