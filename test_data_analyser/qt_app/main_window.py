"""PySide6 main window.

Wires together the framework-independent viewmodels and the migrated Qt panels:
the data-file panel, axis/channel selection, the Matplotlib plot workspace, and
the statistics table. Remaining panels (raw data, maths channels, limits,
engineering notes, runs/comparison, cursor compare, session) are migrated in
subsequent Phase 5 increments and currently show placeholders.

PySide6 is imported only within ``qt_app``; all analysis logic stays in the
domain/services/viewmodels layers.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSplitter,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.config import __version__
from ..core.settings_manager import SettingsManager
from ..viewmodels import MainWindowViewModel
from . import theme
from .adapters import qt_file_dialogs, qt_message_service
from .widgets.axis_selection_panel import AxisSelectionPanel
from .widgets.cursor_compare_panel import CursorComparePanel
from .widgets.data_file_panel import DataFilePanel
from .widgets.engineering_notes_panel import EngineeringNotesPanel
from .widgets.limits_panel import LimitsPanel
from .widgets.maths_channels_panel import MathsChannelsPanel
from .widgets.plot_workspace import PlotWorkspace
from .widgets.raw_data_panel import RawDataPanel
from .widgets.runs_comparison_panel import RunsComparisonPanel
from .widgets.settings_dialog import SettingsDialog
from .widgets.statistics_panel import StatisticsPanel


class MainWindow(QMainWindow):
    def __init__(self, settings_manager: SettingsManager | None = None) -> None:
        super().__init__()
        self.settings_manager = settings_manager or SettingsManager()
        self.vm = MainWindowViewModel(self.settings_manager)

        self.setWindowTitle("Test Data Analyser — Eaton Edition")
        self.resize(1320, 840)

        self._build_menu()
        self._build_central_layout()
        self._apply_theme()

        self.statusBar().showMessage("Ready. Open a data file to begin.")

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_menu(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        open_action = file_menu.addAction("&Open Data File…")
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._open_via_panel)
        file_menu.addSeparator()
        save_session_action = file_menu.addAction("&Save Session…")
        save_session_action.setShortcut("Ctrl+S")
        save_session_action.triggered.connect(self.save_session)
        load_session_action = file_menu.addAction("&Load Session…")
        load_session_action.setShortcut("Ctrl+L")
        load_session_action.triggered.connect(self.load_session)
        file_menu.addSeparator()
        exit_action = file_menu.addAction("E&xit")
        exit_action.triggered.connect(self.close)

        edit_menu = self.menuBar().addMenu("&Edit")
        settings_action = edit_menu.addAction("&Settings…")
        settings_action.triggered.connect(self.open_settings)

    def _build_central_layout(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        self.data_panel = DataFilePanel(self.vm.data_loading)
        self.axis_panel = AxisSelectionPanel()
        self.plot_workspace = PlotWorkspace(self.vm.plot_workspace, self.vm.settings)
        self.statistics_panel = StatisticsPanel()
        self.raw_data_panel = RawDataPanel(self.vm.raw_data)
        self.raw_data_panel.set_selection_provider(self._current_axis_selection)
        self.maths_panel = MathsChannelsPanel(self.vm.maths_channels)
        self.limits_panel = LimitsPanel(self.vm.limits, self.vm.plot_workspace)
        self.limits_panel.set_selection_provider(self._current_axis_selection)
        self.notes_panel = EngineeringNotesPanel(self.vm.engineering_notes)
        self.notes_panel.set_context_provider(self._notes_context)
        self.runs_panel = RunsComparisonPanel(self.vm.runs_comparison)
        self.runs_panel.set_selection_provider(self._current_axis_selection)
        self.plot_workspace.set_cursor_viewmodel(self.vm.cursor_compare)
        self.cursor_panel = CursorComparePanel(self.vm.cursor_compare, self.plot_workspace)
        self.cursor_panel.analysisWindowRequested.connect(self._on_cursor_window)

        self.data_panel.fileLoaded.connect(self._on_file_loaded)
        self.data_panel.statusMessage.connect(self.statusBar().showMessage)
        self.axis_panel.generateRequested.connect(self._on_generate_plot)
        self.axis_panel.fftRequested.connect(self._on_generate_fft)
        self.maths_panel.channelsChanged.connect(self._on_channels_changed)
        self.maths_panel.statusMessage.connect(self.statusBar().showMessage)
        self.limits_panel.limitsChanged.connect(self._on_limits_changed)
        self.limits_panel.statusMessage.connect(self.statusBar().showMessage)
        self.runs_panel.comparisonRequested.connect(self._on_generate_comparison)
        self.runs_panel.statusMessage.connect(self.statusBar().showMessage)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.addWidget(self.data_panel)
        left_layout.addWidget(self.axis_panel, stretch=1)

        right_splitter = QSplitter(Qt.Vertical)
        right_splitter.addWidget(self.plot_workspace)
        right_splitter.addWidget(self._build_lower_tabs())
        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 2)

        body_splitter = QSplitter(Qt.Horizontal)
        body_splitter.addWidget(left)
        body_splitter.addWidget(right_splitter)
        body_splitter.setStretchFactor(0, 1)
        body_splitter.setStretchFactor(1, 4)

        root.addWidget(body_splitter, stretch=1)
        self.setCentralWidget(central)

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("EatonHeader")
        header.setFixedHeight(64)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 8, 20, 8)

        title_box = QVBoxLayout()
        title_box.setSpacing(0)
        title = QLabel("Test Data Analyser")
        title.setObjectName("EatonHeaderTitle")
        subtitle = QLabel(f"Eaton Edition — PySide6 shell (v{__version__})")
        subtitle.setObjectName("EatonHeaderSubtitle")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        layout.addLayout(title_box)
        layout.addStretch(1)
        return header

    def _build_lower_tabs(self) -> QWidget:
        self.lower_tabs = QTabWidget()
        self.lower_tabs.addTab(self.statistics_panel, "Statistics")
        self.lower_tabs.addTab(self.raw_data_panel, "Raw Data")
        self.lower_tabs.addTab(self.maths_panel, "Maths Channels")
        self.lower_tabs.addTab(self.limits_panel, "Requirements / Limits")
        self.lower_tabs.addTab(self.notes_panel, "Engineering Notes")
        self.lower_tabs.addTab(self.runs_panel, "Runs / Comparison")
        self.lower_tabs.addTab(self.cursor_panel, "Point Compare")
        return self.lower_tabs

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------
    def _apply_theme(self) -> None:
        self.setStyleSheet(theme.build_stylesheet(self.vm.settings.theme_name()))

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _open_via_panel(self) -> None:
        self.data_panel.open_file()

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.vm.settings, self)
        if dialog.exec():
            self._apply_theme()
            self.statusBar().showMessage("Settings saved.")

    def save_session(self) -> None:
        path = qt_file_dialogs.save_session_file(self)
        if not path:
            return
        self.vm.capture_working_state(
            x_column=self.axis_panel.x_column(),
            y_columns=self.axis_panel.selected_y(),
            secondary_y_columns=self.axis_panel.selected_secondary_y(),
        )
        result = self.vm.save_session(path)
        qt_message_service.show_result(self, "Save Session", result)
        self.statusBar().showMessage(result.message)

    def load_session(self) -> None:
        path = qt_file_dialogs.open_session_file(self)
        if not path:
            return
        result = self.vm.restore_session(path)
        if not result.ok:
            qt_message_service.error(self, "Load Session", result.message)
            self.statusBar().showMessage(result.message)
            return
        self._apply_loaded_session(result.payload or {})
        if result.warnings:
            qt_message_service.warning(self, "Load Session", "\n".join(result.warnings))
        self.statusBar().showMessage(result.message)

    def _apply_loaded_session(self, selection: dict) -> None:
        columns = self.vm.state.column_names()
        self.axis_panel.apply_selection(
            columns,
            selection.get("x_column", ""),
            selection.get("y_columns", []),
            selection.get("secondary_y_columns", []),
        )
        self.statistics_panel.set_statistics(self.vm.plot_workspace.statistics([]))
        self.raw_data_panel.clear()
        self.maths_panel.clear_form()
        self.maths_panel.refresh()
        self.limits_panel.refresh()
        self.notes_panel.load_from_state()
        self.runs_panel.refresh()
        self.plot_workspace.clear_cursor_markers()
        self.cursor_panel.refresh()

    def _on_file_loaded(self, columns: list[str]) -> None:
        suggested_x = self.vm.data_loading.suggested_x_column(columns)
        self.axis_panel.set_columns(columns, suggested_x)
        self.statistics_panel.set_statistics(self.vm.plot_workspace.statistics([]))
        self.raw_data_panel.clear()
        self.maths_panel.clear_form()
        self.maths_panel.refresh()
        self.limits_panel.refresh()
        self.notes_panel.load_from_state()
        self.runs_panel.refresh()
        self.statusBar().showMessage(f"Loaded {len(columns)} columns. Select channels and generate a plot.")

    def _on_generate_plot(self) -> None:
        result = self._generate_plot()
        if result is None:
            return
        if not result.ok:
            qt_message_service.warning(self, "Plot", result.message)
            self.statusBar().showMessage(result.message)
            return
        self._update_statistics(self.axis_panel.all_selected_y())
        self.raw_data_panel.refresh()
        self.limits_panel.refresh_margins()
        self.runs_panel.update_statistics()
        self.statusBar().showMessage(result.message)

    def _notes_context(self) -> tuple[str, str, str]:
        file_name = self.vm.state.filepath.name if self.vm.state.filepath else ""
        return file_name, self.axis_panel.x_column(), ", ".join(self.axis_panel.all_selected_y())

    def _on_generate_comparison(self) -> None:
        x_col = self.axis_panel.x_column()
        y_cols = self.axis_panel.selected_y()
        if not x_col or not y_cols:
            qt_message_service.warning(self, "Comparison Plot", "Select an X column and at least one Y channel.")
            return
        xmin, xmax = self.axis_panel.analysis_window()
        items, skipped = self.vm.runs_comparison.comparison_plot_items(
            x_col,
            y_cols,
            use_common_x=self.vm.runs_comparison.get_setting("comparison_common_x_range"),
            xmin=xmin,
            xmax=xmax,
            prefix_legend=self.vm.runs_comparison.get_setting("comparison_prefix_legend"),
        )
        result = self.plot_workspace.generate_comparison_plot(
            items, x_col, limit_lines=self._overlay_limit_lines()
        )
        if not result.ok:
            qt_message_service.warning(self, "Comparison Plot", result.message)
            self.statusBar().showMessage(result.message)
            return
        self.runs_panel.update_statistics()
        message = result.message
        if skipped:
            message += f" Skipped {len(skipped)} missing/non-numeric channel(s)."
        self.runs_panel.set_status(message)
        self.statusBar().showMessage(message)

    def _generate_plot(self):
        """Render the current axis selection onto the canvas (shared by plot/limit refresh).

        Returns the ``OperationResult`` or ``None`` when there is nothing selected.
        """
        x_col = self.axis_panel.x_column()
        y_cols = self.axis_panel.all_selected_y()
        if not x_col or not y_cols:
            return None
        xmin, xmax = self.axis_panel.analysis_window()
        use_filter, cutoff, order = self.axis_panel.filter_settings()
        return self.plot_workspace.generate_plot(
            x_col,
            y_cols,
            xmin,
            xmax,
            limit_lines=self._overlay_limit_lines(),
            secondary_y=self.axis_panel.selected_secondary_y(),
            plot_kind=self.axis_panel.plot_kind(),
            use_filter=use_filter,
            cutoff=cutoff,
            order=order,
        )

    def _overlay_limit_lines(self) -> list[dict]:
        return self.vm.limits.normalise(self.vm.state.limit_lines)

    def _current_axis_selection(self) -> tuple[str, list[str], Optional[float], Optional[float]]:
        xmin, xmax = self.axis_panel.analysis_window()
        return self.axis_panel.x_column(), self.axis_panel.all_selected_y(), xmin, xmax

    def _on_channels_changed(self) -> None:
        columns = self.vm.maths_channels.state.column_names()
        if columns:
            self.axis_panel.update_columns(columns)
        self.raw_data_panel.refresh()

    def _on_cursor_window(self, xmin: float, xmax: float) -> None:
        self.axis_panel.xmin_edit.setText(f"{xmin:g}")
        self.axis_panel.xmax_edit.setText(f"{xmax:g}")
        result = self._generate_plot()
        if result is not None and result.ok:
            self.statusBar().showMessage(
                f"Analysis window set from locked points: {xmin:g} to {xmax:g}."
            )

    def _on_limits_changed(self) -> None:
        self._generate_plot()

    def _on_generate_fft(self) -> None:
        x_col = self.axis_panel.x_column()
        y_cols = self.axis_panel.selected_y()
        result = self.plot_workspace.generate_fft(x_col, y_cols)
        if not result.ok:
            qt_message_service.warning(self, "FFT", result.message)
        self.statusBar().showMessage(result.message)

    def _update_statistics(self, y_cols: list[str]) -> None:
        decimals = int(self.vm.settings.get("axis_scaling", "decimal_places_statistics", 4) or 4)
        stats = self.vm.plot_workspace.statistics(y_cols, decimals)
        self.statistics_panel.set_statistics(stats)
