"""Requirements / Limits panel.

Create and edit requirement limit lines (name, type, applies-to, colour, and a
sorted list of X/Y points), then compute the margin-to-limit summary for the
current plot selection. The panel is a thin Qt view; all limit-line CRUD and
margin calculations run through the framework-independent
:class:`LimitsViewModel`; preparing the plot data for the summary uses the
:class:`PlotWorkspaceViewModel`.

Editing limits changes the overlays drawn on the plot, so the panel emits
:attr:`limitsChanged` for the main window to redraw the canvas. The current axis
selection (for the margin summary and the applies-to options) is supplied by an
injected selection provider, mirroring the Raw Data panel.
"""
from __future__ import annotations

from typing import Callable, Optional

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter
from PySide6.QtWidgets import (
    QAbstractItemView,
    QColorDialog,
    QFormLayout,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSplitter,
    QStyledItemDelegate,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ...services.limits_service import MARGIN_TABLE_COLUMNS
from ...viewmodels.limits_vm import LimitsViewModel
from .no_wheel_combo_box import NoWheelComboBox
from ...viewmodels.plot_workspace_vm import PlotWorkspaceViewModel
from ..adapters import qt_message_service
from ..adapters.pandas_table_model import PandasTableModel

SelectionProvider = Callable[[], tuple[str, list[str], Optional[float], Optional[float]]]

_CUSTOM = "Custom"


class MarginSummaryTableModel(QAbstractTableModel):
    def __init__(self, rows: list[dict[str, object]] | None = None) -> None:
        super().__init__()
        self._rows = list(rows or [])

    def set_rows(self, rows: list[dict[str, object]]) -> None:
        self.beginResetModel()
        self._rows = list(rows)
        self.endResetModel()

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self._rows)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(MARGIN_TABLE_COLUMNS)

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self._rows[index.row()]
        column = MARGIN_TABLE_COLUMNS[index.column()]
        value = row.get(column)
        if role == Qt.ItemDataRole.DisplayRole:
            return self._format_value(value, column)
        if role == Qt.ItemDataRole.ToolTipRole:
            return str(row.get("Details", ""))
        if column == "Status" and role == Qt.ItemDataRole.UserRole:
            return str(row.get("Severity", row.get("Status", "INFO")))
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if column in {"Margin", "Margin %", "Worst X", "Data Value", "Limit Value", "First Failure X"}:
                return Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            if column == "Status":
                return Qt.AlignmentFlag.AlignCenter
            return Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        if column == "Status" and role == Qt.ItemDataRole.BackgroundRole:
            return self._status_background(str(row.get("Severity", row.get("Status", "INFO"))))
        if column == "Status" and role == Qt.ItemDataRole.ForegroundRole:
            severity = str(row.get("Severity", row.get("Status", "INFO")))
            return QBrush(QColor("#111111" if severity == "WARN" else "#FFFFFF"))
        return None

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal and 0 <= section < len(MARGIN_TABLE_COLUMNS):
            return MARGIN_TABLE_COLUMNS[section]
        if orientation == Qt.Orientation.Vertical:
            return str(section + 1)
        return None

    @staticmethod
    def _format_value(value: object, column: str) -> str:
        if value is None:
            return ""
        if column == "Margin %":
            try:
                return f"{float(value):.3g}%"
            except (TypeError, ValueError):
                return ""
        if column in {"Margin", "Worst X", "Data Value", "Limit Value", "First Failure X"}:
            try:
                return f"{float(value):.6g}"
            except (TypeError, ValueError):
                return ""
        return str(value)

    @staticmethod
    def _status_background(severity: str) -> QBrush:
        colours = {
            "PASS": "#2E7D32",
            "WARN": "#F9C74F",
            "FAIL": "#C4262E",
            "INFO": "#607D8B",
            "SKIPPED": "#6C757D",
        }
        return QBrush(QColor(colours.get(severity, colours["INFO"])))

    @staticmethod
    def status_colour(severity: str) -> QColor:
        colours = {
            "PASS": "#2E7D32",
            "WARN": "#F9C74F",
            "FAIL": "#C4262E",
            "INFO": "#607D8B",
            "SKIPPED": "#6C757D",
        }
        return QColor(colours.get(severity, colours["INFO"]))


class MarginStatusDelegate(QStyledItemDelegate):
    def paint(self, painter: QPainter, option, index: QModelIndex) -> None:
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "")
        severity = str(index.data(Qt.ItemDataRole.UserRole) or text or "INFO")
        background = MarginSummaryTableModel.status_colour(severity)
        foreground = QColor("#111111" if severity == "WARN" else "#FFFFFF")
        painter.save()
        painter.fillRect(option.rect.adjusted(2, 2, -2, -2), background)
        painter.setPen(foreground)
        painter.drawText(option.rect, Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()


class LimitsPanel(QWidget):
    limitsChanged = Signal()
    statusMessage = Signal(str)

    def __init__(
        self,
        limits_vm: LimitsViewModel,
        plot_vm: PlotWorkspaceViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.vm = limits_vm
        self.plot_vm = plot_vm
        self._selection_provider: Optional[SelectionProvider] = None
        self._loading = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(self._build_toolbar())

        splitter = QSplitter()
        splitter.setChildrenCollapsible(False)
        splitter.setMinimumHeight(380)
        splitter.addWidget(self._build_lines_table())
        splitter.addWidget(self._build_editor())
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        self.content_splitter = splitter

        self.content_scroll = QScrollArea()
        self.content_scroll.setWidgetResizable(True)
        self.content_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.content_scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        self.content_scroll.setWidget(splitter)
        layout.addWidget(self.content_scroll, stretch=1)

        self.summary_panel = self._build_summary_panel()

        self.refresh()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        new_button = QPushButton("+ New Limit")
        new_button.clicked.connect(self._add_line)
        duplicate_button = QPushButton("Duplicate")
        duplicate_button.clicked.connect(self._duplicate_line)
        delete_button = QPushButton("Delete Limit")
        delete_button.clicked.connect(self._delete_line)
        for button in (new_button, duplicate_button, delete_button):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        return toolbar

    def _build_lines_table(self) -> QWidget:
        self.lines_model = PandasTableModel()
        self.lines_table = QTableView()
        self.lines_table.setModel(self.lines_model)
        self.lines_table.setAlternatingRowColors(True)
        self.lines_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.lines_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.lines_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.lines_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.lines_table.verticalHeader().setVisible(False)
        self.lines_table.selectionModel().selectionChanged.connect(self._on_line_selected)
        return self.lines_table

    def _build_editor(self) -> QWidget:
        editor = QFrame()
        editor.setObjectName("EatonPanel")
        editor.setMinimumHeight(360)
        outer = QVBoxLayout(editor)
        outer.setContentsMargins(12, 12, 12, 12)

        heading = QLabel("Selected Limit Definition")
        heading.setObjectName("PanelHeading")
        outer.addWidget(heading)

        form = QFormLayout()
        self.name_edit = QLineEdit()
        self.name_edit.editingFinished.connect(self._store_metadata)
        form.addRow("Name:", self.name_edit)

        self.type_combo = NoWheelComboBox()
        self.type_combo.addItems(self.vm.limit_types())
        self.type_combo.currentIndexChanged.connect(self._store_metadata)
        form.addRow("Type:", self.type_combo)

        self.applies_combo = NoWheelComboBox()
        self.applies_combo.addItem("All selected Y channels")
        self.applies_combo.currentIndexChanged.connect(self._store_metadata)
        form.addRow("Applies to:", self.applies_combo)

        colour_row = QWidget()
        colour_layout = QHBoxLayout(colour_row)
        colour_layout.setContentsMargins(0, 0, 0, 0)
        self.colour_combo = NoWheelComboBox()
        self.colour_combo.addItems(list(self.vm.colour_presets().keys()) + [_CUSTOM])
        self.colour_combo.activated.connect(self._on_colour_preset)
        self.colour_edit = QLineEdit()
        self.colour_edit.setFixedWidth(90)
        self.colour_edit.editingFinished.connect(self._on_colour_text)
        self.colour_swatch = QLabel()
        self.colour_swatch.setFixedWidth(28)
        self.colour_swatch.setFrameShape(QFrame.Shape.Box)
        pick_button = QPushButton("Pick…")
        pick_button.clicked.connect(self._pick_colour)
        colour_layout.addWidget(self.colour_combo, stretch=1)
        colour_layout.addWidget(self.colour_edit)
        colour_layout.addWidget(self.colour_swatch)
        colour_layout.addWidget(pick_button)
        form.addRow("Colour:", colour_row)
        outer.addLayout(form)

        outer.addWidget(self._build_points_group())
        outer.addStretch(1)
        return editor

    def _build_summary_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("EatonPanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(12, 12, 12, 12)

        header = QHBoxLayout()
        heading = QLabel("Margin-to-Limit Summary")
        heading.setObjectName("PanelHeading")
        refresh_button = QPushButton("Refresh Margins")
        refresh_button.setObjectName("PrimaryButton")
        refresh_button.clicked.connect(self.refresh_margins)
        header.addWidget(heading)
        header.addStretch(1)
        header.addWidget(refresh_button)
        layout.addLayout(header)

        hint = QLabel(
            "Define at least one limit line with two or more X/Y points, then generate a plot "
            "or click Refresh Margins to calculate margins for the current selection."
        )
        hint.setObjectName("PlaceholderText")
        hint.setWordWrap(True)
        layout.addWidget(hint)

        self.summary_model = MarginSummaryTableModel()
        self.summary_table = QTableView()
        self.summary_table.setModel(self.summary_model)
        self.summary_table.setAlternatingRowColors(True)
        self.summary_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.summary_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.summary_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.summary_table.verticalHeader().setVisible(False)
        self.summary_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.summary_table.horizontalHeader().setSectionResizeMode(
            MARGIN_TABLE_COLUMNS.index("Details"), QHeaderView.ResizeMode.Stretch
        )
        self.summary_table.setItemDelegateForColumn(
            MARGIN_TABLE_COLUMNS.index("Status"), MarginStatusDelegate(self.summary_table)
        )
        self.summary_table.setMinimumHeight(180)
        layout.addWidget(self.summary_table, stretch=1)
        self._set_margin_message(
            "Margin-to-limit results will appear here after a plot is generated or margins are refreshed."
        )
        return panel

    def _build_points_group(self) -> QWidget:
        group = QGroupBox("X vs Y Limit Points — minimum 2 points to plot / calculate margin")
        group_layout = QVBoxLayout(group)

        entry_row = QHBoxLayout()
        entry_row.addWidget(QLabel("X:"))
        self.point_x_edit = QLineEdit()
        self.point_x_edit.setFixedWidth(90)
        entry_row.addWidget(self.point_x_edit)
        entry_row.addWidget(QLabel("Y:"))
        self.point_y_edit = QLineEdit()
        self.point_y_edit.setFixedWidth(90)
        entry_row.addWidget(self.point_y_edit)
        add_button = QPushButton("Add Point")
        add_button.clicked.connect(self._add_point)
        update_button = QPushButton("Update Selected")
        update_button.clicked.connect(self._update_point)
        delete_button = QPushButton("Delete Selected")
        delete_button.clicked.connect(self._delete_point)
        for button in (add_button, update_button, delete_button):
            entry_row.addWidget(button)
        entry_row.addStretch(1)
        group_layout.addLayout(entry_row)

        self.points_model = PandasTableModel()
        self.points_table = QTableView()
        self.points_table.setModel(self.points_model)
        self.points_table.setAlternatingRowColors(True)
        self.points_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.points_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.points_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.points_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.points_table.verticalHeader().setVisible(False)
        self.points_table.setMinimumHeight(140)
        self.points_table.selectionModel().selectionChanged.connect(self._on_point_selected)
        group_layout.addWidget(self.points_table)
        return group

    # ------------------------------------------------------------------
    # Selection wiring
    # ------------------------------------------------------------------
    def set_selection_provider(self, provider: SelectionProvider) -> None:
        self._selection_provider = provider

    def _selected_y(self) -> list[str]:
        if self._selection_provider is None:
            return []
        return self._selection_provider()[1]

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self._refresh_applies_options()
        self._refresh_lines_table()
        self._load_active_into_form()
        self._refresh_points_table()

    def _refresh_applies_options(self) -> None:
        options = self.vm.applies_options(self._selected_y())
        current = self.applies_combo.currentText()
        self._loading = True
        self.applies_combo.clear()
        self.applies_combo.addItems(options)
        if current in options:
            self.applies_combo.setCurrentText(current)
        self._loading = False

    def _refresh_lines_table(self) -> None:
        self._loading = True
        self.lines_model.set_dataframe(self.vm.lines_table())
        index = self.vm.active_index()
        if index >= 0:
            self.lines_table.selectRow(index)
        self._loading = False

    def _refresh_points_table(self) -> None:
        self.points_model.set_dataframe(self.vm.active_points_table())

    def _load_active_into_form(self) -> None:
        line = self.vm.active_line()
        self._loading = True
        try:
            if line is None:
                self.name_edit.clear()
                self.type_combo.setCurrentText("Upper Limit")
                self.applies_combo.setCurrentText("All selected Y channels")
                self._set_colour("", update_combo=True)
                return
            self.name_edit.setText(line.get("name", "Limit"))
            self.type_combo.setCurrentText(line.get("type", "Upper Limit"))
            applies = line.get("applies_to", "All selected Y channels")
            if self.applies_combo.findText(applies) < 0:
                self.applies_combo.addItem(applies)
            self.applies_combo.setCurrentText(applies)
            self._set_colour(line.get("color", ""), update_combo=True)
        finally:
            self._loading = False

    # ------------------------------------------------------------------
    # Colour helpers
    # ------------------------------------------------------------------
    def _set_colour(self, colour: str, *, update_combo: bool) -> None:
        colour = (colour or "").strip()
        self.colour_edit.setText(colour)
        self.colour_swatch.setStyleSheet(
            f"background-color: {colour or '#FFFFFF'}; border: 1px solid #888888;"
        )
        if update_combo:
            preset = self.vm.preset_for_colour(colour) if colour else _CUSTOM
            self.colour_combo.setCurrentText(preset)

    def _on_colour_preset(self, _index: int) -> None:
        if self._loading:
            return
        preset = self.colour_combo.currentText()
        colour = self.vm.colour_for_preset(preset)
        if colour:
            self._set_colour(colour, update_combo=False)
            self._store_metadata()

    def _on_colour_text(self) -> None:
        if self._loading:
            return
        self._set_colour(self.colour_edit.text(), update_combo=True)
        self._store_metadata()

    def _pick_colour(self) -> None:
        line = self.vm.active_line()
        if line is None:
            return
        initial = self.colour_edit.text().strip() or "#005A8C"
        chosen = QColorDialog.getColor(parent=self)
        if chosen.isValid():
            self._set_colour(chosen.name(), update_combo=True)
            self._store_metadata()

    # ------------------------------------------------------------------
    # Metadata / line actions
    # ------------------------------------------------------------------
    def _store_metadata(self) -> None:
        if self._loading or self.vm.active_line() is None:
            return
        self.vm.update_active_metadata(
            name=self.name_edit.text(),
            limit_type=self.type_combo.currentText(),
            applies_to=self.applies_combo.currentText(),
            colour=self.colour_edit.text(),
        )
        self._refresh_lines_table()
        self.limitsChanged.emit()

    def _on_line_selected(self, *_args) -> None:
        if self._loading:
            return
        rows = self.lines_table.selectionModel().selectedRows()
        if not rows:
            return
        self.vm.select_line(rows[0].row())
        self._load_active_into_form()
        self._refresh_points_table()

    def _add_line(self) -> None:
        self.vm.add_line()
        self.refresh()
        self.limitsChanged.emit()

    def _duplicate_line(self) -> None:
        self.vm.duplicate_line()
        self.refresh()
        self.limitsChanged.emit()

    def _delete_line(self) -> None:
        if not self.vm.lines:
            qt_message_service.warning(self, "Limits", "Select a limit line to delete.")
            return
        if not qt_message_service.confirm(self, "Limits", "Delete the active limit line?"):
            return
        result = self.vm.delete_line()
        self.refresh()
        self.limitsChanged.emit()
        self.statusMessage.emit(result.message)

    # ------------------------------------------------------------------
    # Point actions
    # ------------------------------------------------------------------
    def _selected_point_index(self) -> int:
        rows = self.points_table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    def _add_point(self) -> None:
        result = self.vm.add_point(self.point_x_edit.text(), self.point_y_edit.text())
        if not result.ok:
            qt_message_service.error(self, "Limit Point", result.message)
            return
        self.point_x_edit.clear()
        self.point_y_edit.clear()
        self._after_points_changed()

    def _update_point(self) -> None:
        index = self._selected_point_index()
        if index < 0:
            qt_message_service.warning(self, "Limit Point", "Select a limit point to update.")
            return
        result = self.vm.update_point(index, self.point_x_edit.text(), self.point_y_edit.text())
        if not result.ok:
            qt_message_service.error(self, "Limit Point", result.message)
            return
        self._after_points_changed()

    def _delete_point(self) -> None:
        index = self._selected_point_index()
        if index < 0:
            qt_message_service.warning(self, "Limit Point", "Select a limit point to delete.")
            return
        if not qt_message_service.confirm(self, "Limit Point", "Delete the selected limit point?"):
            return
        result = self.vm.delete_point(index)
        if not result.ok:
            qt_message_service.warning(self, "Limit Point", result.message)
            return
        self._after_points_changed()

    def _after_points_changed(self) -> None:
        self._refresh_points_table()
        self._refresh_lines_table()
        self.limitsChanged.emit()

    def _on_point_selected(self, *_args) -> None:
        index = self._selected_point_index()
        points = self.vm.active_points()
        if 0 <= index < len(points):
            self.point_x_edit.setText(f"{points[index]['x']:.6g}")
            self.point_y_edit.setText(f"{points[index]['y']:.6g}")

    # ------------------------------------------------------------------
    # Margin summary
    # ------------------------------------------------------------------
    def refresh_margins(self) -> None:
        self._refresh_applies_options()
        if self._selection_provider is None:
            return
        x_col, selected_y, xmin, xmax = self._selection_provider()
        if not x_col or not selected_y:
            self._set_margin_message("Select X/Y data and generate a plot to calculate margin-to-limit.")
            return
        try:
            data = self.plot_vm.prepare_plot_data(x_col, selected_y, xmin, xmax)
        except ValueError as exc:
            self._set_margin_message(str(exc), status="SKIPPED")
            return
        self.summary_model.set_rows(self.vm.margin_table_rows(data, self.vm.lines))

    def _set_margin_message(self, message: str, *, status: str = "INFO") -> None:
        self.summary_model.set_rows(
            [
                {
                    "Limit": "",
                    "Channel": "",
                    "Status": status,
                    "Severity": status,
                    "Details": message,
                }
            ]
        )
