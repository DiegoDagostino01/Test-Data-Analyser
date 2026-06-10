"""PySide6 main window.

Wires together the framework-independent viewmodels and the Qt panels for the
full analysis workflow: data loading, plotting, raw data, maths channels,
limits, engineering notes, run comparison, cursor comparison, and sessions.
PySide6 is imported only within ``qt_app``; analysis logic stays in the
domain/services/viewmodels layers.
"""
from __future__ import annotations

import base64
from collections.abc import Callable
from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from ..core.config import __version__, EATON_LOGO_PNG_BASE64
from ..core.settings_manager import SettingsManager
from ..viewmodels import MainWindowViewModel
from . import theme
from .adapters import qt_file_dialogs, qt_message_service, qt_widget_helpers
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
    LOWER_PLOT_INDEX = 0
    LOWER_ANALYSIS_INDEX = 1
    LOWER_REQUIREMENTS_INDEX = 2
    LOWER_NOTES_INDEX = 3
    LEFT_RAIL_INITIAL_WIDTH = 300
    LEFT_RAIL_MINIMUM_WIDTH = 280

    def __init__(self, settings_manager: SettingsManager | None = None) -> None:
        super().__init__()
        self.settings_manager = settings_manager or SettingsManager()
        self.vm = MainWindowViewModel(self.settings_manager)
        self._plot_generated = False

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

        view_menu = self.menuBar().addMenu("&View")
        self.show_ribbon_action = view_menu.addAction("Show Ribbon")
        self.show_ribbon_action.setCheckable(True)
        self.show_ribbon_action.setChecked(True)
        self.show_ribbon_action.toggled.connect(self._set_ribbon_visible)

        help_menu = self.menuBar().addMenu("&Help")
        workflow_action = help_menu.addAction("&Workflow Help")
        workflow_action.triggered.connect(self.show_workflow_help)
        about_action = help_menu.addAction("&About Test Data Analyser")
        about_action.triggered.connect(self.show_about)

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
        self.maths_panel.channelsChanged.connect(self._on_channels_changed)
        self.maths_panel.statusMessage.connect(self.statusBar().showMessage)
        self.limits_panel.limitsChanged.connect(self._on_limits_changed)
        self.limits_panel.statusMessage.connect(self.statusBar().showMessage)
        self.runs_panel.comparisonRequested.connect(self._on_generate_comparison)
        self.runs_panel.statusMessage.connect(self.statusBar().showMessage)

        root.addWidget(self._build_ribbon())
        root.addWidget(self._build_collapsed_ribbon_bar())

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(8, 8, 8, 8)
        left_layout.addWidget(self.data_panel)
        left_layout.addWidget(self.axis_panel, stretch=1)
        left.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        left_scroll = QScrollArea()
        left_scroll.setWidgetResizable(True)
        left_scroll.setFrameShape(QFrame.Shape.NoFrame)
        left_scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        left_scroll.setWidget(left)
        left_scroll.setMinimumWidth(self.LEFT_RAIL_MINIMUM_WIDTH)
        left_scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.left_scroll = left_scroll

        # Plot above, analysis notebook below. The lower tabs are attached to
        # their content while the splitter handles plot/data resizing.
        self.plot_workspace.setMinimumHeight(260)
        lower_panel = self._build_lower_groups()
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.setChildrenCollapsible(True)
        right_splitter.addWidget(self.plot_workspace)
        right_splitter.addWidget(lower_panel)
        right_splitter.setCollapsible(0, True)
        right_splitter.setCollapsible(1, True)
        right_splitter.setStretchFactor(0, 3)
        right_splitter.setStretchFactor(1, 2)
        right_splitter.setSizes([520, 260])
        self.right_splitter = right_splitter

        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(8, 8, 8, 8)
        right_layout.setSpacing(6)
        right_layout.addWidget(right_splitter, stretch=1)
        self.right_panel = right

        body_splitter = QSplitter(Qt.Orientation.Horizontal)
        body_splitter.addWidget(left_scroll)
        body_splitter.addWidget(right)
        body_splitter.setStretchFactor(0, 1)
        body_splitter.setStretchFactor(1, 4)
        body_splitter.setChildrenCollapsible(False)
        self.body_splitter = body_splitter

        root.addWidget(body_splitter, stretch=1)
        self.setCentralWidget(central)
        body_splitter.setSizes([self.LEFT_RAIL_INITIAL_WIDTH, 1020])
        self.lower_stack.setCurrentIndex(self.LOWER_PLOT_INDEX)

    def _build_header(self) -> QFrame:
        header = QFrame()
        header.setObjectName("EatonHeader")
        header.setFixedHeight(58)
        layout = QHBoxLayout(header)
        layout.setContentsMargins(20, 6, 20, 6)
        layout.setSpacing(14)

        logo = self._build_logo_label()
        if logo is not None:
            layout.addWidget(logo, 0, Qt.AlignmentFlag.AlignVCenter)

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

    def _build_ribbon(self) -> QFrame:
        ribbon = QFrame()
        ribbon.setObjectName("RibbonBar")
        ribbon.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.ribbon = ribbon
        layout = QHBoxLayout(ribbon)
        layout.setContentsMargins(12, 5, 12, 5)
        layout.setSpacing(8)

        self.ribbon_buttons: dict[str, QPushButton] = {}
        for title, commands in self._ribbon_commands():
            layout.addWidget(self._build_ribbon_group(title, commands))
        layout.addStretch(1)
        self.hide_ribbon_button = QPushButton("Hide Ribbon")
        self.hide_ribbon_button.setObjectName("RibbonButton")
        self.hide_ribbon_button.setFixedHeight(23)
        self.hide_ribbon_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.hide_ribbon_button.setToolTip("Hide the ribbon to give more space to the plot and lower panels.")
        self.hide_ribbon_button.clicked.connect(lambda: self.show_ribbon_action.setChecked(False))
        layout.addWidget(self.hide_ribbon_button, 0, Qt.AlignmentFlag.AlignTop)
        return ribbon

    def _build_collapsed_ribbon_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("CollapsedRibbonBar")
        bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.collapsed_ribbon_bar = bar

        layout = QHBoxLayout(bar)
        layout.setContentsMargins(12, 3, 12, 3)
        layout.setSpacing(6)
        self.show_ribbon_button = QPushButton("Show Ribbon")
        self.show_ribbon_button.setObjectName("RibbonButton")
        self.show_ribbon_button.setFixedHeight(23)
        self.show_ribbon_button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.show_ribbon_button.clicked.connect(lambda: self.show_ribbon_action.setChecked(True))
        layout.addStretch(1)
        layout.addWidget(self.show_ribbon_button, 0, Qt.AlignmentFlag.AlignRight)
        bar.setVisible(False)
        return bar

    def _ribbon_commands(self) -> list[tuple[str, list[tuple[str, Callable[[], None]]]]]:
        return [
            (
                "FILE",
                [
                    ("Open Data", self._open_via_panel),
                    ("Save Session", self.save_session),
                    ("Load Session", self.load_session),
                    ("Export Data", self._export_selected_data),
                ],
            ),
            (
                "PLOT",
                [
                    ("Generate Plot", self._on_generate_plot),
                    ("FFT", self._on_generate_fft),
                    ("Save Plot", self._save_plot_png),
                    ("Clear Plot", self._clear_plot),
                    ("Runs / Comparison", lambda: self._show_plot_page(0)),
                ],
            ),
            (
                "ANALYSIS",
                [
                    ("Statistics", lambda: self._show_analysis_page(0)),
                    ("Raw Data", lambda: self._show_analysis_page(1)),
                    ("Maths Channels", lambda: self._show_analysis_page(2)),
                    ("Cursor", lambda: self._show_plot_page(1)),
                ],
            ),
            (
                "REQUIREMENTS",
                [
                    ("Limits", lambda: self._show_requirements_page(0)),
                    ("Margins", lambda: self._show_requirements_page(1)),
                    ("Refresh", self._refresh_requirements),
                ],
            ),
            (
                "NOTES",
                [
                    ("Engineering Notes", lambda: self._show_lower_page(self.LOWER_NOTES_INDEX)),
                    ("Refresh Report Text", self._refresh_engineering_notes),
                    ("Clear Notes", self._clear_engineering_notes),
                    ("Copy Notes", self._copy_engineering_notes),
                ],
            ),
        ]

    def _build_ribbon_group(
        self,
        title: str,
        commands: list[tuple[str, Callable[[], None]]],
    ) -> QFrame:
        group = QFrame()
        group.setObjectName("RibbonGroup")
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(6, 3, 6, 4)
        group_layout.setSpacing(3)

        label = QLabel(title)
        label.setObjectName("RibbonGroupLabel")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        group_layout.addWidget(label)

        button_grid = QGridLayout()
        button_grid.setContentsMargins(0, 0, 0, 0)
        button_grid.setHorizontalSpacing(4)
        button_grid.setVerticalSpacing(3)
        column_count = 3 if len(commands) > 4 else 2
        for index, (text, handler) in enumerate(commands):
            button = QPushButton(text)
            button.setObjectName("RibbonButton")
            button.setFixedHeight(23)
            button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            button.clicked.connect(handler)
            self.ribbon_buttons[f"{title}:{text}"] = button
            button_grid.addWidget(button, index // column_count, index % column_count)
        group_layout.addLayout(button_grid)
        return group

    def _build_logo_label(self) -> Optional[QLabel]:
        """Build the Eaton branding logo, or ``None`` if it cannot be decoded.

        The logo is decoded from the ``EATON_LOGO_PNG_BASE64`` constant in
        ``core.config`` here in the Qt layer (the only place allowed to use
        ``QPixmap``). On any failure the header falls back to the text title.
        """
        try:
            raw = base64.b64decode(EATON_LOGO_PNG_BASE64)
            pixmap = QPixmap()
            if not pixmap.loadFromData(raw):
                return None
            label = QLabel()
            label.setPixmap(pixmap.scaledToHeight(38, Qt.TransformationMode.SmoothTransformation))
            label.setFixedHeight(44)
            label.setObjectName("EatonHeaderLogo")
            return label
        except Exception:
            return None

    def _build_lower_groups(self) -> QWidget:
        """Build the grouped lower panel controlled by the ribbon commands."""
        self.lower_stack = QStackedWidget()
        self.lower_stack.setObjectName("AnalysisStack")
        self.lower_stack.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)

        self.plot_group = self._build_plot_group()
        self.analysis_stack = self._build_panel_stack(
            [
                self.statistics_panel,
                self.raw_data_panel,
                self.maths_panel,
            ]
        )
        self.requirements_stack = self._build_panel_stack(
            [
                self.limits_panel,
                self.limits_panel.summary_panel,
            ]
        )

        self.lower_stack.addWidget(self.plot_group)
        self.lower_stack.addWidget(self.analysis_stack)
        self.lower_stack.addWidget(self.requirements_stack)
        self.lower_stack.addWidget(self.notes_panel)
        self.lower_stack.setMinimumHeight(150)

        container = QFrame()
        container.setObjectName("EatonPanel")
        container.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        container_layout = QVBoxLayout(container)
        container_layout.setContentsMargins(8, 8, 8, 8)
        container_layout.addWidget(self.lower_stack)
        container.setMinimumHeight(170)
        return container

    @staticmethod
    def _build_panel_stack(panels: list[QWidget]) -> QStackedWidget:
        stack = QStackedWidget()
        stack.setObjectName("RibbonPanelStack")
        stack.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Expanding)
        for widget in panels:
            stack.addWidget(widget)
        return stack

    def _build_plot_group(self) -> QStackedWidget:
        return self._build_panel_stack([self.runs_panel, self.cursor_panel])

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

    def _set_ribbon_visible(self, visible: bool) -> None:
        if hasattr(self, "ribbon"):
            self.ribbon.setVisible(visible)
        if hasattr(self, "collapsed_ribbon_bar"):
            self.collapsed_ribbon_bar.setVisible(not visible)
        self.statusBar().showMessage("Ribbon shown." if visible else "Ribbon hidden.")

    def _show_lower_page(self, index: int) -> None:
        self.lower_stack.setCurrentIndex(index)

    def _show_plot_page(self, index: int) -> None:
        self._show_lower_page(self.LOWER_PLOT_INDEX)
        self.plot_group.setCurrentIndex(index)

    def _show_analysis_page(self, index: int) -> None:
        self._show_lower_page(self.LOWER_ANALYSIS_INDEX)
        self.analysis_stack.setCurrentIndex(index)

    def _show_requirements_page(self, index: int) -> None:
        self._show_lower_page(self.LOWER_REQUIREMENTS_INDEX)
        self.requirements_stack.setCurrentIndex(index)

    def _export_selected_data(self) -> None:
        self._show_analysis_page(1)
        self.raw_data_panel.export_selected_data()

    def _refresh_requirements(self) -> None:
        self._show_requirements_page(1)
        self.limits_panel.refresh()
        self.limits_panel.refresh_margins()
        self._generate_plot()
        self.statusBar().showMessage("Requirements and margin summary refreshed.")

    def _refresh_engineering_notes(self) -> None:
        self._show_lower_page(self.LOWER_NOTES_INDEX)
        self.notes_panel.refresh_report()
        self.statusBar().showMessage("Engineering notes report text refreshed.")

    def _clear_engineering_notes(self) -> None:
        self._show_lower_page(self.LOWER_NOTES_INDEX)
        if self.notes_panel.clear_notes():
            self.statusBar().showMessage("Engineering notes cleared.")

    def _copy_engineering_notes(self) -> None:
        self._show_lower_page(self.LOWER_NOTES_INDEX)
        self.notes_panel.refresh_report()
        text = self.notes_panel.report_text.toPlainText()
        QGuiApplication.clipboard().setText(text)
        self.statusBar().showMessage("Engineering notes copied to the clipboard.")

    def _clear_plot(self) -> None:
        result = self.plot_workspace.clear_plot()
        self._plot_generated = False
        self.cursor_panel.refresh()
        self.statusBar().showMessage(result.message)

    def open_settings(self) -> None:
        dialog = SettingsDialog(self.vm.settings, self)
        if dialog.exec():
            self._apply_theme()
            self.statusBar().showMessage("Settings saved.")

    def show_workflow_help(self) -> None:
        qt_message_service.info(
            self,
            "Workflow Help",
            "Open a CSV or Excel file, select X/Y channels, then generate plots, statistics, "
            "raw-data views, maths channels, limits, notes, comparisons, and sessions from the panels.",
        )

    def show_about(self) -> None:
        qt_message_service.info(
            self,
            "About Test Data Analyser",
            f"Test Data Analyser\nEaton Edition\nVersion {__version__}\n\n"
            "PySide6 desktop application for engineering test data analysis.",
        )

    def save_session(self) -> None:
        initial_dir = qt_widget_helpers.save_session_initial_directory(
            self.settings_manager,
            self.vm.state.filepath,
        )
        path = qt_file_dialogs.save_session_file(self, initial_dir)
        if not path:
            return
        qt_widget_helpers.remember_session_directory(self.settings_manager, path)
        appearance = self.plot_workspace.current_axis_appearance() if self._plot_generated else {}
        self.vm.capture_working_state(
            x_column=self.axis_panel.x_column(),
            y_columns=self.axis_panel.selected_y(),
            secondary_y_columns=self.axis_panel.selected_secondary_y(),
            plot_kind=self.axis_panel.plot_kind(),
            legend_settings={"display_mode": self.plot_workspace.legend_display()},
            analysis_window=self.axis_panel.analysis_window_texts(),
            filter_settings=self.axis_panel.filter_setting_texts(),
            title=appearance.get("title", ""),
            x_label=appearance.get("x_label", ""),
            y_label=appearance.get("y_label", ""),
            secondary_y_label=appearance.get("secondary_y_label", ""),
            axis_limits=appearance.get("axis_limits", {}),
            auto_fit_axes=appearance.get("auto_fit_axes", True),
            generated=self._plot_generated,
        )
        result = self.vm.save_session(path)
        qt_message_service.show_result(self, "Save Session", result)
        self.statusBar().showMessage(result.message)

    def load_session(self) -> None:
        initial_dir = qt_widget_helpers.last_session_directory(self.settings_manager)
        path = qt_file_dialogs.open_session_file(self, initial_dir)
        if not path:
            return
        qt_widget_helpers.remember_session_directory(self.settings_manager, path)
        result = self.vm.restore_session(path)
        if not result.ok:
            qt_message_service.error(self, "Load Session", result.message)
            self.statusBar().showMessage(result.message)
            return
        selection = result.payload if isinstance(result.payload, dict) else {}
        self._apply_loaded_session(selection)
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
        profile = self.vm.state.active_plot_profile() or {}
        self.axis_panel.apply_plot_settings(profile)
        legend_settings = profile.get("legend", {}) if isinstance(profile, dict) else {}
        display_mode = legend_settings.get("display_mode", "panel") if isinstance(legend_settings, dict) else "panel"
        self.plot_workspace.set_legend_display(str(display_mode))
        self.statistics_panel.set_statistics(self.vm.plot_workspace.statistics([]))
        self.raw_data_panel.clear()
        self.maths_panel.clear_form()
        self.maths_panel.refresh()
        self.limits_panel.refresh()
        self.notes_panel.load_from_state()
        self.runs_panel.refresh()
        self.plot_workspace.clear_cursor_markers()
        self.cursor_panel.refresh()
        self._restore_generated_plot(profile)

    def _restore_generated_plot(self, profile: dict) -> None:
        """Re-render the plot that was on screen when the session was saved.

        Only regenerates when the saved profile was flagged as generated and the
        restored axis selection is plottable, so loading a session that was never
        plotted leaves a clean canvas. The saved Figure Options appearance (title,
        axis labels, and axis limits) is re-applied so the plot looks identical.
        """
        self._plot_generated = False
        if not (isinstance(profile, dict) and profile.get("generated")):
            return
        appearance = {
            "title": profile.get("title", ""),
            "x_label": profile.get("x_label", ""),
            "y_label": profile.get("y_label", ""),
            "secondary_y_label": profile.get("secondary_y_label", ""),
            "axis_limits": profile.get("axis_limits", {}),
            "auto_fit_axes": profile.get("auto_fit_axes", True),
        }
        result = self._generate_plot(appearance)
        if result is None or not result.ok:
            return
        self._plot_generated = True
        self._update_statistics(self.axis_panel.all_selected_y())
        self.raw_data_panel.refresh()
        self.limits_panel.refresh_margins()
        self.runs_panel.update_statistics()

    def _on_file_loaded(self, columns: list[str]) -> None:
        suggested_x = self.vm.data_loading.suggested_x_column(columns)
        self._plot_generated = False
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
        self._plot_generated = True
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

    def _generate_plot(self, appearance: dict | None = None):
        """Render the current axis selection onto the canvas (shared by plot/limit refresh).

        Returns the ``OperationResult`` or ``None`` when there is nothing selected.
        ``appearance`` supplies saved Figure Options title/labels/limits on restore.
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
            **self._appearance_kwargs(appearance),
        )

    @staticmethod
    def _appearance_kwargs(appearance: dict | None) -> dict:
        """Translate a saved appearance dict into ``generate_plot`` keyword args."""
        if not appearance:
            return {}
        raw_limits = appearance.get("axis_limits") or {}
        axis_limits = {key: MainWindow._parse_limit(value) for key, value in raw_limits.items()}
        return {
            "title": str(appearance.get("title", "")),
            "x_label": str(appearance.get("x_label", "")),
            "y_label": str(appearance.get("y_label", "")),
            "secondary_y_label": str(appearance.get("secondary_y_label", "")),
            "axis_limits": axis_limits,
            "auto_fit_axes": bool(appearance.get("auto_fit_axes", True)),
        }

    @staticmethod
    def _parse_limit(value) -> Optional[float]:
        text = str(value).strip()
        if not text:
            return None
        try:
            return float(text)
        except ValueError:
            return None

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

    def _save_plot_png(self) -> None:
        path = qt_file_dialogs.save_image_file(self)
        if not path:
            return
        result = self.plot_workspace.save_plot_png(path)
        if not result.ok:
            qt_message_service.warning(self, "Save Plot", result.message)
            self.statusBar().showMessage(result.message)
            return
        self.statusBar().showMessage(result.message)

    def _update_statistics(self, y_cols: list[str]) -> None:
        decimals = int(self.vm.settings.get("axis_scaling", "decimal_places_statistics", 4) or 4)
        stats = self.vm.plot_workspace.statistics(y_cols, decimals)
        self.statistics_panel.set_statistics(stats)
