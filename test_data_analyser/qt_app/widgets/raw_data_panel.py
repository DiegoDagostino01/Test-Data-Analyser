"""Raw Data panel.

Shows the selected X/Y channels as an editable table with a row-display limit,
an "apply analysis window" toggle, a "hide blank rows" toggle, inline cell
editing with undo, and an export action. The panel is a thin Qt view;
framing/filtering, edit coercion, undo, and export all run
through the framework-independent :class:`RawDataViewModel`.

The current axis/window selection lives in the axis-selection panel, so the main
window injects a *selection provider* callable that returns the live
``(x_col, selected_y, xmin, xmax)`` when the panel needs to refresh.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QPushButton,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ...viewmodels.dataset_vm import DatasetViewModel
from ...viewmodels.raw_data_vm import RawDataViewModel
from ..adapters import qt_file_dialogs, qt_message_service
from ..adapters.editable_dataset_model import EditableDatasetModel
from ..adapters.editable_raw_data_model import EditableRawDataTableModel

SelectionProvider = Callable[[], tuple[str, list[str], Optional[float], Optional[float]]]


class RawDataPanel(QWidget):
    datasetChanged = Signal()

    def __init__(
        self,
        view_model: RawDataViewModel,
        dataset_view_model: DatasetViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.vm = view_model
        self.dataset_vm = dataset_view_model
        self._selection_provider: Optional[SelectionProvider] = None
        self._edit_mode = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(self._build_controls())
        layout.addLayout(self._build_structural_toolbar())

        self.model = EditableRawDataTableModel(self.vm.coerce_edit_value)
        self.model.cellEdited.connect(self._on_cell_edited)
        self.model.editFailed.connect(self._on_edit_failed)

        self.dataset_model = EditableDatasetModel(self.dataset_vm)
        self.dataset_model.cellEdited.connect(self._on_dataset_cell_edited)
        self.dataset_model.cellWarning.connect(self._on_dataset_cell_warning)
        self.dataset_model.editFailed.connect(self._on_edit_failed)

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
        self._update_structural_toolbar_visibility()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_controls(self) -> QHBoxLayout:
        controls = QHBoxLayout()
        self.edit_mode_check = QCheckBox("Edit dataset")
        self.edit_mode_check.setToolTip(
            "Edit the full dataset: add, rename or delete columns and rows. "
            "Changes affect the current session only."
        )
        self.edit_mode_check.toggled.connect(self._on_edit_mode_toggled)
        controls.addWidget(self.edit_mode_check)

        self.row_limit_label = QLabel("Rows to display:")
        controls.addWidget(self.row_limit_label)
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

    def _build_structural_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        self._structural_buttons: list[QPushButton] = []
        for text, handler in [
            ("Add Column", self._add_column),
            ("Rename Column", self._rename_column),
            ("Delete Column", self._delete_column),
            ("Add Row", self._add_row),
            ("Delete Row(s)", self._delete_rows),
        ]:
            button = QPushButton(text)
            button.clicked.connect(handler)
            toolbar.addWidget(button)
            self._structural_buttons.append(button)
        toolbar.addStretch(1)
        return toolbar

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
        self.model.set_dataframe(self.vm.empty_frame())
        self.status_label.setText("Select X/Y channels and click Refresh to view the raw data.")

    def refresh(self) -> None:
        x_col, selected_y, xmin, xmax = self._selection()
        if not x_col or not selected_y:
            self.clear()
            return

        result = self.vm.display_frame(
            x_col,
            selected_y,
            row_limit_text=self.row_limit_edit.text(),
            apply_window=self.apply_window_check.isChecked(),
            xmin=xmin,
            xmax=xmax,
            drop_blank=self.drop_blank_check.isChecked(),
        )
        for warning in result.warnings:
            qt_message_service.warning(self, "Raw Data", warning)
        payload = result.payload if isinstance(result.payload, dict) else {}
        if not payload.get("row_limit_valid", True):
            self.row_limit_edit.setText("All")
        frame = payload.get("frame", self.vm.empty_frame())
        if not result.ok:
            self.model.set_dataframe(frame)
            self.status_label.setText(result.message)
            return
        self.model.set_dataframe(frame)
        self.status_label.setText(result.message)

    def export_selected_data(self) -> None:
        self._export()

    # ------------------------------------------------------------------
    # Full-dataset editing (Edit dataset mode)
    # ------------------------------------------------------------------
    def enter_edit_mode(self) -> None:
        """Switch the panel into full-dataset edit mode (used for manual sessions)."""
        if self.edit_mode_check.isChecked():
            self._apply_edit_mode(True)
        else:
            self.edit_mode_check.setChecked(True)

    def refresh_dataset(self) -> None:
        self.dataset_model.refresh()
        df = self.dataset_vm.state.df
        rows = len(df) if df is not None else 0
        columns = len(self.dataset_vm.editable_columns())
        self.status_label.setText(
            f"Editing dataset: {columns} column(s) × {rows} row(s). "
            "Changes affect the current session only."
        )

    def _on_edit_mode_toggled(self, enabled: bool) -> None:
        self._apply_edit_mode(enabled)

    def _apply_edit_mode(self, enabled: bool) -> None:
        self._edit_mode = enabled
        if enabled:
            self.table.setModel(self.dataset_model)
            self.refresh_dataset()
        else:
            self.table.setModel(self.model)
            self.refresh()
        # Filter/inspection controls only apply to the read view; disabling them
        # in edit mode keeps row indices aligned 1:1 for structural edits.
        for widget in (
            self.row_limit_label,
            self.row_limit_edit,
            self.apply_window_check,
            self.drop_blank_check,
            self.refresh_button,
            self.undo_button,
        ):
            widget.setEnabled(not enabled)
        self._update_structural_toolbar_visibility()
        if not enabled:
            self._update_undo_button()

    def _update_structural_toolbar_visibility(self) -> None:
        for button in getattr(self, "_structural_buttons", []):
            button.setVisible(self._edit_mode)

    def _selected_column_id(self) -> Optional[str]:
        index = self.table.currentIndex()
        if index.isValid():
            channel_id = self.dataset_model.channel_id_at(index.column())
            if channel_id:
                return channel_id
        columns = self.dataset_vm.editable_columns()
        return columns[0]["id"] if columns else None

    def _after_structural_change(self, result) -> None:
        self.refresh_dataset()
        for warning in result.warnings:
            qt_message_service.warning(self, "Edit Dataset", warning)
        self.datasetChanged.emit()

    def _add_column(self) -> None:
        name, ok = QInputDialog.getText(self, "Add Column", "New column name:")
        if not ok or not name.strip():
            return
        result = self.dataset_vm.add_column(name.strip())
        if not result.ok:
            qt_message_service.warning(self, "Add Column", result.message)
            return
        self._after_structural_change(result)

    def _rename_column(self) -> None:
        channel_id = self._selected_column_id()
        if channel_id is None:
            qt_message_service.warning(self, "Rename Column", "Add a column first.")
            return
        current = self.dataset_vm.state.name_for_channel_id(channel_id) or ""
        name, ok = QInputDialog.getText(self, "Rename Column", "New column name:", text=current)
        if not ok or not name.strip():
            return
        result = self.dataset_vm.rename_column(channel_id, name.strip())
        if not result.ok:
            qt_message_service.warning(self, "Rename Column", result.message)
            return
        self._after_structural_change(result)

    def _delete_column(self) -> None:
        channel_id = self._selected_column_id()
        if channel_id is None:
            qt_message_service.warning(self, "Delete Column", "There is no column to delete.")
            return
        name = self.dataset_vm.state.name_for_channel_id(channel_id) or ""
        if not qt_message_service.confirm(self, "Delete Column", f'Delete column "{name}"?'):
            return
        result = self.dataset_vm.delete_column(channel_id)
        if not result.ok:
            qt_message_service.warning(self, "Delete Column", result.message)
            return
        self._after_structural_change(result)

    def _add_row(self) -> None:
        result = self.dataset_vm.add_row()
        if not result.ok:
            qt_message_service.warning(self, "Add Row", result.message)
            return
        self._after_structural_change(result)

    def _delete_rows(self) -> None:
        selection_model = self.table.selectionModel()
        rows = sorted({index.row() for index in selection_model.selectedIndexes()}) if selection_model else []
        if not rows:
            qt_message_service.warning(self, "Delete Row(s)", "Select one or more rows to delete.")
            return
        if not qt_message_service.confirm(self, "Delete Row(s)", f"Delete {len(rows)} selected row(s)?"):
            return
        result = self.dataset_vm.delete_rows(rows)
        if not result.ok:
            qt_message_service.warning(self, "Delete Row(s)", result.message)
            return
        self._after_structural_change(result)

    def _on_dataset_cell_edited(self) -> None:
        self.datasetChanged.emit()

    def _on_dataset_cell_warning(self, message: str) -> None:
        self.status_label.setText(message)

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
