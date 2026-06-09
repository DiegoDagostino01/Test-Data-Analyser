"""Raw Data panel.

Shows the selected X/Y channels as an editable table, mirroring the Tkinter Raw
Data tab: a row-display limit, an "apply analysis window" toggle, a "hide blank
rows" toggle, inline cell editing with undo, and an export action. The panel is
a thin Qt view; framing/filtering, edit coercion, undo, and export all run
through the framework-independent :class:`RawDataViewModel`.

The current axis/window selection lives in the axis-selection panel, so the main
window injects a *selection provider* callable that returns the live
``(x_col, selected_y, xmin, xmax)`` when the panel needs to refresh.
"""
from __future__ import annotations

from typing import Callable, Optional

import pandas as pd
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ...viewmodels.raw_data_vm import RawDataViewModel
from ..adapters import qt_file_dialogs, qt_message_service
from ..adapters.editable_raw_data_model import EditableRawDataTableModel

SelectionProvider = Callable[[], tuple[str, list[str], Optional[float], Optional[float]]]


class RawDataPanel(QWidget):
    def __init__(self, view_model: RawDataViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vm = view_model
        self._selection_provider: Optional[SelectionProvider] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(self._build_controls())

        self.model = EditableRawDataTableModel(self.vm.coerce_edit_value)
        self.model.cellEdited.connect(self._on_cell_edited)
        self.model.editFailed.connect(self._on_edit_failed)

        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked | QAbstractItemView.EditTrigger.EditKeyPressed
        )
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        layout.addWidget(self.table, stretch=1)

        self.status_label = QLabel("Select X/Y channels and click Refresh to view the raw data.")
        self.status_label.setObjectName("PlaceholderText")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self._update_undo_button()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_controls(self) -> QHBoxLayout:
        controls = QHBoxLayout()
        controls.addWidget(QLabel("Rows to display:"))
        self.row_limit_edit = QLineEdit("All")
        self.row_limit_edit.setFixedWidth(80)
        self.row_limit_edit.returnPressed.connect(self.refresh)
        controls.addWidget(self.row_limit_edit)

        self.apply_window_check = QCheckBox("Apply analysis window")
        self.apply_window_check.setChecked(True)
        self.apply_window_check.toggled.connect(self.refresh)
        controls.addWidget(self.apply_window_check)

        self.drop_blank_check = QCheckBox("Hide rows with blank cells")
        self.drop_blank_check.setChecked(True)
        self.drop_blank_check.toggled.connect(self.refresh)
        controls.addWidget(self.drop_blank_check)

        controls.addStretch(1)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        controls.addWidget(self.refresh_button)

        self.undo_button = QPushButton("Undo Edit")
        self.undo_button.clicked.connect(self._undo_edit)
        controls.addWidget(self.undo_button)

        self.export_button = QPushButton("Export…")
        self.export_button.clicked.connect(self._export)
        controls.addWidget(self.export_button)
        return controls

    # ------------------------------------------------------------------
    # Selection wiring
    # ------------------------------------------------------------------
    def set_selection_provider(self, provider: SelectionProvider) -> None:
        self._selection_provider = provider

    def _selection(self) -> tuple[str, list[str], Optional[float], Optional[float]]:
        if self._selection_provider is None:
            return "", [], None, None
        return self._selection_provider()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def clear(self) -> None:
        self.model.set_dataframe(pd.DataFrame())
        self.status_label.setText("Select X/Y channels and click Refresh to view the raw data.")

    def refresh(self) -> None:
        x_col, selected_y, xmin, xmax = self._selection()
        if not x_col or not selected_y:
            self.clear()
            return

        limit_result = self.vm.parse_row_limit(self.row_limit_edit.text())
        if not limit_result.ok:
            qt_message_service.warning(self, "Raw Data", limit_result.message)
            self.row_limit_edit.setText("All")
            limit: Optional[int] = None
        else:
            payload = limit_result.payload
            limit = payload if isinstance(payload, int) else None

        frame, removed = self.vm.select_frame(
            x_col,
            selected_y,
            apply_window=self.apply_window_check.isChecked(),
            xmin=xmin,
            xmax=xmax,
            drop_blank=self.drop_blank_check.isChecked(),
        )
        if frame.empty:
            self.model.set_dataframe(pd.DataFrame())
            self.status_label.setText("No complete selected X/Y rows to display.")
            return

        display = frame if limit is None else frame.head(limit)
        self.model.set_dataframe(display)
        self.status_label.setText(
            f"Selected raw data: {len(display):,} / {len(frame):,} rows, {display.shape[1]:,} columns. "
            f"Removed {removed:,} row(s) with blank cells. Double-click a cell to edit it."
        )

    # ------------------------------------------------------------------
    # Editing
    # ------------------------------------------------------------------
    def _on_cell_edited(self, df_index: object, column_name: str, value: object) -> None:
        result = self.vm.apply_edit(df_index, column_name, value)
        if result.ok:
            self.status_label.setText(f"Updated '{column_name}'. Use Undo Edit to restore the previous value.")
        self._update_undo_button()

    def _on_edit_failed(self, message: str) -> None:
        qt_message_service.error(self, "Raw Data Edit", message)

    def _undo_edit(self) -> None:
        result = self.vm.undo_last_edit()
        if not result.ok:
            qt_message_service.info(self, "Raw Data Undo", result.message)
            self._update_undo_button()
            return
        self.refresh()
        self.status_label.setText(result.message)
        self._update_undo_button()

    def _update_undo_button(self) -> None:
        self.undo_button.setEnabled(self.vm.can_undo)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def _export(self) -> None:
        x_col, selected_y, xmin, xmax = self._selection()
        if not x_col or not selected_y:
            qt_message_service.warning(self, "Export Selected Data", "Select X/Y channels before exporting.")
            return
        path = qt_file_dialogs.save_export_file(self)
        if not path:
            return
        result = self.vm.export_selected_frame(
            path,
            x_col,
            selected_y,
            apply_window=self.apply_window_check.isChecked(),
            xmin=xmin,
            xmax=xmax,
            drop_blank=self.drop_blank_check.isChecked(),
        )
        qt_message_service.show_result(self, "Export Selected Data", result)
