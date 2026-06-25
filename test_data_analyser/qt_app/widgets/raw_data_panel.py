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

from typing import Any, Callable, Optional

from PySide6.QtCore import QEvent, QModelIndex, QPoint, Qt, Signal
from PySide6.QtGui import QGuiApplication, QKeyEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QAbstractItemDelegate,
    QCheckBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMenu,
    QPushButton,
    QStyledItemDelegate,
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


class RawDataCellDelegate(QStyledItemDelegate):
    enterPressed = Signal()

    def createEditor(self, parent: QWidget, option, index: QModelIndex):
        editor = super().createEditor(parent, option, index)
        if isinstance(editor, QLineEdit):
            editor.setObjectName("RawDataCellEditor")
            editor.setMinimumHeight(max(28, option.rect.height()))
            editor.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
            editor.setStyleSheet(
                "QLineEdit#RawDataCellEditor { padding: 3px 6px; min-height: 24px; }"
            )
        return editor

    def updateEditorGeometry(self, editor: QWidget, option, index: QModelIndex) -> None:
        rect = option.rect.adjusted(1, 1, -1, -1)
        if rect.height() < 28:
            rect.setHeight(28)
        editor.setGeometry(rect)

    def eventFilter(self, editor: QWidget, event: QEvent) -> bool:
        if (
            event.type() == QEvent.Type.KeyPress
            and isinstance(event, QKeyEvent)
            and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)
        ):
            self.commitData.emit(editor)
            self.closeEditor.emit(editor, QAbstractItemDelegate.EndEditHint.NoHint)
            self.enterPressed.emit()
            return True
        return super().eventFilter(editor, event)


class RawDataTableView(QTableView):
    def move_current_down(self) -> None:
        model = self.model()
        index = self.currentIndex()
        if model is None or not index.isValid():
            return
        data_row_count = getattr(model, "data_row_count", model.rowCount)()
        next_row = index.row() + 1
        if next_row >= data_row_count:
            return
        next_index = model.index(next_row, index.column())
        self.setCurrentIndex(next_index)
        self.scrollTo(next_index, QAbstractItemView.ScrollHint.EnsureVisible)

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.state() != QAbstractItemView.State.EditingState:
            index = self.currentIndex()
            model = self.model()
            is_data_index = getattr(model, "is_data_index", lambda current: current.isValid())
            if index.isValid() and is_data_index(index):
                self.edit(index)
                return
        super().keyPressEvent(event)


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
        self._sort_state: Optional[tuple[str, bool]] = None
        self._filter_enabled = False
        self._column_filters: dict[str, str] = {}
        self._filter_edits: dict[str, QLineEdit] = {}
        self._find_replace_dialog = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(self._build_controls())
        self.filter_row = self._build_filter_row()
        layout.addWidget(self.filter_row)

        self.model = EditableRawDataTableModel(self.vm.coerce_edit_value)
        self.model.cellEdited.connect(self._on_cell_edited)
        self.model.editFailed.connect(self._on_edit_failed)

        self.dataset_model = EditableDatasetModel(self.dataset_vm)
        self.dataset_model.cellEdited.connect(self._on_dataset_cell_edited)
        self.dataset_model.cellWarning.connect(self._on_dataset_cell_warning)
        self.dataset_model.editFailed.connect(self._on_edit_failed)

        self.table = RawDataTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.DoubleClicked
            | QAbstractItemView.EditTrigger.EditKeyPressed
            | QAbstractItemView.EditTrigger.AnyKeyPressed
        )
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectItems)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.verticalHeader().setDefaultSectionSize(30)
        self.table.verticalHeader().setMinimumSectionSize(28)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setMinimumSectionSize(36)
        self.table.horizontalHeader().setSectionsClickable(True)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().sectionClicked.connect(self._on_horizontal_header_clicked)
        self.table.horizontalHeader().sectionDoubleClicked.connect(self._rename_column_from_header)
        self.table.horizontalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.horizontalHeader().customContextMenuRequested.connect(self._show_column_context_menu)
        self.table.verticalHeader().setSectionsClickable(True)
        self.table.verticalHeader().sectionClicked.connect(self._on_vertical_header_clicked)
        self.table.verticalHeader().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.verticalHeader().customContextMenuRequested.connect(self._show_row_context_menu)
        self.table.viewport().setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.viewport().customContextMenuRequested.connect(self._show_table_context_menu)
        self.table.clicked.connect(self._on_table_clicked)
        self.cell_delegate = RawDataCellDelegate(self.table)
        self.cell_delegate.enterPressed.connect(self.table.move_current_down)
        self.table.setItemDelegate(self.cell_delegate)
        self._install_clipboard_shortcuts()
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

        self.filter_check = QCheckBox("Filter")
        self.filter_check.setToolTip("Show a per-column filter row (substring, or >n, <n, a..b, =n).")
        self.filter_check.toggled.connect(self._on_filter_toggled)
        controls.addWidget(self.filter_check)

        self.clear_filters_button = QPushButton("Clear filters")
        self.clear_filters_button.clicked.connect(self._clear_filters)
        self.clear_filters_button.setVisible(False)
        controls.addWidget(self.clear_filters_button)

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

    def _build_filter_row(self) -> QWidget:
        row = QWidget()
        row.setObjectName("RawDataFilterRow")
        self._filter_layout = QHBoxLayout(row)
        self._filter_layout.setContentsMargins(0, 0, 0, 0)
        self._filter_layout.setSpacing(4)
        row.setVisible(False)
        return row

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
        self._resize_inline_controls()
        self.status_label.setText("Select X/Y channels and click Refresh to view the raw data.")

    def refresh(self) -> None:
        x_col, selected_y, xmin, xmax = self._selection()
        if not x_col or not selected_y:
            self.clear()
            return

        sort_column, sort_ascending = self._active_sort()
        column_filters = self._active_filters() if self._filter_enabled else None
        result = self.vm.display_frame(
            x_col,
            selected_y,
            row_limit_text=self.row_limit_edit.text(),
            apply_window=self.apply_window_check.isChecked(),
            xmin=xmin,
            xmax=xmax,
            drop_blank=self.drop_blank_check.isChecked(),
            column_filters=column_filters,
            sort_column=sort_column,
            sort_ascending=sort_ascending,
        )
        for warning in result.warnings:
            qt_message_service.warning(self, "Raw Data", warning)
        payload = result.payload if isinstance(result.payload, dict) else {}
        if not payload.get("row_limit_valid", True):
            self.row_limit_edit.setText("All")
        frame = payload.get("frame", self.vm.empty_frame())
        self.model.set_dataframe(frame)
        self._resize_inline_controls()
        self._sync_sort_indicator()
        if self._filter_enabled and result.ok:
            self._rebuild_filter_row(list(frame.columns))
        self.status_label.setText(result.message)

    # ------------------------------------------------------------------
    # Sorting and filtering (read view only)
    # ------------------------------------------------------------------
    def _active_sort(self) -> tuple[Optional[str], bool]:
        if self._sort_state is None:
            return None, True
        return self._sort_state

    def _cycle_sort(self, section: int) -> None:
        column = self._view_column_name(section)
        if column is None:
            return
        if self._sort_state is None or self._sort_state[0] != column:
            self._sort_state = (column, True)
        elif self._sort_state[1]:
            self._sort_state = (column, False)
        else:
            self._sort_state = None
        self.refresh()

    def _view_column_name(self, section: int) -> Optional[str]:
        if section < 0 or section >= self.model.columnCount():
            return None
        name = self.model.headerData(section, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
        return str(name) if name is not None else None

    def _section_for_column(self, column: str) -> Optional[int]:
        for section in range(self.model.columnCount()):
            if self._view_column_name(section) == column:
                return section
        return None

    def _sync_sort_indicator(self) -> None:
        header = self.table.horizontalHeader()
        if self._sort_state is None or self._edit_mode:
            header.setSortIndicatorShown(False)
            return
        section = self._section_for_column(self._sort_state[0])
        if section is None:
            header.setSortIndicatorShown(False)
            return
        order = Qt.SortOrder.AscendingOrder if self._sort_state[1] else Qt.SortOrder.DescendingOrder
        header.setSortIndicatorShown(True)
        header.setSortIndicator(section, order)

    def _on_filter_toggled(self, enabled: bool) -> None:
        self._filter_enabled = enabled
        self.filter_row.setVisible(enabled)
        self.clear_filters_button.setVisible(enabled)
        self.refresh()

    def _on_filter_text_changed(self, column: str, text: str) -> None:
        if text.strip():
            self._column_filters[column] = text
        else:
            self._column_filters.pop(column, None)
        self.refresh()

    def _clear_filters(self) -> None:
        self._column_filters.clear()
        for edit in self._filter_edits.values():
            edit.blockSignals(True)
            edit.clear()
            edit.blockSignals(False)
        self.refresh()

    def _active_filters(self) -> dict[str, str]:
        return {column: text for column, text in self._column_filters.items() if text.strip()}

    def _rebuild_filter_row(self, columns: list[str]) -> None:
        if list(self._filter_edits.keys()) == columns:
            return
        while self._filter_layout.count():
            item = self._filter_layout.takeAt(0)
            if item is None:
                continue
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        self._filter_edits = {}
        for column in columns:
            edit = QLineEdit()
            edit.setPlaceholderText(column)
            edit.setToolTip(f"Filter {column}: substring, or >n, <n, >=n, <=n, a..b, =n")
            edit.setText(self._column_filters.get(column, ""))
            edit.textChanged.connect(lambda text, name=column: self._on_filter_text_changed(name, text))
            self._filter_edits[column] = edit
            self._filter_layout.addWidget(edit)

    def export_selected_data(self) -> None:
        self._export()

    # ------------------------------------------------------------------
    # Clipboard copy / cut / paste
    # ------------------------------------------------------------------
    def _install_clipboard_shortcuts(self) -> None:
        for key, handler in (
            (QKeySequence.StandardKey.Copy, self._on_copy),
            (QKeySequence.StandardKey.Cut, self._on_cut),
            (QKeySequence.StandardKey.Paste, self._on_paste),
        ):
            shortcut = QShortcut(key, self.table)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(handler)
        for key, replace_enabled in (
            (QKeySequence.StandardKey.Find, False),
            (QKeySequence.StandardKey.Replace, True),
        ):
            shortcut = QShortcut(key, self.table)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(lambda enabled=replace_enabled: self._open_find_replace(enabled))

    def _on_copy(self) -> None:
        rows, channel_ids = self._current_selection_block()
        if not rows or not channel_ids:
            return
        tsv = self.dataset_vm.copy_block(rows, channel_ids)
        QGuiApplication.clipboard().setText(tsv)
        self.status_label.setText(f"Copied {len(rows)} x {len(channel_ids)} cells.")

    def _on_cut(self) -> None:
        if not self._edit_mode:
            self.status_label.setText("Switch on 'Edit dataset' to cut cells.")
            return
        rows, channel_ids = self._current_selection_block()
        if not rows or not channel_ids:
            return
        result = self.dataset_vm.cut_block(rows, channel_ids)
        if result.ok:
            QGuiApplication.clipboard().setText(str(result.payload or ""))
            self.refresh_dataset()
            self.datasetChanged.emit()
        self.status_label.setText(result.message)

    def _on_paste(self) -> None:
        if not self._edit_mode:
            self.status_label.setText("Switch on 'Edit dataset' to paste cells.")
            return
        anchor = self._anchor_cell()
        if anchor is None:
            self.status_label.setText("Select a cell to paste into.")
            return
        text = QGuiApplication.clipboard().text()
        if not text:
            return
        top_row, channel_id = anchor
        result = self.dataset_vm.paste_block(top_row, channel_id, text)
        if result.ok:
            self.refresh_dataset()
            self.datasetChanged.emit()
            if result.warnings:
                qt_message_service.warning(self, "Paste", "\n".join(result.warnings))
        self.status_label.setText(result.message)

    def _current_selection_block(self) -> tuple[list[int], list[str]]:
        """Return ``(source_rows, channel_ids)`` for the selection's bounding box.

        Works in both view and edit mode by mapping the selected cell rectangle
        to source dataframe rows and channel IDs; phantom add-row/add-column
        cells are skipped.
        """
        selection = self.table.selectionModel()
        if selection is None:
            return [], []
        indexes = [index for index in selection.selectedIndexes() if index.isValid()]
        if not indexes:
            return [], []
        rows = sorted({index.row() for index in indexes})
        cols = sorted({index.column() for index in indexes})
        source_rows: list[int] = []
        for row in range(rows[0], rows[-1] + 1):
            df_row = self._source_row(row)
            if df_row is not None:
                source_rows.append(df_row)
        channel_ids: list[str] = []
        for col in range(cols[0], cols[-1] + 1):
            channel_id = self._source_channel_id(col)
            if channel_id is not None:
                channel_ids.append(channel_id)
        return source_rows, channel_ids

    def _anchor_cell(self) -> Optional[tuple[int, str]]:
        index = self.table.currentIndex()
        if not index.isValid():
            selection = self.table.selectionModel()
            indexes = [i for i in selection.selectedIndexes() if i.isValid()] if selection else []
            if not indexes:
                return None
            index = min(indexes, key=lambda i: (i.row(), i.column()))
        df_row = self._source_row(index.row())
        channel_id = self._source_channel_id(index.column())
        if df_row is None or channel_id is None:
            return None
        return df_row, channel_id

    def _source_row(self, view_row: int) -> Optional[int]:
        if view_row < 0:
            return None
        if self._edit_mode:
            if self.dataset_model.is_add_row(view_row):
                return None
            return view_row
        label = self.model.source_row_at(view_row)
        return None if label is None else int(label)

    def _source_channel_id(self, view_col: int) -> Optional[str]:
        if view_col < 0:
            return None
        if self._edit_mode:
            if self.dataset_model.is_add_column(view_col):
                return None
            return self.dataset_model.channel_id_at(view_col)
        name = self.model.column_name_at(view_col)
        if name is None:
            return None
        return self.dataset_vm.state.channel_id_for_name(name)

    # ------------------------------------------------------------------
    # Find & replace
    # ------------------------------------------------------------------
    def _open_find_replace(self, replace_enabled: bool) -> None:
        if self._find_replace_dialog is None:
            from .find_replace_dialog import FindReplaceDialog

            self._find_replace_dialog = FindReplaceDialog(self, replace_enabled=replace_enabled, parent=self)
        else:
            self._find_replace_dialog.set_replace_enabled(replace_enabled)
        self._find_replace_dialog.show()
        self._find_replace_dialog.raise_()
        self._find_replace_dialog.focus_query()

    def current_display_frame(self):
        """Return the dataframe currently shown in the read view, or ``None``.

        Used by the Find dialog for the 'displayed view only' search scope; in
        edit mode there is no read-view frame, so the search falls back to the
        full dataset.
        """
        if self._edit_mode:
            return None
        return self.model.dataframe

    def after_find_replace(self) -> None:
        """Refresh the table and undo state after a dialog-driven replacement."""
        if self._edit_mode:
            self.refresh_dataset()
        else:
            self.refresh()
        self._update_undo_button()
        self.datasetChanged.emit()

    def focus_source_cell(self, row_label: Any, column_name: str) -> bool:
        """Select the table cell for a source ``(row label, column)`` if visible."""
        model = self.table.model()
        if model is None:
            return False
        target_col = None
        for col in range(model.columnCount()):
            header = model.headerData(col, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole)
            if header is not None and str(header) == column_name:
                target_col = col
                break
        if target_col is None:
            return False
        target_row = None
        if self._edit_mode:
            try:
                row = int(row_label)
            except (TypeError, ValueError):
                return False
            if 0 <= row < model.rowCount():
                target_row = row
        else:
            for row in range(self.model.rowCount()):
                if self.model.source_row_at(row) == row_label:
                    target_row = row
                    break
        if target_row is None:
            return False
        index = model.index(target_row, target_col)
        self.table.setCurrentIndex(index)
        self.table.scrollTo(index, QAbstractItemView.ScrollHint.EnsureVisible)
        return True

    # ------------------------------------------------------------------
    # Fill (fill-down / drag-fill)
    # ------------------------------------------------------------------
    def fill_handle_visible(self) -> bool:
        """Whether an Excel-style fill handle applies to the current selection.

        Offered only in edit mode for a non-empty data selection; the fill itself
        is available via the right-click "Fill Down" action.
        """
        if not self._edit_mode:
            return False
        selection = self.table.selectionModel()
        if selection is None:
            return False
        return any(index.isValid() for index in selection.selectedIndexes())

    def _fill_down(self, rows: list[int], channel_ids: list[str]) -> None:
        result = self.dataset_vm.fill_down(rows, channel_ids)
        if result.ok:
            self.refresh_dataset()
            self.datasetChanged.emit()
            self._update_undo_button()
        self.status_label.setText(result.message)

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
        self._resize_inline_controls()
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
            self.filter_check,
            self.clear_filters_button,
        ):
            widget.setEnabled(not enabled)
        if enabled:
            self.filter_row.setVisible(False)
        elif self._filter_enabled:
            self.filter_row.setVisible(True)
        self._resize_inline_controls()
        self._sync_sort_indicator()
        self._update_undo_button()

    def _resize_inline_controls(self) -> None:
        header = self.table.horizontalHeader()
        header.setStretchLastSection(False)
        if not self._edit_mode or self.table.model() is not self.dataset_model:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
            self._resize_columns_to_headers()
            return
        add_column = self.dataset_model.data_column_count()
        for section in range(self.dataset_model.columnCount()):
            mode = QHeaderView.ResizeMode.Fixed if section == add_column else QHeaderView.ResizeMode.Interactive
            header.setSectionResizeMode(section, mode)
        self._resize_columns_to_headers(exclude={add_column})
        if add_column < self.dataset_model.columnCount():
            self.table.setColumnWidth(add_column, 36)
        add_row = self.dataset_model.data_row_count()
        if add_row < self.dataset_model.rowCount():
            self.table.setRowHeight(add_row, 30)

    def _resize_columns_to_headers(self, *, exclude: set[int] | None = None) -> None:
        model = self.table.model()
        if model is None:
            return
        excluded = exclude or set()
        metrics = self.table.horizontalHeader().fontMetrics()
        for section in range(model.columnCount()):
            if section in excluded:
                continue
            header_text = model.headerData(
                section,
                Qt.Orientation.Horizontal,
                Qt.ItemDataRole.DisplayRole,
            )
            if header_text is None:
                continue
            width = max(72, metrics.horizontalAdvance(str(header_text)) + 34)
            self.table.setColumnWidth(section, max(self.table.columnWidth(section), width))

    def _on_table_clicked(self, index: QModelIndex) -> None:
        return

    def _on_horizontal_header_clicked(self, section: int) -> None:
        if self._edit_mode:
            if self.dataset_model.is_add_column(section):
                self._add_column()
            return
        self._cycle_sort(section)

    def _on_vertical_header_clicked(self, section: int) -> None:
        if self._edit_mode and self.dataset_model.is_add_row(section):
            self._add_row()

    def _rename_column_from_header(self, section: int) -> None:
        if not self._edit_mode:
            return
        if self.dataset_model.is_add_column(section):
            self._add_column()
            return
        self._rename_column(self.dataset_model.channel_id_at(section))

    def _show_table_context_menu(self, position: QPoint) -> None:
        if not self._edit_mode:
            return
        index = self.table.indexAt(position)
        if not index.isValid():
            return
        menu = QMenu(self)
        if self.dataset_model.is_add_column(index.column()):
            return
        elif self.dataset_model.is_add_row(index.row()):
            return
        else:
            self.table.setCurrentIndex(index)
            rows = self._selected_data_rows(index)
            channel_ids = self._selected_column_ids(index.column())
            if rows:
                menu.addAction(f"Delete {len(rows)} Row(s)", lambda checked=False, selected=rows: self._delete_rows(selected))
            if channel_ids:
                label = "Delete Column" if len(channel_ids) == 1 else f"Delete {len(channel_ids)} Columns"
                menu.addAction(label, lambda checked=False, selected=channel_ids: self._delete_columns(selected))
            block_rows, block_ids = self._current_selection_block()
            if len(block_rows) >= 2 and block_ids:
                menu.addAction(
                    "Fill Down",
                    lambda checked=False, r=block_rows, c=block_ids: self._fill_down(r, c),
                )
        if not menu.isEmpty():
            menu.exec(self.table.viewport().mapToGlobal(position))

    def _show_column_context_menu(self, position: QPoint) -> None:
        if not self._edit_mode:
            return
        section = self.table.horizontalHeader().logicalIndexAt(position)
        if section < 0:
            return
        menu = QMenu(self)
        if self.dataset_model.is_add_column(section):
            menu.addAction("Add Column", self._add_column)
        else:
            channel_id = self.dataset_model.channel_id_at(section)
            if channel_id is not None:
                menu.addAction("Rename Column", lambda checked=False, selected=channel_id: self._rename_column(selected))
                channel_ids = self._selected_column_ids(section)
                label = "Delete Column" if len(channel_ids) == 1 else f"Delete {len(channel_ids)} Columns"
                menu.addAction(label, lambda checked=False, selected=channel_ids: self._delete_columns(selected))
        if not menu.isEmpty():
            menu.exec(self.table.horizontalHeader().mapToGlobal(position))

    def _show_row_context_menu(self, position: QPoint) -> None:
        if not self._edit_mode:
            return
        section = self.table.verticalHeader().logicalIndexAt(position)
        if section < 0:
            return
        menu = QMenu(self)
        if self.dataset_model.is_add_row(section):
            menu.addAction("Add Row", self._add_row)
        else:
            rows = self._selected_data_rows(self.dataset_model.index(section, 0))
            if section not in rows:
                rows = [section]
            menu.addAction(f"Delete {len(rows)} Row(s)", lambda checked=False, selected=rows: self._delete_rows(selected))
        if not menu.isEmpty():
            menu.exec(self.table.verticalHeader().mapToGlobal(position))

    def _selected_data_rows(self, fallback: QModelIndex | None = None) -> list[int]:
        selection_model = self.table.selectionModel()
        rows: set[int] = set()
        if selection_model is not None:
            rows = {
                index.row()
                for index in selection_model.selectedIndexes()
                if self.dataset_model.is_data_index(index)
            }
        if not rows and fallback is not None and self.dataset_model.is_data_index(fallback):
            rows.add(fallback.row())
        return sorted(rows)

    def _selected_column_ids(self, fallback_section: int | None = None) -> list[str]:
        selection_model = self.table.selectionModel()
        sections: set[int] = set()
        if selection_model is not None:
            sections = {
                index.column()
                for index in selection_model.selectedColumns()
                if not self.dataset_model.is_add_column(index.column())
            }
        if not sections and fallback_section is not None and not self.dataset_model.is_add_column(fallback_section):
            sections.add(fallback_section)
        return [
            channel_id
            for section in sorted(sections)
            if (channel_id := self.dataset_model.channel_id_at(section)) is not None
        ]

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
        self._update_undo_button()
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

    def _rename_column(self, channel_id: Optional[str] = None) -> None:
        channel_id = channel_id or self._selected_column_id()
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

    def _delete_column(self, channel_id: Optional[str] = None) -> None:
        channel_id = channel_id or self._selected_column_id()
        if channel_id is None:
            qt_message_service.warning(self, "Delete Column", "There is no column to delete.")
            return
        self._delete_columns([channel_id])

    def _delete_columns(self, channel_ids: list[str]) -> None:
        if not channel_ids:
            qt_message_service.warning(self, "Delete Column", "There is no column to delete.")
            return
        names = [self.dataset_vm.state.name_for_channel_id(channel_id) or "" for channel_id in channel_ids]
        names = [name for name in names if name]
        title = "Delete Column" if len(names) == 1 else "Delete Columns"
        if len(names) == 1:
            prompt = f'Delete column "{names[0]}"?'
        else:
            prompt = f"Delete {len(names)} selected columns?"
        if not qt_message_service.confirm(self, title, prompt):
            return
        result = self.dataset_vm.delete_columns(channel_ids)
        if not result.ok:
            qt_message_service.warning(self, title, result.message)
            return
        self._after_structural_change(result)

    def _add_row(self) -> None:
        result = self.dataset_vm.add_row()
        if not result.ok:
            qt_message_service.warning(self, "Add Row", result.message)
            return
        self._after_structural_change(result)

    def _delete_rows(self, rows: Optional[list[int]] = None) -> None:
        rows = rows if rows is not None else self._selected_data_rows()
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
        self.status_label.setText("Cell updated.")
        self._update_undo_button()
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
        result = self.dataset_vm.undo_last_edit() if self._edit_mode else self.vm.undo_last_edit()
        if not result.ok:
            qt_message_service.info(self, "Raw Data Undo", result.message)
            self._update_undo_button()
            return
        if self._edit_mode:
            self.refresh_dataset()
            self.datasetChanged.emit()
        else:
            self.refresh()
        self.status_label.setText(result.message)
        self._update_undo_button()

    def _update_undo_button(self) -> None:
        can_undo = self.dataset_vm.can_undo if self._edit_mode else self.vm.can_undo
        self.undo_button.setEnabled(can_undo)

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
