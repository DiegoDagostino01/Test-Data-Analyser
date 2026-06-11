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
from pathlib import Path
from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSplitter,
    QStackedWidget,
    QTabBar,
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
from .widgets.help_dialog import HelpDialog
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
    LEFT_RAIL_MAXIMUM_WIDTH = 380

    def __init__(self, settings_manager: SettingsManager | None = None) -> None:
        super().__init__()
        self.settings_manager = settings_manager or SettingsManager()
        self.vm = MainWindowViewModel(self.settings_manager)
        self.vm.ensure_plot_profiles()
        self._plot_generated = False
        self._syncing_plot_tabs = False
        self._active_plot_tab_index = self.vm.state.active_plot_profile_index
        self._current_session_path: str | None = None
        self._help_dialog: HelpDialog | None = None

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
        settings_action = self.menuBar().addAction("&Settings")
        settings_action.triggered.connect(self.open_settings)
        self._build_file_shortcuts()

        self.show_ribbon_action = QAction("Show Ribbon", self)
        self.show_ribbon_action.setCheckable(True)
        self.show_ribbon_action.setChecked(True)
        self.show_ribbon_action.toggled.connect(self._set_ribbon_visible)

        help_action = self.menuBar().addAction("&Help")
        help_action.triggered.connect(self.show_workflow_help)

    def _build_file_shortcuts(self) -> None:
        for text, shortcut, handler in [
            ("Open Data", "Ctrl+O", self._open_via_panel),
            ("Save Session", "Ctrl+S", self.save_session),
            ("Load Session", "Ctrl+L", self.load_session),
        ]:
            action = QAction(text, self)
            action.setShortcut(shortcut)
            action.triggered.connect(handler)
            self.addAction(action)

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
        left_scroll.setMaximumWidth(self.LEFT_RAIL_MAXIMUM_WIDTH)
        left_scroll.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.left_scroll = left_scroll

        # Plot above, analysis notebook below. The lower tabs are attached to
        # their content while the splitter handles plot/data resizing.
        self.plot_workspace.setMinimumHeight(260)
        plot_area = QWidget()
        plot_area_layout = QVBoxLayout(plot_area)
        plot_area_layout.setContentsMargins(0, 0, 0, 0)
        plot_area_layout.setSpacing(6)
        plot_area_layout.addWidget(self._build_plot_tabs_bar())
        plot_area_layout.addWidget(self.plot_workspace, stretch=1)
        self.plot_area = plot_area

        lower_panel = self._build_lower_groups()
        right_splitter = QSplitter(Qt.Orientation.Vertical)
        right_splitter.setChildrenCollapsible(True)
        right_splitter.addWidget(plot_area)
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
        body_splitter.setCollapsible(0, True)
        body_splitter.setCollapsible(1, False)
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
        subtitle = QLabel(f"Eaton Engineering - Analysis Workspace (V{__version__})")
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
            if title == "PLOT" and text == "Generate Plot":
                button.setProperty("ribbonPrimary", "true")
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

    def _build_plot_tabs_bar(self) -> QFrame:
        bar = QFrame()
        bar.setObjectName("PlotTabsBar")
        bar.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.plot_tab_bar = QTabBar()
        self.plot_tab_bar.setObjectName("PlotProfileTabs")
        self.plot_tab_bar.setExpanding(False)
        self.plot_tab_bar.setMovable(False)
        self.plot_tab_bar.setUsesScrollButtons(True)
        self.plot_tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.plot_tab_bar.currentChanged.connect(self._on_plot_tab_changed)
        self.plot_tab_bar.customContextMenuRequested.connect(self._show_plot_tab_menu)
        layout.addWidget(self.plot_tab_bar, stretch=1)

        self._sync_plot_tabs()
        return bar

    # ------------------------------------------------------------------
    # Theme
    # ------------------------------------------------------------------
    def _apply_theme(self) -> None:
        theme_name = self.vm.settings.theme_name()
        self.setStyleSheet(theme.build_stylesheet(theme_name))
        if hasattr(self, "plot_workspace"):
            self.plot_workspace.apply_theme(theme_name)
        if self._help_dialog is not None:
            self._help_dialog.apply_theme(theme_name)

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _sync_plot_tabs(self) -> None:
        if not hasattr(self, "plot_tab_bar"):
            return
        self.vm.ensure_plot_profiles()
        self._syncing_plot_tabs = True
        try:
            while self.plot_tab_bar.count():
                self.plot_tab_bar.removeTab(0)
            for profile in self.vm.state.plot_profiles:
                self.plot_tab_bar.addTab(str(profile.get("name", "Plot")))
            add_index = self.plot_tab_bar.addTab("+")
            self.plot_tab_bar.setTabToolTip(add_index, "Create a new plot")
            index = self.vm.state.active_plot_profile_index
            self.plot_tab_bar.setCurrentIndex(index)
            self._active_plot_tab_index = index
        finally:
            self._syncing_plot_tabs = False

    def _show_plot_tab_menu(self, position) -> None:
        index = self.plot_tab_bar.tabAt(position)
        if index < 0:
            return
        if index >= len(self.vm.state.plot_profiles):
            return
        menu = QMenu(self)
        duplicate_action = menu.addAction("Duplicate")
        rename_action = menu.addAction("Rename")
        delete_action = menu.addAction("Delete")
        delete_action.setEnabled(len(self.vm.state.plot_profiles) > 1)
        chosen = menu.exec(self.plot_tab_bar.mapToGlobal(position))
        if chosen == duplicate_action:
            self._duplicate_plot_profile(index)
        elif chosen == rename_action:
            self._rename_plot_profile(index)
        elif chosen == delete_action:
            self._delete_plot_profile(index)

    def _new_plot_profile(self) -> None:
        self._capture_current_plot_profile()
        result = self.vm.add_plot_profile()
        if not result.ok:
            qt_message_service.warning(self, "New Plot", result.message)
            return
        self._sync_plot_tabs()
        self._apply_active_plot_profile()
        self.statusBar().showMessage(result.message)

    def _duplicate_plot_profile(self, index: int | None = None) -> None:
        self._capture_current_plot_profile()
        result = self.vm.duplicate_plot_profile(index)
        if not result.ok:
            qt_message_service.warning(self, "Duplicate Plot", result.message)
            return
        self._sync_plot_tabs()
        self._apply_active_plot_profile()
        self.statusBar().showMessage(result.message)

    def _rename_plot_profile(self, index: int, name: str | None = None) -> None:
        current = self.vm.state.plot_profiles[index] if 0 <= index < len(self.vm.state.plot_profiles) else {}
        new_name = name
        if new_name is None:
            new_name, ok = QInputDialog.getText(
                self,
                "Rename Plot",
                "Plot name:",
                text=str(current.get("name", f"Plot {index + 1}")),
            )
            if not ok:
                return
        self._capture_current_plot_profile()
        result = self.vm.rename_plot_profile(index, new_name)
        if not result.ok:
            qt_message_service.warning(self, "Rename Plot", result.message)
            return
        self._sync_plot_tabs()
        self.statusBar().showMessage(result.message)

    def _delete_plot_profile(self, index: int, confirm: bool = True) -> None:
        current = self.vm.state.plot_profiles[index] if 0 <= index < len(self.vm.state.plot_profiles) else {}
        name = str(current.get("name", f"Plot {index + 1}"))
        if len(self.vm.state.plot_profiles) <= 1:
            qt_message_service.warning(self, "Delete Plot", "At least one plot must remain in the session.")
            return
        if confirm and not qt_message_service.confirm(
            self,
            "Delete Plot",
            f"Delete plot '{name}'? This removes the plot tab from the current session.",
        ):
            return
        self._capture_current_plot_profile()
        result = self.vm.delete_plot_profile(index)
        if not result.ok:
            qt_message_service.warning(self, "Delete Plot", result.message)
            return
        self._sync_plot_tabs()
        self._apply_active_plot_profile()
        self.statusBar().showMessage(result.message)

    def _on_plot_tab_changed(self, index: int) -> None:
        if self._syncing_plot_tabs or index < 0:
            return
        if index >= len(self.vm.state.plot_profiles):
            self._new_plot_profile()
            return
        if index == self.vm.state.active_plot_profile_index:
            self._active_plot_tab_index = index
            return
        self._capture_current_plot_profile()
        result = self.vm.select_plot_profile(index)
        if not result.ok:
            qt_message_service.warning(self, "Plot Tabs", result.message)
            self._sync_plot_tabs()
            return
        self._active_plot_tab_index = index
        self._apply_active_plot_profile()
        self.statusBar().showMessage(result.message)

    def _capture_current_plot_profile(self) -> None:
        self.vm.ensure_plot_profiles()
        profile = self.vm.state.active_plot_profile() or {}
        appearance = self.plot_workspace.current_axis_appearance() if self._plot_generated else {}
        if not appearance:
            appearance = self._stored_profile_appearance(profile)
        self.vm.capture_working_state(
            x_column=self.axis_panel.x_column(),
            y_columns=self.axis_panel.selected_y(),
            secondary_y_columns=self.axis_panel.selected_secondary_y(),
            plot_kind=self.axis_panel.plot_kind(),
            legend_settings={"display_mode": self.plot_workspace.legend_display()},
            analysis_window=self.axis_panel.analysis_window_texts(),
            axis_ticks=self.plot_workspace.axis_tick_setting_texts(),
            filter_settings=self.axis_panel.filter_setting_texts(),
            title=appearance.get("title", ""),
            x_label=appearance.get("x_label", ""),
            y_label=appearance.get("y_label", ""),
            secondary_y_label=appearance.get("secondary_y_label", ""),
            axis_limits=appearance.get("axis_limits", {}),
            auto_fit_axes=appearance.get("auto_fit_axes", True),
            generated=self._plot_generated,
        )

    @staticmethod
    def _stored_profile_appearance(profile: dict) -> dict:
        return {
            "title": profile.get("title", ""),
            "x_label": profile.get("x_label", ""),
            "y_label": profile.get("y_label", ""),
            "secondary_y_label": profile.get("secondary_y_label", ""),
            "axis_limits": profile.get("axis_limits", {}),
            "auto_fit_axes": profile.get("auto_fit_axes", True),
        }

    def _apply_active_plot_profile(self, *, clear_global_forms: bool = False) -> None:
        self.vm.ensure_plot_profiles()
        profile = self.vm.state.active_plot_profile() or {}
        self.vm.state.limit_lines = [dict(line) for line in profile.get("limit_lines", [])]
        self.vm.state.active_limit_line_index = 0
        self.vm.state.engineering_notes = dict(profile.get("engineering_notes", {}))

        columns = self.vm.state.column_names()
        self.axis_panel.apply_selection(
            columns,
            str(profile.get("x_column", "")),
            list(profile.get("y_columns", [])),
            list(profile.get("secondary_y_columns", [])),
            maths_channel_names=self._maths_channel_names(),
        )
        self.axis_panel.apply_plot_settings(profile)
        axis_ticks = profile.get("axis_ticks", {}) if isinstance(profile, dict) else {}
        self.plot_workspace.set_axis_tick_settings(axis_ticks if isinstance(axis_ticks, dict) else {})
        legend_settings = profile.get("legend", {}) if isinstance(profile, dict) else {}
        display_mode = legend_settings.get("display_mode", "panel") if isinstance(legend_settings, dict) else "panel"
        self.plot_workspace.set_legend_display(str(display_mode))
        self.statistics_panel.set_statistics(self.vm.plot_workspace.statistics([]))
        self.raw_data_panel.clear()
        if clear_global_forms:
            self.maths_panel.clear_form()
        self.maths_panel.refresh()
        self.limits_panel.refresh()
        self.notes_panel.load_from_state()
        self.runs_panel.refresh()
        self.plot_workspace.clear_cursor_markers()
        self.cursor_panel.refresh()
        self._restore_generated_plot(profile)

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
        if self._help_dialog is None:
            self._help_dialog = HelpDialog(self, self.vm.settings.theme_name())
        self._help_dialog.show()
        self._help_dialog.raise_()
        self._help_dialog.activateWindow()

    def save_session(self) -> None:
        initial_dir = self._save_session_initial_path()
        path = qt_file_dialogs.save_session_file(self, initial_dir)
        if not path:
            return
        qt_widget_helpers.remember_session_directory(self.settings_manager, path)
        self._capture_current_plot_profile()
        result = self.vm.save_session(path)
        if result.ok:
            self._current_session_path = str(getattr(result, "payload", None) or path)
        qt_message_service.show_result(self, "Save Session", result)
        self.statusBar().showMessage(result.message)

    def _save_session_initial_path(self) -> str:
        if self._current_session_path:
            return self._current_session_path
        return qt_widget_helpers.save_session_initial_directory(
            self.settings_manager,
            self.vm.state.filepath,
        )

    def load_session(self) -> None:
        initial_dir = qt_widget_helpers.last_session_directory(self.settings_manager)
        path = qt_file_dialogs.open_session_file(self, initial_dir)
        if not path:
            return
        qt_widget_helpers.remember_session_directory(self.settings_manager, path)
        result, main_data_warning_shown = self._restore_session_with_optional_relink(path)
        if not result.ok:
            qt_message_service.error(self, "Load Session", result.message)
            self.statusBar().showMessage(result.message)
            return
        self._current_session_path = path
        selection = result.payload if isinstance(result.payload, dict) else {}
        self._apply_loaded_session(selection)
        warnings = self._warnings_for_display(result.warnings, main_data_warning_shown)
        if warnings:
            qt_message_service.warning(self, "Load Session", "\n".join(warnings))
        self.statusBar().showMessage(result.message)

    def _apply_loaded_session(self, selection: dict) -> None:
        self.data_panel.refresh_from_state()
        self._sync_plot_tabs()
        self._apply_active_plot_profile(clear_global_forms=True)

    def _restore_session_with_optional_relink(self, path: str) -> tuple[Any, bool]:
        result = self.vm.restore_session(path)
        main_data_warning_shown = False
        while result.ok and self._needs_main_data_relink(result):
            replacement = self._prompt_for_relocated_source_file(result)
            main_data_warning_shown = True
            if not replacement:
                break
            result = self.vm.restore_session(path, data_file_override=replacement)
            if result.ok and not self._needs_main_data_relink(result):
                qt_widget_helpers.remember_data_directory(self.settings_manager, replacement)
        return result, main_data_warning_shown

    @staticmethod
    def _needs_main_data_relink(result) -> bool:
        payload = result.payload if isinstance(result.payload, dict) else {}
        return bool(payload.get("main_data_warning")) and not bool(payload.get("main_data_loaded"))

    def _prompt_for_relocated_source_file(self, result) -> str | None:
        payload = result.payload if isinstance(result.payload, dict) else {}
        source_file_path = str(payload.get("source_file_path") or "")
        main_data_warning = str(payload.get("main_data_warning") or "The source data file could not be loaded.")
        message = (
            "The data file saved in this session could not be loaded:\n"
            f"{source_file_path or '(no source path saved)'}\n\n"
            f"{main_data_warning}\n\n"
            "Select the moved CSV/Excel file to continue loading the session, "
            "or cancel to open the session without data."
        )
        qt_message_service.warning(self, "Load Session", message)
        return qt_file_dialogs.locate_data_file(
            self,
            self._initial_relink_directory(source_file_path),
            self._source_filename(source_file_path),
        )

    def _initial_relink_directory(self, source_file_path: str) -> str:
        try:
            source_parent = Path(source_file_path).expanduser().resolve().parent
            if source_file_path and source_parent.is_dir():
                return str(source_parent)
        except Exception:
            pass
        return (
            qt_widget_helpers.last_data_directory(self.settings_manager)
            or qt_widget_helpers.last_session_directory(self.settings_manager)
        )

    @staticmethod
    def _source_filename(source_file_path: str) -> str:
        try:
            return Path(source_file_path).name
        except Exception:
            return ""

    @staticmethod
    def _warnings_for_display(warnings: list[str], main_data_warning_shown: bool) -> list[str]:
        if not main_data_warning_shown:
            return warnings
        return [warning for warning in warnings if not warning.startswith("Main data file:")]

    def _restore_generated_plot(self, profile: dict) -> None:
        """Re-render the plot that was on screen when the session was saved.

        Only regenerates when the saved profile was flagged as generated and the
        restored axis selection is plottable, so loading a session that was never
        plotted leaves a clean canvas. The saved Figure Options appearance (title,
        axis labels, and axis limits) is re-applied so the plot looks identical.
        """
        self._plot_generated = False
        if not (isinstance(profile, dict) and profile.get("generated")):
            self.plot_workspace.clear_plot()
            self.cursor_panel.refresh()
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
            self.plot_workspace.clear_plot()
            self.cursor_panel.refresh()
            return
        self._plot_generated = True
        self._update_statistics(self.axis_panel.all_selected_y())
        self.raw_data_panel.refresh()
        self.limits_panel.refresh_margins()
        self.runs_panel.update_statistics()

    def _on_file_loaded(self, columns: list[str]) -> None:
        suggested_x = self.vm.data_loading.suggested_x_column(columns)
        self._current_session_path = None
        self._plot_generated = False
        self.vm.reset_plot_profiles()
        self._sync_plot_tabs()
        self.plot_workspace.clear_plot()
        self.cursor_panel.refresh()
        self.axis_panel.set_columns(columns, suggested_x, maths_channel_names=self._maths_channel_names())
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
        primary_y = self.axis_panel.selected_y()
        secondary_y = self.axis_panel.selected_secondary_y()
        y_cols = primary_y + [column for column in secondary_y if column not in primary_y]
        if not x_col or not y_cols:
            return None
        xmin, xmax = self.axis_panel.analysis_window()
        use_filter, cutoff, order = self.axis_panel.filter_settings()
        channel_colours = self.vm.persistent_plot_channel_colours(primary_y, secondary_y)
        return self.plot_workspace.generate_plot(
            x_col,
            y_cols,
            xmin,
            xmax,
            limit_lines=self._overlay_limit_lines(),
            secondary_y=secondary_y,
            plot_kind=self.axis_panel.plot_kind(),
            use_filter=use_filter,
            cutoff=cutoff,
            order=order,
            channel_colours=channel_colours,
            axis_tick_settings=self.plot_workspace.axis_tick_setting_texts(),
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

    def _maths_channel_names(self) -> list[str]:
        return list(self.vm.state.calculated_channels.keys())

    def _on_channels_changed(self) -> None:
        columns = self.vm.maths_channels.state.column_names()
        if columns:
            self.axis_panel.update_columns(columns, maths_channel_names=self._maths_channel_names())
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
