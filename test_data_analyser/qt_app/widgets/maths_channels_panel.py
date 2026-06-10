"""Maths (calculated) channels panel.

Create, validate, edit, recalculate, and delete calculated channels with a
definition form beside a table of defined channels. The panel is a thin Qt view;
all formula evaluation and channel CRUD run through the framework-independent
:class:`MathsChannelsViewModel`, which returns :class:`OperationResult` objects
the panel turns into dialogs/status.

Creating, deleting, or recalculating channels changes the dataframe columns, so
the panel emits :attr:`channelsChanged` for the main window to refresh the
dependent panels (axis selection, raw data).
"""
from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ...viewmodels.maths_channels_vm import MathsChannelsViewModel
from ..adapters import qt_message_service
from ..adapters.pandas_table_model import PandasTableModel

_EXAMPLES = (
    "Examples:\n"
    "`Outlet Pressure` - `Inlet Pressure`\n"
    "`Voltage` * `Current`\n"
    "rolling_mean(`Current`, 25)\n"
    "sqrt(abs(`Signal A`))\n"
    "clip(`Pressure`, 0, 500)\n"
    "Tip: wrap exact column names in backticks."
)


class MathsChannelsPanel(QWidget):
    channelsChanged = Signal()
    statusMessage = Signal(str)

    def __init__(self, view_model: MathsChannelsViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vm = view_model
        self._selected_name: str | None = None
        self._channel_order: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(self._build_toolbar())

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.setMinimumHeight(340)
        splitter.addWidget(self._build_form())
        splitter.addWidget(self._build_table())
        splitter.setStretchFactor(0, 2)
        splitter.setStretchFactor(1, 3)
        self.content_splitter = splitter

        self.content_scroll = QScrollArea()
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.content_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.content_scroll.setWidget(splitter)
        layout.addWidget(self.content_scroll, stretch=1)

        self.refresh()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        new_button = QPushButton("New / Clear Form")
        new_button.clicked.connect(self.clear_form)
        validate_button = QPushButton("Validate Formula")
        validate_button.clicked.connect(self._validate)
        apply_button = QPushButton("Apply / Save Channel")
        apply_button.setObjectName("PrimaryButton")
        apply_button.clicked.connect(self._apply)
        delete_button = QPushButton("Delete Channel")
        delete_button.clicked.connect(self._delete)
        recalc_button = QPushButton("Recalculate All")
        recalc_button.clicked.connect(self._recalculate)
        for button in (new_button, validate_button, apply_button, delete_button, recalc_button):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        return toolbar

    def _build_form(self) -> QWidget:
        frame = QFrame()
        frame.setObjectName("EatonPanel")
        frame.setMinimumHeight(320)
        outer = QVBoxLayout(frame)
        outer.setContentsMargins(12, 12, 12, 12)

        heading = QLabel("Maths Channel Definition")
        heading.setObjectName("PanelHeading")
        outer.addWidget(heading)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        form.addRow("Channel name:", self.name_edit)

        column_row = QWidget()
        column_layout = QHBoxLayout(column_row)
        column_layout.setContentsMargins(0, 0, 0, 0)
        self.column_combo = QComboBox()
        insert_button = QPushButton("Insert into Formula")
        insert_button.clicked.connect(self._insert_column)
        column_layout.addWidget(self.column_combo, stretch=1)
        column_layout.addWidget(insert_button)
        form.addRow("Existing column:", column_row)

        self.formula_edit = QPlainTextEdit()
        self.formula_edit.setMinimumHeight(90)
        self.formula_edit.setPlaceholderText("`Channel A` - `Channel B`")
        form.addRow("Formula:", self.formula_edit)

        self.description_edit = QLineEdit()
        form.addRow("Description:", self.description_edit)
        outer.addLayout(form)

        examples = QLabel(_EXAMPLES)
        examples.setObjectName("PlaceholderText")
        examples.setWordWrap(True)
        outer.addWidget(examples)
        outer.addStretch(1)
        return frame

    def _build_table(self) -> QWidget:
        self.model = PandasTableModel()
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.selectionModel().selectionChanged.connect(self._on_selection_changed)
        return self.table

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        columns = self.vm.state.column_names()
        current = self.column_combo.currentText()
        self.column_combo.blockSignals(True)
        self.column_combo.clear()
        self.column_combo.addItems(columns)
        if current in columns:
            self.column_combo.setCurrentText(current)
        self.column_combo.blockSignals(False)

        self._channel_order = self.vm.channel_names()
        self.model.set_dataframe(self.vm.channel_table())

    def clear_form(self) -> None:
        self._selected_name = None
        self.name_edit.clear()
        self.description_edit.clear()
        self.formula_edit.clear()
        self.table.clearSelection()

    # ------------------------------------------------------------------
    # Selection
    # ------------------------------------------------------------------
    def _on_selection_changed(self, *_args) -> None:
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        row = rows[0].row()
        if 0 <= row < len(self._channel_order):
            self._load_into_form(self._channel_order[row])

    def _load_into_form(self, name: str) -> None:
        definition = self.vm.state.calculated_channels.get(name)
        if definition is None:
            return
        self._selected_name = name
        self.name_edit.setText(definition.get("name", name))
        self.description_edit.setText(definition.get("description", ""))
        self.formula_edit.setPlainText(definition.get("formula", ""))

    def _select_channel(self, name: str) -> None:
        if name in self._channel_order:
            self.table.selectRow(self._channel_order.index(name))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _insert_column(self) -> None:
        column = self.column_combo.currentText().strip()
        if not column:
            qt_message_service.warning(self, "Maths Channels", "Select an existing column to insert.")
            return
        if "`" in column:
            qt_message_service.error(self, "Maths Channels", "Columns containing backticks cannot be inserted into formulas.")
            return
        self.formula_edit.insertPlainText(f"`{column}`")
        self.formula_edit.setFocus()

    def _validate(self) -> None:
        result = self.vm.validate_formula(self.formula_edit.toPlainText().strip())
        if not result.ok:
            qt_message_service.error(self, "Maths Channels", result.message)
            return
        payload = result.payload or {}
        if payload.get("numeric"):
            message = (
                f"{result.message}\n\n"
                f"Rows: {payload['rows']:,}\n"
                f"Numeric values: {payload['numeric']:,}\n"
                f"Min / Max: {payload['min']:.6g} / {payload['max']:.6g}"
            )
        else:
            message = result.message
        qt_message_service.info(self, "Maths Channels", message)

    def _apply(self) -> None:
        result = self.vm.apply_channel(
            self.name_edit.text(),
            self.formula_edit.toPlainText(),
            self.description_edit.text(),
            selected_name=self._selected_name,
        )
        if not result.ok:
            qt_message_service.error(self, "Maths Channels", result.message)
            self.statusMessage.emit(result.message)
            return
        applied_name = (result.payload or {}).get("name", self.name_edit.text().strip())
        self.refresh()
        self._select_channel(applied_name)
        self.channelsChanged.emit()
        self.statusMessage.emit(result.message)

    def _delete(self) -> None:
        name = self._selected_name or self.name_edit.text().strip()
        if not name or name not in self.vm.state.calculated_channels:
            qt_message_service.warning(self, "Maths Channels", "Select a Maths Channel to delete.")
            return
        if not qt_message_service.confirm(self, "Maths Channels", f"Delete Maths Channel '{name}'?"):
            return
        result = self.vm.delete_channel(name)
        if not result.ok:
            qt_message_service.warning(self, "Maths Channels", result.message)
            return
        self.clear_form()
        self.refresh()
        self.channelsChanged.emit()
        self.statusMessage.emit(result.message)

    def _recalculate(self) -> None:
        result = self.vm.recalculate()
        errors = (result.payload or {}).get("errors", []) if result.payload else []
        if errors:
            qt_message_service.warning(
                self,
                "Maths Channels",
                "Some Maths Channels could not be recalculated:\n\n" + "\n".join(errors),
            )
        else:
            qt_message_service.info(self, "Maths Channels", result.message)
        self.refresh()
        self.channelsChanged.emit()
        self.statusMessage.emit(result.message)
