"""Runs / Comparison panel.

Manage multiple loaded runs (add, remove, duplicate, rename, set-active, toggle
enabled), configure the comparison options, view per-run comparison statistics,
and overlay the enabled runs on the shared plot canvas. The panel is a thin Qt
view; run CRUD, file loading, comparison-item preparation, and statistics all
run through the framework-independent :class:`RunsComparisonViewModel`.

The current axis selection (X column, Y channels, analysis window) is supplied by
an injected selection provider. Generating a comparison plot is delegated to the
main window via the :attr:`comparisonRequested` signal, which owns the canvas.
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
    QPushButton,
    QSplitter,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from ...viewmodels.runs_comparison_vm import RunsComparisonViewModel
from ..adapters import qt_file_dialogs, qt_message_service, qt_widget_helpers
from ..adapters.pandas_table_model import PandasTableModel

SelectionProvider = Callable[[], tuple[str, list[str], Optional[float], Optional[float]]]

class RunsComparisonPanel(QWidget):
    comparisonRequested = Signal()
    statusMessage = Signal(str)

    def __init__(self, view_model: RunsComparisonViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.vm = view_model
        self._selection_provider: Optional[SelectionProvider] = None

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addLayout(self._build_toolbar())
        layout.addLayout(self._build_options())

        splitter = QSplitter()
        splitter.addWidget(self._build_runs_table())
        splitter.addWidget(self._build_stats_table())
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)
        layout.addWidget(splitter, stretch=1)

        self.status_label = QLabel("Add one or more runs, then select channels and generate a comparison plot.")
        self.status_label.setObjectName("PlaceholderText")
        self.status_label.setWordWrap(True)
        layout.addWidget(self.status_label)

        self.refresh()

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_toolbar(self) -> QHBoxLayout:
        toolbar = QHBoxLayout()
        add_button = QPushButton("Add Run…")
        add_button.setObjectName("PrimaryButton")
        add_button.clicked.connect(self._add_run)
        remove_button = QPushButton("Remove Run")
        remove_button.clicked.connect(self._remove_run)
        duplicate_button = QPushButton("Duplicate Run")
        duplicate_button.clicked.connect(self._duplicate_run)
        rename_button = QPushButton("Rename Run")
        rename_button.clicked.connect(self._rename_run)
        active_button = QPushButton("Set Active")
        active_button.clicked.connect(self._set_active)
        toggle_button = QPushButton("Toggle Enabled")
        toggle_button.clicked.connect(self._toggle_enabled)
        plot_button = QPushButton("Generate Comparison Plot")
        plot_button.clicked.connect(self.comparisonRequested)
        for button in (add_button, remove_button, duplicate_button, rename_button, active_button, toggle_button, plot_button):
            toolbar.addWidget(button)
        toolbar.addStretch(1)
        return toolbar

    def _build_options(self) -> QHBoxLayout:
        options = QHBoxLayout()
        self.prefix_check = QCheckBox("Prefix legend labels with run name")
        self.prefix_check.setChecked(self.vm.get_setting("comparison_prefix_legend"))
        self.prefix_check.toggled.connect(
            lambda checked: self.vm.set_setting("comparison_prefix_legend", checked)
        )
        self.common_x_check = QCheckBox("Use common X range only")
        self.common_x_check.setChecked(self.vm.get_setting("comparison_common_x_range"))
        self.common_x_check.toggled.connect(
            lambda checked: self.vm.set_setting("comparison_common_x_range", checked)
        )
        options.addWidget(self.prefix_check)
        options.addWidget(self.common_x_check)
        options.addStretch(1)
        return options

    def _build_runs_table(self) -> QWidget:
        self.runs_model = PandasTableModel()
        self.runs_table = QTableView()
        self.runs_table.setModel(self.runs_model)
        self.runs_table.setAlternatingRowColors(True)
        self.runs_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.runs_table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.runs_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.runs_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.runs_table.verticalHeader().setVisible(False)
        self.runs_table.doubleClicked.connect(self._on_double_click)
        return self.runs_table

    def _build_stats_table(self) -> QWidget:
        self.stats_model = PandasTableModel()
        self.stats_table = QTableView()
        self.stats_table.setModel(self.stats_model)
        self.stats_table.setAlternatingRowColors(True)
        self.stats_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.stats_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self.stats_table.verticalHeader().setVisible(False)
        return self.stats_table

    # ------------------------------------------------------------------
    # Selection wiring
    # ------------------------------------------------------------------
    def set_selection_provider(self, provider: SelectionProvider) -> None:
        self._selection_provider = provider

    def _selection(self) -> tuple[str, list[str], Optional[float], Optional[float]]:
        if self._selection_provider is None:
            return "", [], None, None
        return self._selection_provider()

    def _selected_index(self) -> int:
        rows = self.runs_table.selectionModel().selectedRows()
        return rows[0].row() if rows else -1

    # ------------------------------------------------------------------
    # Population
    # ------------------------------------------------------------------
    def refresh(self) -> None:
        self.runs_model.set_dataframe(self.vm.run_table())
        self.update_statistics()

    def update_statistics(self) -> None:
        _x, selected_y, _xmin, _xmax = self._selection()
        self.stats_model.set_dataframe(self.vm.comparison_statistics_table(selected_y))

    # ------------------------------------------------------------------
    # Run CRUD actions
    # ------------------------------------------------------------------
    def _add_run(self) -> None:
        manager = getattr(getattr(self.vm, "state", None), "settings_manager", None)
        path = qt_file_dialogs.open_data_file(self, qt_widget_helpers.last_data_directory(manager))
        if not path:
            return
        qt_widget_helpers.remember_data_directory(manager, path)
        sheets = self.vm.get_sheets(path)
        sheet_name: Optional[str] = None
        if sheets:
            if len(sheets) == 1:
                sheet_name = sheets[0]
            else:
                chosen, ok = QInputDialog.getItem(self, "Select Excel Sheet", "Sheet:", sheets, 0, False)
                if not ok:
                    return
                sheet_name = chosen
        result = self.vm.add_run(path, sheet_name)
        if not result.ok:
            qt_message_service.error(self, "Add Run", result.message)
            return
        self.refresh()
        self.statusMessage.emit(result.message)

    def _remove_run(self) -> None:
        index = self._selected_index()
        if index < 0:
            qt_message_service.warning(self, "Runs / Comparison", "Select a run to remove.")
            return
        if not qt_message_service.confirm(self, "Remove Run", "Remove the selected run from this comparison?"):
            return
        result = self.vm.remove_run(index)
        self.refresh()
        self.statusMessage.emit(result.message)

    def _duplicate_run(self) -> None:
        index = self._selected_index()
        if index < 0:
            qt_message_service.warning(self, "Runs / Comparison", "Select a run to duplicate.")
            return
        result = self.vm.duplicate_run(index)
        self.refresh()
        self.statusMessage.emit(result.message)

    def _rename_run(self) -> None:
        index = self._selected_index()
        if index < 0:
            qt_message_service.warning(self, "Runs / Comparison", "Select a run to rename.")
            return
        current = self.vm.state.runs[index].get("name", "")
        new_name, ok = QInputDialog.getText(self, "Rename Run", "Run name:", text=str(current))
        if not ok:
            return
        result = self.vm.rename_run(index, new_name)
        if not result.ok:
            qt_message_service.warning(self, "Rename Run", result.message)
            return
        self.refresh()
        self.statusMessage.emit(result.message)

    def _set_active(self) -> None:
        index = self._selected_index()
        if index < 0:
            qt_message_service.warning(self, "Runs / Comparison", "Select a run to make active.")
            return
        result = self.vm.set_active(index)
        self.refresh()
        self.statusMessage.emit(result.message)

    def _toggle_enabled(self) -> None:
        index = self._selected_index()
        if index < 0:
            qt_message_service.warning(self, "Runs / Comparison", "Select a run to toggle.")
            return
        result = self.vm.toggle_enabled(index)
        self.refresh()
        self.statusMessage.emit(result.message)

    def _on_double_click(self, index) -> None:
        if index.isValid():
            self._toggle_via_index(index.row())

    def _toggle_via_index(self, index: int) -> None:
        self.vm.toggle_enabled(index)
        self.refresh()

    def set_status(self, message: str) -> None:
        self.status_label.setText(message)
