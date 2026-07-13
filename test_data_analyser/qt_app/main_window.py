"""PySide6 main window.

Wires together the framework-independent viewmodels and the Qt panels for the
full analysis workflow: data loading, plotting, raw data, maths channels,
limits, engineering notes, run comparison, cursor comparison, and sessions.
PySide6 is imported only within ``qt_app``; analysis logic stays in the
domain/services/viewmodels layers.
"""
from __future__ import annotations

import base64
import time
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QActionGroup, QDragEnterEvent, QDropEvent, QGuiApplication, QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView,
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
from .application_status_manager import ApplicationStatusManager, PlotStatus
from .command_manager import CommandManager
from .recovery_policy import RecoveryCandidate, find_recovery_candidate
from .ribbon_manager import RibbonManager
from .user_experience_mode import (
    BASIC_HIDDEN_COMMAND_IDS,
    BASIC_HIDDEN_PANEL_IDS,
    UserExperienceMode,
)
from .workspace import (
    DockArea,
    PanelDescriptor,
    WorkspaceManager,
    WorkspacePreset,
    WorkspaceRegistry,
)
from .widgets.axis_selection_panel import AxisSelectionPanel
from .widgets.best_fit_formulas_panel import BestFitFormulasPanel
from .widgets.cursor_compare_panel import CursorComparePanel
from .widgets.data_file_panel import DataFilePanel
from .widgets.dashboard import Dashboard
from .widgets.engineering_notes_panel import EngineeringNotesPanel
from .widgets.limits_panel import LimitsPanel
from .widgets.maths_channels_panel import MathsChannelsPanel
from .widgets.plot_workspace import PlotWorkspace
from .widgets.raw_data_panel import RawDataPanel
from .widgets.runs_comparison_panel import RunsComparisonPanel
from .widgets.statistics_panel import StatisticsPanel
from .widgets.command_palette import CommandPalette

if TYPE_CHECKING:
    from .widgets.help_dialog import HelpDialog

HelpDialog = None
SettingsDialog = None


class MainWindow(QMainWindow):
    LOWER_PLOT_INDEX = 0
    LOWER_ANALYSIS_INDEX = 1
    LOWER_REQUIREMENTS_INDEX = 2
    LOWER_NOTES_INDEX = 3
    LEFT_RAIL_INITIAL_WIDTH = 300
    LEFT_RAIL_MINIMUM_WIDTH = 240
    LEFT_RAIL_MAXIMUM_WIDTH = 640
    DATA_DROP_SUFFIXES = (".csv", ".xlsx", ".xls")
    SESSION_DROP_SUFFIXES = (".json",)
    AUTOSAVE_POLL_MS = 30_000

    def __init__(self, settings_manager: SettingsManager | None = None) -> None:
        super().__init__()
        self.settings_manager = settings_manager or SettingsManager()
        self.vm = MainWindowViewModel(self.settings_manager)
        self.vm.ensure_plot_profiles()
        self._plot_generated = False
        self._plot_display_frozen = False
        self._plot_profile_snapshots: dict[int, dict[str, Any]] = {}
        self._last_plot_selection: dict[str, Any] | None = None
        self._syncing_plot_tabs = False
        self._active_plot_tab_index = self.vm.state.active_plot_profile_index
        self._current_session_path: str | None = None
        self._help_dialog: HelpDialog | None = None
        self._last_autosave_epoch: float | None = None
        self._active_recovery_path: Path | None = None
        self._recovery_candidate: RecoveryCandidate | None = None
        self._experience_mode = UserExperienceMode.from_value(
            self.settings_manager.get("general_ui", "user_experience_mode")
        )
        self.app_status = ApplicationStatusManager(self.statusBar())
        self.command_manager = CommandManager(self)
        self._command_palette: CommandPalette | None = None
        self._register_commands()

        self.setWindowTitle("Test Data Analyser — Eaton Edition")
        self.resize(1320, 840)
        self.setAcceptDrops(True)

        self._build_menu()
        self._build_central_layout()
        self._apply_theme()
        self._apply_user_experience_mode()

        self._autosave_timer = QTimer(self)
        self._autosave_timer.setInterval(self.AUTOSAVE_POLL_MS)
        self._autosave_timer.timeout.connect(self._on_autosave_tick)
        self._configure_autosave_timer()

        self.app_status.show_message("Ready. Open a data file to begin.")
        self.app_status.set_plot_status(PlotStatus.NO_PLOT)
        self.app_status.set_session_dirty(False)
        if self._startup_behaviour() == "last_session":
            QTimer.singleShot(0, self._open_last_session_at_startup)

    # ------------------------------------------------------------------
    # Construction
    # ------------------------------------------------------------------
    def _build_menu(self) -> None:
        settings_action = self.command_manager.action("app.settings")
        settings_action.setText("&Settings")
        self.menuBar().addAction(settings_action)

        workspace_menu = self.menuBar().addMenu("&Workspace")
        for command_id in (
            "workspace.apply.analysis",
            "workspace.apply.comparison",
            "workspace.apply.reporting",
            "workspace.apply.dataEditing",
        ):
            workspace_menu.addAction(self.command_manager.action(command_id))
        workspace_menu.addSeparator()
        workspace_menu.addAction(self.command_manager.action("workspace.saveCustom"))
        workspace_menu.addAction(self.command_manager.action("workspace.restoreCustom"))
        workspace_menu.addSeparator()
        workspace_menu.addAction(self.command_manager.action("plot.workspace.float"))
        workspace_menu.addAction(self.command_manager.action("plot.workspace.dock"))
        self.workspace_menu = workspace_menu

        mode_menu = self.menuBar().addMenu("&Mode")
        mode_menu.addAction(self.command_manager.action("view.mode.basic"))
        mode_menu.addAction(self.command_manager.action("view.mode.advanced"))
        self.mode_menu = mode_menu

        self.show_ribbon_action = self.command_manager.action("workspace.ribbon.toggle")

        help_action = self.command_manager.action("app.help")
        help_action.setText("&Help")
        self.menuBar().addAction(help_action)

    def _register_commands(self) -> None:
        register = self.command_manager.register
        advanced_only = {
            "availability": self._advanced_mode_available,
            "disabled_reason": "Switch to Advanced mode to use this command.",
        }
        register("data.open", "Open Excel", self._open_via_panel, category="Data", aliases=("open csv", "open xlsx"), shortcut="Ctrl+O", tooltip="Open a CSV or Excel data file.")
        register("session.create", "Create Session", self._create_manual_session, category="Home", aliases=("new session",), shortcut="Ctrl+N", tooltip="Start a blank manual data session.")
        register("session.save", "Save Session", self.save_session, category="Home", aliases=("save analysis",), shortcut="Ctrl+S", tooltip="Save the current analysis session.")
        register("session.open", "Load Session", self.load_session, category="Home", aliases=("open session",), shortcut="Ctrl+L", tooltip="Load a saved analysis session.")
        register("recent.open", "Recent", self._show_recent_menu, category="Home", aliases=("recent files", "recent sessions"), tooltip="Open recent data files and sessions.")
        register("data.exportSelection", "Export Data", self._export_selected_data, category="Data", aliases=("export table",), tooltip="Export the selected Raw Data view.")
        register("plot.generate", "Generate Plot", self._on_generate_plot, category="Plot", aliases=("render", "refresh graph"), shortcut="F5", tooltip="Generate the active plot from the selected channels.")
        register("plot.saveImage", "Save Plot", self._save_plot_png, category="Plot", aliases=("export figure", "save image"), tooltip="Save the current figure.", availability=lambda: self._plot_generated, disabled_reason="Generate a plot first.")
        register("plot.clear", "Clear Plot", self._clear_plot, category="Plot", tooltip="Clear the active plot canvas.")
        register("comparison.show", "Runs / Comparison", lambda: self._show_plot_page(0), category="Analysis", aliases=("runs", "compare"), tooltip="Open Runs / Comparison.")
        register("analysis.statistics.show", "Statistics", lambda: self._show_analysis_page(0), category="Analysis", tooltip="Open Statistics.")
        register("data.raw.show", "Raw Data", self._show_raw_data, category="Data", aliases=("table", "edit data"), tooltip="Open Raw Data.")
        register("analysis.maths.show", "Maths Channels", lambda: self._show_analysis_page(2), category="Data", aliases=("calculated channels",), tooltip="Open Maths Channels.", **advanced_only)
        register("analysis.bestFits.show", "Best Fit Formulas", lambda: self._show_analysis_page(3), category="Analysis", aliases=("regression formulas",), tooltip="Open Best Fit Formulas.")
        register("analysis.pointCompare.show", "Point Compare", lambda: self._show_plot_page(1), category="Analysis", aliases=("cursor",), tooltip="Open Point Compare.", **advanced_only)
        register("requirements.limits.show", "Limits", lambda: self._show_requirements_page(0), category="Requirements", tooltip="Open Requirements / Limits.", **advanced_only)
        register("requirements.margins.show", "Margins", lambda: self._show_requirements_page(1), category="Requirements", tooltip="Open margin-to-limit results.", **advanced_only)
        register("requirements.refresh", "Refresh", self._refresh_requirements, category="Requirements", tooltip="Refresh limits, margins, and plot overlays.", **advanced_only)
        register("reporting.notes.show", "Engineering Notes", lambda: self._show_lower_page(self.LOWER_NOTES_INDEX), category="Reporting", aliases=("notes",), tooltip="Open Engineering Notes.", **advanced_only)
        register("reporting.notes.refresh", "Refresh Report", self._refresh_engineering_notes, category="Reporting", tooltip="Refresh compiled report text.", **advanced_only)
        register("reporting.notes.copy", "Copy Notes", self._copy_engineering_notes, category="Reporting", tooltip="Copy compiled notes to the clipboard.", **advanced_only)
        register("reporting.notes.clear", "Clear Notes", self._clear_engineering_notes, category="Reporting", tooltip="Clear Engineering Notes.", **advanced_only)
        for preset, suffix, label in (
            (WorkspacePreset.ANALYSIS, "analysis", "Analysis"),
            (WorkspacePreset.COMPARISON, "comparison", "Comparison"),
            (WorkspacePreset.REPORTING, "reporting", "Reporting"),
            (WorkspacePreset.DATA_EDITING, "dataEditing", "Data Editing"),
        ):
            register(f"workspace.apply.{suffix}", label, lambda preset=preset: self._apply_workspace_preset(preset), category="Settings", aliases=(f"{label} workspace",), tooltip=f"Apply the {label} workspace layout.", **advanced_only)
        register("workspace.saveCustom", "Save Custom Layout", self._save_custom_workspace, category="Settings", tooltip="Overwrite the single Custom workspace layout.", **advanced_only)
        register("workspace.restoreCustom", "Restore Custom Layout", self._restore_custom_workspace, category="Settings", tooltip="Restore the saved Custom workspace layout.", **advanced_only)
        register("plot.workspace.float", "Float Plot Workspace", self._float_plot_workspace, category="Plot", aliases=("detach plot",), tooltip="Open Plot Workspace in a floating window.")
        register("plot.workspace.dock", "Bring Plot Back", self._dock_plot_workspace, category="Plot", aliases=("dock plot",), tooltip="Return Plot Workspace to the main window.")
        ribbon_action = register(
            "workspace.ribbon.toggle",
            "Show Ribbon",
            None,
            category="Settings",
            checkable=True,
            checked=True,
            tooltip="Show or hide the ribbon.",
        )
        ribbon_action.toggled.connect(self._set_ribbon_visible)
        basic_action = register(
            "view.mode.basic",
            "Basic Mode",
            lambda: self._set_user_experience_mode(UserExperienceMode.BASIC),
            category="Settings",
            aliases=("simple view",),
            tooltip="Show the core data and plotting workflow.",
            checkable=True,
            checked=self._experience_mode is UserExperienceMode.BASIC,
        )
        advanced_action = register(
            "view.mode.advanced",
            "Advanced Mode",
            lambda: self._set_user_experience_mode(UserExperienceMode.ADVANCED),
            category="Settings",
            aliases=("engineering tools",),
            tooltip="Show all engineering analysis tools.",
            checkable=True,
            checked=self._experience_mode is UserExperienceMode.ADVANCED,
        )
        self._experience_mode_action_group = QActionGroup(self)
        self._experience_mode_action_group.setExclusive(True)
        self._experience_mode_action_group.addAction(basic_action)
        self._experience_mode_action_group.addAction(advanced_action)
        register("app.settings", "Settings", self.open_settings, category="Settings", tooltip="Open application settings.")
        register("app.help", "Help", self.show_workflow_help, category="Settings", aliases=("shortcuts", "workflow help"), tooltip="Open workflow help.")
        register("palette.open", "Command Palette", self._open_command_palette, category="Home", aliases=("command search",), shortcut="Ctrl+Shift+P", tooltip="Search and execute application commands.")
        for panel_id, title in (
            ("plot.controls", "Plot Navigator"), ("plot.legend", "Legend"), ("analysis.statistics", "Statistics"), ("data.raw", "Raw Data"), ("requirements.limits", "Requirements / Limits"), ("notes.engineering", "Engineering Notes"), ("runs.comparison", "Runs / Comparison"), ("compare.points", "Point Compare"), ("maths.channels", "Maths Channels"), ("analysis.best_fit_formulas", "Best Fit Formulas"),
        ):
            options = advanced_only if panel_id in BASIC_HIDDEN_PANEL_IDS else {}
            register(f"panel.show.{panel_id}", f"Show {title}", lambda panel_id=panel_id: self.workspace_manager.show_panel(panel_id), category="View", aliases=(title,), tooltip=f"Show and focus {title}.", **options)

    def _build_central_layout(self) -> None:
        central = QWidget()
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)
        root.addWidget(self._build_header())

        self.data_panel = DataFilePanel(self.vm.data_loading)
        self.axis_panel = AxisSelectionPanel()
        self.axis_panel.plotConfigurationChanged.connect(
            self._on_plot_configuration_changed
        )
        self.plot_workspace = PlotWorkspace(self.vm.plot_workspace, self.vm.settings)
        self.plot_workspace.canvas.toolbar.set_axis_reset_controller(self._reset_axis_appearance)
        self.statistics_panel = StatisticsPanel()
        self.raw_data_panel = RawDataPanel(self.vm.raw_data, self.vm.dataset)
        self.raw_data_panel.set_selection_provider(self._current_axis_selection)
        self.raw_data_panel.datasetChanged.connect(self._on_dataset_changed)
        self.maths_panel = MathsChannelsPanel(self.vm.maths_channels)
        self.best_fit_formulas_panel = BestFitFormulasPanel()
        self.limits_panel = LimitsPanel(self.vm.limits, self.vm.plot_workspace)
        self.limits_panel.set_selection_provider(self._current_axis_selection)
        self.notes_panel = EngineeringNotesPanel(self.vm.engineering_notes)
        self.notes_panel.set_context_provider(self._notes_context)
        self.runs_panel = RunsComparisonPanel(self.vm.runs_comparison)
        self.runs_panel.set_selection_provider(self._current_axis_selection)
        self.plot_workspace.set_cursor_viewmodel(self.vm.cursor_compare)
        self.plot_workspace.annotationsChanged.connect(self._on_annotations_changed)
        self.plot_workspace.legendChannelStyleChanged.connect(self._on_legend_channel_style_changed)
        self.plot_workspace.legendChannelVisibilityChanged.connect(self._on_legend_channel_visibility_changed)
        self.plot_workspace.bestFitFormulasChanged.connect(self._refresh_best_fit_formulas)
        self.cursor_panel = CursorComparePanel(self.vm.cursor_compare, self.plot_workspace)
        self.cursor_panel.analysisWindowRequested.connect(self._on_cursor_window)

        self.data_panel.fileLoaded.connect(self._on_file_loaded)
        self.data_panel.sheetChanged.connect(self._on_sheet_changed)
        self.data_panel.statusMessage.connect(self.app_status.show_message)
        self.maths_panel.channelRenamed.connect(self.axis_panel.rename_channel_selection)
        self.maths_panel.channelsChanged.connect(self._on_channels_changed)
        self.maths_panel.statusMessage.connect(self.app_status.show_message)
        self.limits_panel.limitsChanged.connect(self._on_limits_changed)
        self.limits_panel.statusMessage.connect(self.app_status.show_message)
        self.runs_panel.comparisonRequested.connect(self._on_generate_comparison)
        self.runs_panel.statusMessage.connect(self.app_status.show_message)

        root.addWidget(self._build_ribbon())
        root.addWidget(self._build_collapsed_ribbon_bar())

        self.plot_workspace.setMinimumHeight(260)
        self.plot_area = self._build_plot_workspace_panel()
        self.plot_navigator = self._build_plot_navigator_panel()
        self.requirements_panel = self._build_requirements_panel()
        self.workspace_registry = self._build_workspace_registry()
        self.workspace_manager = WorkspaceManager(
            self,
            self.workspace_registry,
            self.settings_manager,
        )
        self.dashboard = Dashboard(self.command_manager)
        self.dashboard.recentFileRequested.connect(self._open_recent_file)
        self.dashboard.recentSessionRequested.connect(self._open_recent_session)
        self.dashboard.recoveryRequested.connect(self._recover_from_dashboard)
        self.dashboard.recoveryDismissed.connect(self._dismiss_dashboard_recovery)
        self.content_stack = QStackedWidget()
        self.content_stack.setObjectName("MainContentStack")
        self.content_stack.addWidget(self.dashboard)
        self.content_stack.addWidget(self.workspace_manager.widget)
        root.addWidget(self.content_stack, stretch=1)
        self.setCentralWidget(central)
        self.workspace_manager.build()
        self._refresh_dashboard()
        self.content_stack.setCurrentWidget(self.dashboard)
        self.command_manager.refresh_availability()

    def _build_plot_workspace_panel(self) -> QWidget:
        panel = QWidget()
        panel.setObjectName("PlotWorkspacePanel")
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        layout.addWidget(self._build_plot_tabs_bar())
        layout.addWidget(self.plot_workspace, stretch=1)
        return panel

    def _build_plot_navigator_panel(self) -> QScrollArea:
        content = QWidget()
        layout = QVBoxLayout(content)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.data_panel)
        layout.addWidget(self.axis_panel, stretch=1)
        content.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        scroll = QScrollArea()
        scroll.setObjectName("PlotNavigator")
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setWidget(content)
        scroll.setMinimumWidth(self.LEFT_RAIL_MINIMUM_WIDTH)
        scroll.setMaximumWidth(self.LEFT_RAIL_MAXIMUM_WIDTH)
        return scroll

    def _build_requirements_panel(self) -> QStackedWidget:
        stack = self._build_panel_stack([self.limits_panel, self.limits_panel.summary_panel])
        stack.setObjectName("RequirementsPanelStack")
        return stack

    def _build_workspace_registry(self) -> WorkspaceRegistry:
        legend_panel = self.plot_workspace.take_legend_panel()
        registry = WorkspaceRegistry()
        descriptors = (
            PanelDescriptor(
                "plot.workspace",
                "Plot Workspace",
                self.plot_area,
                DockArea.CENTER,
                closable=False,
                pinnable=False,
                required=True,
            ),
            PanelDescriptor("plot.controls", "Plot Navigator", self.plot_navigator, DockArea.LEFT),
            PanelDescriptor("plot.legend", "Legend", legend_panel, DockArea.RIGHT),
            PanelDescriptor(
                "analysis.statistics", "Statistics", self.statistics_panel, DockArea.RIGHT
            ),
            PanelDescriptor("data.raw", "Raw Data", self.raw_data_panel, DockArea.BOTTOM),
            PanelDescriptor(
                "requirements.limits",
                "Requirements / Limits",
                self.requirements_panel,
                DockArea.BOTTOM,
            ),
            PanelDescriptor(
                "notes.engineering", "Engineering Notes", self.notes_panel, DockArea.RIGHT
            ),
            PanelDescriptor(
                "runs.comparison", "Runs / Comparison", self.runs_panel, DockArea.BOTTOM
            ),
            PanelDescriptor("compare.points", "Point Compare", self.cursor_panel, DockArea.BOTTOM),
            PanelDescriptor("maths.channels", "Maths Channels", self.maths_panel, DockArea.BOTTOM),
            PanelDescriptor(
                "analysis.best_fit_formulas",
                "Best Fit Formulas",
                self.best_fit_formulas_panel,
                DockArea.BOTTOM,
            ),
        )
        for descriptor in descriptors:
            registry.register(descriptor)
        return registry

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
        ribbon_layout = (
            ("Home", ("session.create", "session.save", "session.open", "recent.open", "palette.open")),
            ("Data", ("data.open", "data.raw.show", "analysis.maths.show", "data.exportSelection")),
            ("Plot", ("plot.generate", "plot.saveImage", "plot.clear", "plot.workspace.float")),
            ("Analysis", ("analysis.statistics.show", "comparison.show", "analysis.bestFits.show", "analysis.pointCompare.show")),
            ("Requirements", ("requirements.limits.show", "requirements.margins.show", "requirements.refresh")),
            ("Reporting", ("reporting.notes.show", "reporting.notes.refresh", "reporting.notes.copy", "reporting.notes.clear")),
            ("Settings", ("app.settings", "view.mode.basic", "view.mode.advanced", "workspace.apply.analysis", "app.help")),
        )
        self.ribbon_manager = RibbonManager(
            self,
            self.command_manager,
            ribbon_layout,
            menu_populators={"recent.open": self._populate_recent_menu},
        )
        ribbon = self.ribbon_manager.build()
        self.ribbon = ribbon
        self.ribbon_buttons = dict(self.ribbon_manager.buttons)
        compatibility_keys = {
            "FILE:Open Excel": "data.open", "FILE:Create Session": "session.create", "FILE:Save Session": "session.save", "FILE:Load Session": "session.open", "FILE:Recent": "recent.open", "FILE:Export Data": "data.exportSelection",
            "PLOT:Generate Plot": "plot.generate", "PLOT:Save Plot": "plot.saveImage", "PLOT:Clear Plot": "plot.clear", "PLOT:Runs / Comparison": "comparison.show",
            "ANALYSIS:Statistics": "analysis.statistics.show", "ANALYSIS:Raw Data": "data.raw.show", "ANALYSIS:Maths Channels": "analysis.maths.show", "ANALYSIS:Best Fit Formulas": "analysis.bestFits.show", "ANALYSIS:Cursor": "analysis.pointCompare.show",
            "REQUIREMENTS:Limits": "requirements.limits.show", "REQUIREMENTS:Margins": "requirements.margins.show", "REQUIREMENTS:Refresh": "requirements.refresh",
            "NOTES:Engineering Notes": "reporting.notes.show", "NOTES:Refresh Report Text": "reporting.notes.refresh", "NOTES:Clear Notes": "reporting.notes.clear", "NOTES:Copy Notes": "reporting.notes.copy",
        }
        for key, command_id in compatibility_keys.items():
            self.ribbon_buttons[key] = self.ribbon_manager.button_for(command_id)
        layout = ribbon.layout()
        assert isinstance(layout, QHBoxLayout)
        self.hide_ribbon_button = QPushButton("Hide Ribbon")
        self.hide_ribbon_button.setObjectName("RibbonButton")
        self.hide_ribbon_button.setFixedHeight(23)
        self.hide_ribbon_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.hide_ribbon_button.setAccessibleName("Hide ribbon")
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
        self.show_ribbon_button.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.show_ribbon_button.setAccessibleName("Show ribbon")
        self.show_ribbon_button.clicked.connect(lambda: self.show_ribbon_action.setChecked(True))
        layout.addStretch(1)
        layout.addWidget(self.show_ribbon_button, 0, Qt.AlignmentFlag.AlignRight)
        bar.setVisible(False)
        return bar

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
                self.best_fit_formulas_panel,
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
        self.plot_tab_bar.setMovable(True)
        self.plot_tab_bar.setUsesScrollButtons(True)
        self.plot_tab_bar.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.plot_tab_bar.currentChanged.connect(self._on_plot_tab_changed)
        self.plot_tab_bar.tabMoved.connect(self._on_plot_tab_moved)
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

    def _on_plot_tab_moved(self, from_index: int, to_index: int) -> None:
        """Reorder plot profiles when a tab is dragged, keeping the '+' tab last."""
        if self._syncing_plot_tabs:
            return
        profile_count = len(self.vm.state.plot_profiles)
        if from_index >= profile_count or to_index >= profile_count:
            # The trailing '+' tab cannot be moved; restore the tab order.
            QTimer.singleShot(0, self._sync_plot_tabs)
            return
        result = self.vm.reorder_plot_profile(from_index, to_index)
        if result.ok:
            self._show_status(result.message)
        QTimer.singleShot(0, self._sync_plot_tabs)

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
        self._show_status(result.message)

    def _duplicate_plot_profile(self, index: int | None = None) -> None:
        source_index = self.vm.state.active_plot_profile_index if index is None else index
        self._capture_current_plot_profile()
        result = self.vm.duplicate_plot_profile(index)
        if not result.ok:
            qt_message_service.warning(self, "Duplicate Plot", result.message)
            return
        if isinstance(result.payload, int):
            self._insert_plot_snapshot(result.payload, self._plot_profile_snapshots.get(source_index))
        self._sync_plot_tabs()
        self._apply_active_plot_profile()
        self._show_status(result.message)

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
        self._show_status(result.message)

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
        self._delete_plot_snapshot(index)
        self._sync_plot_tabs()
        self._apply_active_plot_profile()
        self._show_status(result.message)

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
        self._show_status(result.message)

    def _capture_current_plot_profile(self) -> None:
        self.vm.ensure_plot_profiles()
        profile = self.vm.state.active_plot_profile() or {}
        appearance = self.plot_workspace.current_axis_appearance() if self._plot_generated else {}
        if self._plot_display_frozen:
            self._capture_preserved_plot_profile(profile, appearance)
            return
        if not appearance:
            appearance = self._stored_profile_appearance(profile)
        self._capture_working_state(
            profile,
            appearance,
            x_column=self.axis_panel.x_column(),
            y_columns=self.axis_panel.selected_y(),
            secondary_y_columns=self.axis_panel.selected_secondary_y(),
            plot_kind=self.axis_panel.plot_kind(),
            best_fit_lines=self.plot_workspace.best_fit_settings(),
            annotations=self.plot_workspace.current_annotations(),
            analysis_window=self.axis_panel.analysis_window_texts(),
            axis_ticks=self.plot_workspace.axis_tick_setting_texts(),
            filter_settings=self.axis_panel.filter_setting_texts(),
            generated=self._plot_generated,
        )

    def _capture_preserved_plot_profile(self, profile: dict, appearance: dict | None = None) -> None:
        if not appearance:
            appearance = self._stored_profile_appearance(profile)
        self._capture_working_state(
            profile,
            appearance,
            x_column=str(profile.get("x_column", "")),
            y_columns=list(profile.get("y_columns", [])),
            secondary_y_columns=list(profile.get("secondary_y_columns", [])),
            plot_kind=str(profile.get("plot_kind", "Line")),
            best_fit_lines=list(profile.get("best_fit_lines", [])) if isinstance(profile.get("best_fit_lines"), list) else [],
            annotations=list(profile.get("annotations", [])) if isinstance(profile.get("annotations"), list) else [],
            analysis_window=dict(profile.get("analysis_window", {})) if isinstance(profile.get("analysis_window"), dict) else {},
            axis_ticks=dict(profile.get("axis_ticks", {})) if isinstance(profile.get("axis_ticks"), dict) else {},
            filter_settings=dict(profile.get("filter", {})) if isinstance(profile.get("filter"), dict) else {},
            generated=bool(profile.get("generated", False)),
        )

    def _capture_working_state(
        self,
        profile: dict,
        appearance: dict,
        *,
        x_column: str,
        y_columns: list,
        secondary_y_columns: list,
        plot_kind: str,
        best_fit_lines: list,
        annotations: list,
        analysis_window: dict,
        axis_ticks: dict,
        filter_settings: dict,
        generated: bool,
    ) -> None:
        """Fold the supplied axis/appearance state into the active plot profile.

        Both capture paths (live UI vs frozen/preserved profile) supply the
        differing values above; the shared legend and appearance fields are
        derived here so the two callers stay in lock-step.
        """
        self.vm.capture_working_state(
            x_column=x_column,
            y_columns=y_columns,
            secondary_y_columns=secondary_y_columns,
            plot_kind=plot_kind,
            legend_settings=self._current_legend_settings(profile),
            best_fit_lines=best_fit_lines,
            annotations=annotations,
            analysis_window=analysis_window,
            axis_ticks=axis_ticks,
            filter_settings=filter_settings,
            title=appearance.get("title", ""),
            x_label=appearance.get("x_label", ""),
            y_label=appearance.get("y_label", ""),
            secondary_y_label=appearance.get("secondary_y_label", ""),
            axis_limits=appearance.get("axis_limits", {}),
            auto_fit_axes=appearance.get("auto_fit_axes", True),
            generated=generated,
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

    def _current_legend_settings(self, profile: dict) -> dict[str, Any]:
        legend_settings = profile.get("legend", {}) if isinstance(profile, dict) else {}
        legend = dict(legend_settings) if isinstance(legend_settings, dict) else {}
        legend["display_mode"] = self.plot_workspace.legend_display()
        return legend

    def _cache_active_plot_snapshot(self, result) -> None:
        payload = result.payload if isinstance(result.payload, dict) else {}
        plot_data = payload.get("plot_data")
        if plot_data is None:
            return
        self._plot_profile_snapshots[self.vm.state.active_plot_profile_index] = {"plot_data": plot_data}

    def _insert_plot_snapshot(self, index: int, snapshot: dict[str, Any] | None = None) -> None:
        self._plot_profile_snapshots = {
            (profile_index + 1 if profile_index >= index else profile_index): value
            for profile_index, value in self._plot_profile_snapshots.items()
        }
        if snapshot is not None:
            self._plot_profile_snapshots[index] = dict(snapshot)

    def _delete_plot_snapshot(self, index: int) -> None:
        updated: dict[int, dict[str, Any]] = {}
        for profile_index, snapshot in self._plot_profile_snapshots.items():
            if profile_index == index:
                continue
            updated[profile_index - 1 if profile_index > index else profile_index] = snapshot
        self._plot_profile_snapshots = updated

    def _apply_active_plot_profile(self, *, clear_global_forms: bool = False) -> None:
        self._plot_display_frozen = False
        self.vm.ensure_plot_profiles()
        profile = self.vm.state.active_plot_profile() or {}
        self.vm.state.limit_lines = [dict(line) for line in profile.get("limit_lines", [])]
        self.vm.state.active_limit_line_index = 0
        self.vm.state.engineering_notes = dict(profile.get("engineering_notes", {}))

        columns = self._plottable_columns()
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
        best_fit_lines = profile.get("best_fit_lines", []) if isinstance(profile, dict) else []
        self.plot_workspace.set_best_fit_settings(best_fit_lines if isinstance(best_fit_lines, list) else [])
        annotations = profile.get("annotations", []) if isinstance(profile, dict) else []
        self.plot_workspace.set_annotations(annotations if isinstance(annotations, list) else [])
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

    def _reset_axis_appearance(self) -> None:
        """Clear the active plot's manual title/labels/limits/ticks and re-render."""
        result = self.vm.reset_active_axis_appearance()
        if not result.ok:
            self._show_status(result.message)
            return
        self._apply_active_plot_profile()
        self._show_status(result.message)
        self._refresh_best_fit_formulas()

    def _open_via_panel(self) -> None:
        self.data_panel.open_file()

    def _create_manual_session(self) -> None:
        if self.vm.state.has_data and self.vm.state.is_dirty:
            if not qt_message_service.confirm(
                self,
                "Create Session",
                "Start a new manual data session? Any unsaved changes to the current data will be lost.",
            ):
                return
        result = self.vm.create_manual_session()
        self._active_recovery_path = None
        self._current_session_path = None
        self._plot_generated = False
        self._plot_display_frozen = False
        self._last_plot_selection = None
        self._plot_profile_snapshots.clear()
        self._sync_plot_tabs()
        self.plot_workspace.clear_plot()
        self.cursor_panel.refresh()
        self.data_panel.show_manual_session()
        suggested_x = self.vm.data_loading.suggested_x_column(self._plottable_columns())
        self.axis_panel.set_columns(
            self._plottable_columns(), suggested_x, maths_channel_names=self._maths_channel_names()
        )
        self.vm.set_current_x_axis(self.axis_panel.x_column())
        self.statistics_panel.set_statistics(self.vm.plot_workspace.statistics([]))
        self.maths_panel.clear_form()
        self.maths_panel.refresh()
        self.limits_panel.refresh()
        self.notes_panel.load_from_state()
        self.runs_panel.refresh()
        self.raw_data_panel.enter_edit_mode()
        self._show_analysis_page(1)
        self._show_workspace()
        self.app_status.set_plot_status(PlotStatus.NO_PLOT)
        self._show_status(
            f"{result.message} Edit the Raw Data table, then generate a plot."
        )

    def _on_dataset_changed(self) -> None:
        """Refresh channel-dependent views after a structural or cell dataset edit."""
        self.axis_panel.update_columns(
            self._plottable_columns(), maths_channel_names=self._maths_channel_names()
        )
        self.vm.set_current_x_axis(self.axis_panel.x_column())
        if self.vm.state.calculated_channels:
            self.vm.maths_channels.recalculate()
        self.maths_panel.refresh()
        self.statistics_panel.set_statistics(self.vm.plot_workspace.statistics([]))
        self.vm.state.is_dirty = True
        self._sync_durable_status()

    def _set_ribbon_visible(self, visible: bool) -> None:
        if hasattr(self, "ribbon"):
            self.ribbon.setVisible(visible)
        if hasattr(self, "collapsed_ribbon_bar"):
            self.collapsed_ribbon_bar.setVisible(not visible)
        self._show_status("Ribbon shown." if visible else "Ribbon hidden.")

    def _advanced_mode_available(self) -> bool:
        return self._experience_mode is UserExperienceMode.ADVANCED

    def _apply_user_experience_mode(self) -> None:
        is_basic = self._experience_mode is UserExperienceMode.BASIC
        self.workspace_manager.set_visibility_mask(
            BASIC_HIDDEN_PANEL_IDS if is_basic else frozenset()
        )
        for command_id in BASIC_HIDDEN_COMMAND_IDS:
            self.command_manager.action(command_id).setVisible(not is_basic)
        self.command_manager.action("view.mode.basic").setChecked(is_basic)
        self.command_manager.action("view.mode.advanced").setChecked(not is_basic)
        self.command_manager.refresh_availability()

    def _set_user_experience_mode(self, mode: UserExperienceMode) -> None:
        resolved = UserExperienceMode.from_value(mode)
        if resolved is self._experience_mode:
            return
        self._experience_mode = resolved
        self._apply_user_experience_mode()
        self.settings_manager.set("general_ui", "user_experience_mode", resolved.value)
        try:
            self.settings_manager.save()
        except RuntimeError:
            self._show_status(
                f"{resolved.value.title()} mode applied for this run; settings are read-only."
            )
            return
        self._show_status(f"{resolved.value.title()} mode applied.")

    def _show_status(self, message: object) -> None:
        self.app_status.show_message(message)
        self._sync_durable_status()
        self.command_manager.refresh_availability()

    def _sync_durable_status(self) -> None:
        self.app_status.set_session_dirty(self.vm.state.is_dirty)

    def _on_plot_configuration_changed(self) -> None:
        if not self._plot_generated:
            self.app_status.set_plot_status(PlotStatus.NO_PLOT)
            return
        current = self._current_plot_selection_signature()
        if self._last_plot_selection is not None and current == self._last_plot_selection:
            self.app_status.set_plot_status(PlotStatus.CURRENT)
        else:
            self.app_status.set_plot_status(PlotStatus.STALE)

    def _show_lower_page(self, index: int) -> None:
        panel_ids = {
            self.LOWER_PLOT_INDEX: "runs.comparison",
            self.LOWER_ANALYSIS_INDEX: "analysis.statistics",
            self.LOWER_REQUIREMENTS_INDEX: "requirements.limits",
            self.LOWER_NOTES_INDEX: "notes.engineering",
        }
        self.workspace_manager.show_panel(panel_ids[index])

    def _show_plot_page(self, index: int) -> None:
        self.workspace_manager.show_panel(
            ("runs.comparison", "compare.points")[index]
        )

    def _show_analysis_page(self, index: int) -> None:
        self.workspace_manager.show_panel(
            (
                "analysis.statistics",
                "data.raw",
                "maths.channels",
                "analysis.best_fit_formulas",
            )[index]
        )

    def _show_raw_data(self) -> None:
        self.raw_data_panel.refresh()
        self.workspace_manager.show_panel("data.raw")

    def _show_requirements_page(self, index: int) -> None:
        self.requirements_panel.setCurrentIndex(index)
        self.workspace_manager.show_panel("requirements.limits")

    def _export_selected_data(self) -> None:
        self._show_analysis_page(1)
        self.raw_data_panel.export_selected_data()

    def _refresh_requirements(self) -> None:
        self._show_requirements_page(1)
        self.limits_panel.refresh()
        self.limits_panel.refresh_margins()
        self._generate_plot()
        self._show_status("Requirements and margin summary refreshed.")

    def _refresh_engineering_notes(self) -> None:
        self._show_lower_page(self.LOWER_NOTES_INDEX)
        self.notes_panel.refresh_report()
        self._show_status("Engineering notes report text refreshed.")

    def _clear_engineering_notes(self) -> None:
        self._show_lower_page(self.LOWER_NOTES_INDEX)
        if self.notes_panel.clear_notes():
            self._show_status("Engineering notes cleared.")

    def _copy_engineering_notes(self) -> None:
        self._show_lower_page(self.LOWER_NOTES_INDEX)
        self.notes_panel.refresh_report()
        text = self.notes_panel.report_text.toPlainText()
        QGuiApplication.clipboard().setText(text)
        self._show_status("Engineering notes copied to the clipboard.")

    def _clear_plot(self) -> None:
        result = self.plot_workspace.clear_plot()
        self._plot_generated = False
        self._plot_display_frozen = False
        self._plot_profile_snapshots.pop(self.vm.state.active_plot_profile_index, None)
        self.cursor_panel.refresh()
        self._refresh_best_fit_formulas()
        self.app_status.set_plot_status(PlotStatus.NO_PLOT)
        self._show_status(result.message)

    def open_settings(self) -> None:
        global SettingsDialog
        if SettingsDialog is None:
            from .widgets.settings_dialog import SettingsDialog as _SettingsDialog

            SettingsDialog = _SettingsDialog

        dialog = SettingsDialog(self.vm.settings, self)
        if dialog.exec():
            self._experience_mode = UserExperienceMode.from_value(
                self.settings_manager.get("general_ui", "user_experience_mode")
            )
            self._apply_user_experience_mode()
            self._apply_theme()
            self._configure_autosave_timer()
            self._show_status("Settings saved.")

    def show_workflow_help(self) -> None:
        global HelpDialog
        if self._help_dialog is None:
            if HelpDialog is None:
                from .widgets.help_dialog import HelpDialog as _HelpDialog

                HelpDialog = _HelpDialog

            self._help_dialog = HelpDialog(self, self.vm.settings.theme_name())
        self._help_dialog.show()
        self._help_dialog.raise_()
        self._help_dialog.activateWindow()

    def save_session(self) -> bool:
        """Save the current session, returning ``True`` only when a file was written.

        Returns ``False`` when the user cancels the file dialog or the save fails,
        so callers such as the close handler can keep the app open.
        """
        initial_dir = self._save_session_initial_path()
        path = qt_file_dialogs.save_session_file(self, initial_dir)
        if not path:
            return False
        qt_widget_helpers.remember_session_directory(self.settings_manager, path)
        self._capture_current_plot_profile()
        result = self.vm.save_session(path)
        if result.ok:
            self._current_session_path = str(getattr(result, "payload", None) or path)
            self.vm.register_recent_session(self._current_session_path)
            self._retire_active_recovery()
        qt_message_service.show_result(self, "Save Session", result)
        self._show_status(result.message)
        return bool(result.ok)

    def _retire_active_recovery(self) -> None:
        recovery_path = self._active_recovery_path
        self._active_recovery_path = None
        if recovery_path is None:
            return
        try:
            recovery_path.unlink(missing_ok=True)
        except OSError:
            self.app_status.set_autosave("Recovery cleanup failed", failed=True)
        self._refresh_dashboard()

    def _save_session_initial_path(self) -> str:
        if self._current_session_path:
            return self._current_session_path
        return qt_widget_helpers.save_session_initial_directory(
            self.settings_manager,
            self.vm.state.filepath,
        )

    def _has_unsaved_changes(self) -> bool:
        return bool(self.vm.state.has_data and self.vm.state.is_dirty)

    def _save_custom_workspace(self) -> None:
        self.workspace_manager.save_custom_layout()
        self.app_status.set_workspace("Custom")
        self._show_status("Custom workspace layout saved.")

    def _apply_workspace_preset(self, preset: WorkspacePreset) -> None:
        self.workspace_manager.apply_preset(preset)
        self.app_status.set_workspace(preset.value.replace("_", " ").title())
        self.app_status.show_message(
            f"{preset.value.replace('_', ' ').title()} workspace applied."
        )

    def _restore_custom_workspace(self) -> None:
        try:
            self.workspace_manager.apply_preset(WorkspacePreset.CUSTOM)
            self.app_status.set_workspace("Custom")
            self._show_status("Custom workspace applied.")
        except ValueError as exc:
            self._show_status(str(exc))

    def _float_plot_workspace(self) -> None:
        self.workspace_manager.float_panel("plot.workspace")
        self._show_status("Plot Workspace opened separately.")

    def _dock_plot_workspace(self) -> None:
        self.workspace_manager.dock_panel("plot.workspace")
        self._show_status("Plot Workspace returned to the main window.")

    def _open_command_palette(self) -> None:
        if self._command_palette is None:
            self._command_palette = CommandPalette(self.command_manager, self)
        self._command_palette.open_palette()

    def _show_recent_menu(self) -> None:
        if not hasattr(self, "ribbon_manager"):
            return
        button = self.ribbon_manager.button_for("recent.open")
        menu = button.menu()
        if menu is None:
            return
        self.ribbon_manager._populate_menu(menu, self._populate_recent_menu)
        menu.popup(button.mapToGlobal(button.rect().bottomLeft()))

    def _accept_close(self, event) -> None:
        self.workspace_manager.save()
        self.workspace_manager.begin_shutdown()
        event.accept()

    def closeEvent(self, event) -> None:
        """Warn about unsaved changes before closing.

        Offers Save / Don't Save / Cancel when there are changes since the last
        save. Save keeps the app open if the save is cancelled or fails; Cancel
        aborts the close; Don't Save closes without saving.
        """
        # Fold any pending panel/Figure Options edits into the active profile so
        # changes made without regenerating are detected as unsaved.
        if self.vm.state.has_data:
            self._capture_current_plot_profile()
        if not self._has_unsaved_changes():
            self._accept_close(event)
            return
        choice = qt_message_service.confirm_unsaved_changes(
            self,
            "Unsaved Changes",
            "You have unsaved changes since your last save.\n\n"
            "Do you want to save them before closing?",
        )
        if choice == "cancel":
            event.ignore()
            return
        if choice == "save" and not self.save_session():
            event.ignore()
            return
        self._accept_close(event)

    def load_session(self) -> None:
        initial_dir = qt_widget_helpers.last_session_directory(self.settings_manager)
        path = qt_file_dialogs.open_session_file(self, initial_dir)
        if not path:
            return
        self._load_session_path(path)

    def _load_session_path(self, path: str, *, recovery: bool = False) -> bool:
        """Restore a session from ``path`` (shared by the dialog and recent menu)."""
        qt_widget_helpers.remember_session_directory(self.settings_manager, path)
        result, main_data_warning_shown = self._restore_session_with_optional_relink(path)
        if not result.ok:
            qt_message_service.error(self, "Load Session", result.message)
            self._show_status(result.message)
            self._show_dashboard()
            return False
        self._current_session_path = None if recovery else path
        if not recovery:
            self._active_recovery_path = None
            self.vm.register_recent_session(path)
        selection = result.payload if isinstance(result.payload, dict) else {}
        self._apply_loaded_session(selection)
        self._refresh_dashboard()
        if self.vm.state.has_data:
            self._show_workspace()
        else:
            self._show_dashboard()
        warnings = self._warnings_for_display(result.warnings, main_data_warning_shown)
        if warnings:
            qt_message_service.warning(self, "Load Session", "\n".join(warnings))
        self._show_status(result.message)
        return True

    # ------------------------------------------------------------------
    # Recent files / sessions menu
    # ------------------------------------------------------------------
    def _populate_recent_menu(self, menu: QMenu) -> None:
        """Fill the FILE ribbon 'Recent' drop-down from the viewmodel.

        Missing files are listed but disabled rather than removed, so the user
        can see what was there. Real entries carry the full path as action data
        and tool-tip; section headers are disabled, non-actionable rows.
        """
        recent_files = self.vm.recent_files()
        recent_sessions = self.vm.recent_sessions()
        if not recent_files and not recent_sessions:
            empty = menu.addAction("No recent items")
            empty.setEnabled(False)
            return
        if recent_files:
            header = menu.addAction("Data Files")
            header.setEnabled(False)
            for path in recent_files:
                self._add_recent_action(menu, path, self._open_recent_file)
        if recent_sessions:
            if recent_files:
                menu.addSeparator()
            header = menu.addAction("Sessions")
            header.setEnabled(False)
            for path in recent_sessions:
                self._add_recent_action(menu, path, self._open_recent_session)

    def _add_recent_action(self, menu: QMenu, path: str, handler: Callable[[str], None]) -> None:
        action = menu.addAction(Path(path).name or path)
        action.setData(path)
        action.setToolTip(path)
        if Path(path).exists():
            action.triggered.connect(lambda _checked=False, p=path: handler(p))
        else:
            action.setEnabled(False)

    def _open_recent_file(self, path: str) -> None:
        if not Path(path).exists():
            self._show_status(f"File no longer exists: {path}")
            return
        self.data_panel.load_path(path)

    def _open_recent_session(self, path: str) -> None:
        if not Path(path).exists():
            self._show_status(f"Session no longer exists: {path}")
            return
        self._load_session_path(path)

    def _startup_behaviour(self) -> str:
        try:
            return str(self.settings_manager.get("general_ui", "startup_behaviour"))
        except (KeyError, AttributeError):
            return "blank"

    def _open_last_session_at_startup(self) -> None:
        if self.vm.state.has_data:
            return
        for path in self.vm.recent_sessions():
            if Path(path).exists():
                self._load_session_path(path)
                return
        self._show_dashboard()

    def _show_dashboard(self) -> None:
        if self.vm.state.has_data:
            return
        self._refresh_dashboard()
        self.content_stack.setCurrentWidget(self.dashboard)

    def _show_workspace(self) -> None:
        self.content_stack.setCurrentWidget(self.workspace_manager.widget)

    def _refresh_dashboard(self) -> None:
        recent_files = self.vm.recent_files()
        recent_sessions = self.vm.recent_sessions()
        self.dashboard.set_recent_items(recent_files, recent_sessions)
        try:
            dismissed = self.settings_manager.get("recovery", "dismissed_fingerprints")
        except (KeyError, AttributeError):
            dismissed = []
        dismissed_fingerprints = dismissed if isinstance(dismissed, list) else []
        self._recovery_candidate = find_recovery_candidate(
            recent_files,
            recent_sessions,
            [str(value) for value in dismissed_fingerprints],
        )
        if self._recovery_candidate is None:
            self.dashboard.set_recovery("")
            return
        modified = time.strftime(
            "%Y-%m-%d %H:%M",
            time.localtime(self._recovery_candidate.modified_epoch),
        )
        self.dashboard.set_recovery(str(self._recovery_candidate.path), modified)

    def _recover_from_dashboard(self, path: str) -> None:
        candidate = self._recovery_candidate
        if candidate is None or candidate.path != Path(path) or not candidate.path.exists():
            self._refresh_dashboard()
            self._show_status("The recovery file is no longer available.")
            return
        if not self._load_session_path(path, recovery=True):
            return
        self._active_recovery_path = candidate.path
        self.vm.state.is_dirty = True
        self._sync_durable_status()
        self._show_status("Recovery loaded. Save the session to keep this work.")

    def _dismiss_dashboard_recovery(self, path: str) -> None:
        candidate = self._recovery_candidate
        if candidate is None or candidate.path != Path(path):
            self._refresh_dashboard()
            return
        try:
            dismissed = self.settings_manager.get("recovery", "dismissed_fingerprints")
        except (KeyError, AttributeError):
            dismissed = []
        fingerprints = [str(value) for value in dismissed] if isinstance(dismissed, list) else []
        fingerprints = [value for value in fingerprints if value != candidate.fingerprint]
        fingerprints.append(candidate.fingerprint)
        self.settings_manager.set("recovery", "dismissed_fingerprints", fingerprints[-20:])
        try:
            self.settings_manager.save()
        except RuntimeError:
            pass
        self._refresh_dashboard()
        self._show_status("Recovery dismissed. The recovery file was not deleted.")

    # ------------------------------------------------------------------
    # Drag-and-drop file open
    # ------------------------------------------------------------------
    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self._first_supported_drop_path(event) is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event: QDropEvent) -> None:
        path = self._first_supported_drop_path(event)
        if path is None:
            event.ignore()
            return
        event.acceptProposedAction()
        if Path(path).suffix.lower() in self.SESSION_DROP_SUFFIXES:
            self._load_session_path(path)
        else:
            self.data_panel.load_path(path)
        self._show_status(f"Opened via drag-and-drop: {path}")

    def _first_supported_drop_path(self, event: Any) -> Optional[str]:
        """Return the first dropped local file with a supported extension.

        Only the first matching file is opened; additional dropped files are
        ignored for now. Batch import (a later update) is the intended hook for
        turning multi-file drops into runs.
        """
        mime = event.mimeData()
        if not mime.hasUrls():
            return None
        supported = self.DATA_DROP_SUFFIXES + self.SESSION_DROP_SUFFIXES
        for url in mime.urls():
            local = url.toLocalFile()
            if local and Path(local).suffix.lower() in supported:
                return local
        return None

    # ------------------------------------------------------------------
    # Auto-save
    # ------------------------------------------------------------------
    def _configure_autosave_timer(self) -> None:
        """Start or stop the auto-save poll timer to match current settings."""
        if self._auto_save_enabled():
            if not self._autosave_timer.isActive():
                self._autosave_timer.start()
        else:
            self._autosave_timer.stop()

    def _auto_save_enabled(self) -> bool:
        try:
            return bool(self.settings_manager.get("general_ui", "auto_save_enabled"))
        except (KeyError, AttributeError):
            return False

    def _auto_save_interval_minutes(self) -> int:
        try:
            return int(self.settings_manager.get("general_ui", "auto_save_interval_minutes"))
        except (KeyError, ValueError, TypeError, AttributeError):
            return 10

    def _is_editing_cell(self) -> bool:
        table = getattr(self.raw_data_panel, "table", None)
        if table is None:
            return False
        try:
            return table.state() == QAbstractItemView.State.EditingState
        except Exception:
            return False

    def _on_autosave_tick(self) -> None:
        """Auto-save the session when due, dirty, and safe to do so.

        Silent by design: progress is reported only on the status bar so the
        background save never interrupts the user with a modal dialog.
        """
        if not self._auto_save_enabled():
            return
        if self.vm.state.df is None or not self.vm.state.is_dirty:
            return
        if self._is_editing_cell():
            return
        if not self.vm.auto_save_due(self._last_autosave_epoch, time.time(), self._auto_save_interval_minutes()):
            return
        target = self.vm.auto_save_target_path(self._current_session_path)
        self._capture_current_plot_profile()
        result = self.vm.save_session(target, mark_clean=False)
        self._last_autosave_epoch = time.time()
        if result.ok:
            saved_at = time.strftime("%H:%M:%S")
            self.app_status.set_autosave(f"Recovery saved {saved_at}")
            self._show_status(f"Auto-saved at {saved_at}")
        else:
            self.app_status.set_autosave("Auto-save failed", failed=True)
            self._show_status(f"Auto-save failed: {result.message}")

    def _apply_loaded_session(self, selection: dict) -> None:
        self._plot_profile_snapshots.clear()
        if self.vm.state.is_manual_source:
            self.data_panel.show_manual_session()
        else:
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

    def _needs_main_data_relink(self, result) -> bool:
        return self.vm.needs_main_data_relink(result)

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
        result = self._restore_plot_from_snapshot(profile, appearance)
        if result is None:
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

    def _restore_plot_from_snapshot(self, profile: dict, appearance: dict) -> Any:
        snapshot = self._plot_profile_snapshots.get(self.vm.state.active_plot_profile_index, {})
        plot_data = snapshot.get("plot_data")
        if plot_data is None:
            return None
        primary_y = list(profile.get("y_columns", []))
        secondary_y = list(profile.get("secondary_y_columns", []))
        result = self.plot_workspace.render_plot_data(
            plot_data,
            str(profile.get("x_column", "")),
            limit_lines=self._overlay_limit_lines(),
            secondary_y=secondary_y,
            plot_kind=str(profile.get("plot_kind", "Line")),
            channel_colours=self.vm.persistent_plot_channel_colours(primary_y, secondary_y),
            channel_styles=self.vm.active_legend_channel_overrides(),
            axis_tick_settings=profile.get("axis_ticks", {}) if isinstance(profile.get("axis_ticks"), dict) else {},
            annotations=list(profile.get("annotations", [])) if isinstance(profile.get("annotations"), list) else [],
            **self._appearance_kwargs(appearance),
        )
        if result.ok:
            self._last_plot_selection = None
            self._cache_active_plot_snapshot(result)
            self._plot_display_frozen = True
        return result

    def _on_legend_channel_style_changed(self, channel: str, style: dict) -> None:
        result = self.vm.update_active_legend_channel_override(channel, style)
        if not result.ok:
            qt_message_service.warning(self, "Legend Channel", result.message)
            self._show_status(result.message)
            return
        appearance = self.plot_workspace.current_axis_appearance() if self._plot_generated else {}
        plot_result = self._generate_plot(appearance)
        if plot_result is None:
            self._show_status(result.message)
            return
        if not plot_result.ok:
            qt_message_service.warning(self, "Legend Channel", plot_result.message)
            self.app_status.set_plot_status(PlotStatus.ERROR, plot_result.message)
            self._show_status(plot_result.message)
            return
        self._plot_generated = True
        self.app_status.set_plot_status(PlotStatus.CURRENT)
        self._show_status(result.message)

    def _on_annotations_changed(self) -> None:
        self.vm.ensure_plot_profiles()
        index = self.vm.state.active_plot_profile_index
        if not 0 <= index < len(self.vm.state.plot_profiles):
            return
        self.vm.state.plot_profiles[index]["annotations"] = self.plot_workspace.current_annotations()
        self.vm.state.is_dirty = True
        self.app_status.set_plot_status(PlotStatus.CURRENT)
        self._show_status("Plot annotations updated.")

    def _on_legend_channel_visibility_changed(self, channel: str, hidden: bool) -> None:
        result = self.vm.update_active_legend_channel_override(channel, {"channel": channel, "hidden": hidden})
        if not result.ok:
            qt_message_service.warning(self, "Legend Channel", result.message)
            self._show_status(result.message)
            return
        appearance = self.plot_workspace.current_axis_appearance() if self._plot_generated else {}
        plot_result = self._generate_plot(appearance)
        if plot_result is None:
            self._show_status(result.message)
            return
        if not plot_result.ok:
            qt_message_service.warning(self, "Legend Channel", plot_result.message)
            self.app_status.set_plot_status(PlotStatus.ERROR, plot_result.message)
            self._show_status(plot_result.message)
            return
        self._plot_generated = True
        action = "Hidden" if hidden else "Shown"
        self.app_status.set_plot_status(PlotStatus.CURRENT)
        self._show_status(f"{action} '{channel}'.")

    def _on_file_loaded(self, columns: list[str]) -> None:
        suggested_x = self.vm.data_loading.suggested_x_column(columns)
        self._active_recovery_path = None
        self._current_session_path = None
        self._plot_generated = False
        self._plot_display_frozen = False
        self._last_plot_selection = None
        self.vm.reset_plot_profiles()
        self._plot_profile_snapshots.clear()
        self._sync_plot_tabs()
        self.plot_workspace.clear_plot()
        self.cursor_panel.refresh()
        self.axis_panel.set_columns(self._plottable_columns(), suggested_x, maths_channel_names=self._maths_channel_names())
        self.vm.set_current_x_axis(self.axis_panel.x_column())
        self.statistics_panel.set_statistics(self.vm.plot_workspace.statistics([]))
        self.raw_data_panel.clear()
        self.maths_panel.clear_form()
        self.maths_panel.refresh()
        self.limits_panel.refresh()
        self.notes_panel.load_from_state()
        self.runs_panel.refresh()
        loaded_path = self.vm.state.filepath
        if loaded_path:
            self.vm.register_recent_file(str(loaded_path))
        self._refresh_dashboard()
        self._show_workspace()
        self.app_status.set_plot_status(PlotStatus.NO_PLOT)
        self._show_status(f"Loaded {len(columns)} columns. Select channels and generate a plot.")

    def _on_sheet_changed(self, columns: list[str]) -> None:
        self._capture_current_plot_profile()
        self._plot_display_frozen = self._plot_generated
        self._last_plot_selection = None
        self.axis_panel.update_columns(self._plottable_columns(), maths_channel_names=self._maths_channel_names())
        self.vm.set_current_x_axis(self.axis_panel.x_column())
        self.statistics_panel.set_statistics(self.vm.plot_workspace.statistics([]))
        self.raw_data_panel.clear()
        self.maths_panel.refresh()
        self.limits_panel.refresh()
        self.notes_panel.load_from_state()
        self.runs_panel.refresh()
        self.cursor_panel.refresh()
        self._refresh_best_fit_formulas()
        sheet_name = self.vm.state.sheet_name or "selected sheet"
        self._show_status(
            f"Loaded sheet '{sheet_name}' with {len(columns)} columns. Existing plots were left unchanged."
        )

    def _on_generate_plot(self) -> None:
        appearance = None
        axis_tick_settings = None
        current_selection = self._current_plot_selection_signature()
        if self._plot_generated and self._last_plot_selection and current_selection:
            if self.vm.plot_selection_preserves_appearance(self._last_plot_selection, current_selection):
                appearance = self.plot_workspace.current_axis_appearance()
                axis_tick_settings = self.plot_workspace.axis_tick_setting_texts()
            else:
                axis_tick_settings = {}
        result = self._generate_plot(appearance, axis_tick_settings=axis_tick_settings)
        if result is None:
            return
        if not result.ok:
            qt_message_service.warning(self, "Plot", result.message)
            self.app_status.set_plot_status(PlotStatus.ERROR, result.message)
            self._show_status(result.message)
            return
        self._plot_generated = True
        self._update_statistics(self.axis_panel.all_selected_y())
        self.raw_data_panel.refresh()
        self.limits_panel.refresh_margins()
        self.runs_panel.update_statistics()
        self._refresh_best_fit_formulas()
        self.app_status.set_plot_status(PlotStatus.CURRENT)
        self._show_status(result.message)

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
            self.app_status.set_plot_status(PlotStatus.ERROR, result.message)
            self._show_status(result.message)
            return
        self._last_plot_selection = None
        self.runs_panel.update_statistics()
        message = result.message
        if skipped:
            message += f" Skipped {len(skipped)} missing/non-numeric channel(s)."
        self.runs_panel.set_status(message)
        self.app_status.set_plot_status(PlotStatus.CURRENT)
        self._show_status(message)

    def _generate_plot(
        self,
        appearance: dict | None = None,
        *,
        axis_tick_settings: dict[str, object] | None = None,
    ):
        """Render the current axis selection onto the canvas (shared by plot/limit refresh).

        Returns the ``OperationResult`` or ``None`` when there is nothing selected.
        ``appearance`` supplies saved Figure Options title/labels/limits on restore.
        """
        selection = self._current_plot_selection_signature()
        if selection is None:
            return None
        x_col = str(selection["x_column"])
        primary_y = list(selection["primary_y"])
        secondary_y = list(selection["secondary_y"])
        y_cols = primary_y + [column for column in secondary_y if column not in primary_y]
        if not x_col or not y_cols:
            return None
        xmin = selection["xmin"]
        xmax = selection["xmax"]
        use_filter = bool(selection["use_filter"])
        cutoff = selection["cutoff"]
        order = int(selection["order"])
        channel_colours = self.vm.persistent_plot_channel_colours(primary_y, secondary_y)
        channel_styles = self.vm.active_legend_channel_overrides()
        tick_settings = self.plot_workspace.axis_tick_setting_texts() if axis_tick_settings is None else axis_tick_settings
        profile = self.vm.state.active_plot_profile() or {}
        annotations = profile.get("annotations", []) if isinstance(profile, dict) else []
        result = self.plot_workspace.generate_plot(
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
            channel_styles=channel_styles,
            axis_tick_settings=tick_settings,
            annotations=annotations if isinstance(annotations, list) else [],
            **self._appearance_kwargs(appearance),
        )
        if result.ok:
            self._last_plot_selection = dict(selection)
            self._plot_display_frozen = False
            self._cache_active_plot_snapshot(result)
            self.app_status.set_plot_status(PlotStatus.CURRENT)
        else:
            self.app_status.set_plot_status(PlotStatus.ERROR, result.message)
        self._sync_durable_status()
        return result

    def _current_plot_selection_signature(self) -> dict[str, Any] | None:
        x_col = self.axis_panel.x_column()
        primary_y = self.axis_panel.selected_y()
        secondary_y = self.axis_panel.selected_secondary_y()
        y_cols = primary_y + [column for column in secondary_y if column not in primary_y]
        if not x_col or not y_cols:
            return None
        xmin, xmax = self.axis_panel.analysis_window()
        use_filter, cutoff, order = self.axis_panel.filter_settings()
        return {
            "x_column": x_col,
            "primary_y": list(primary_y),
            "secondary_y": list(secondary_y),
            "xmin": xmin,
            "xmax": xmax,
            "use_filter": bool(use_filter),
            "cutoff": cutoff,
            "order": order,
        }

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

    def _plottable_columns(self) -> list[str]:
        """Numeric source columns plus Maths Channels, for the axis selectors.

        Text columns are excluded so only numeric-compatible channels are offered
        for plotting; Maths Channels (numeric, tracked outside the registry) are
        appended.
        """
        numeric = self.vm.state.numeric_column_names()
        maths = [name for name in self._maths_channel_names() if name not in numeric]
        return numeric + maths

    def _on_channels_changed(self) -> None:
        columns = self._plottable_columns()
        if columns:
            self.axis_panel.update_columns(columns, maths_channel_names=self._maths_channel_names())
        self.raw_data_panel.refresh()

    def _on_cursor_window(self, xmin: float, xmax: float) -> None:
        self.axis_panel.xmin_edit.setText(f"{xmin:g}")
        self.axis_panel.xmax_edit.setText(f"{xmax:g}")
        result = self._generate_plot()
        if result is not None and result.ok:
            self.app_status.set_plot_status(PlotStatus.CURRENT)
            self._show_status(
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
            self._show_status(result.message)
            return
        self._show_status(result.message)

    def _update_statistics(self, y_cols: list[str]) -> None:
        decimals = int(self.vm.settings.get("axis_scaling", "decimal_places_statistics", 4) or 4)
        stats = self.vm.plot_workspace.statistics(y_cols, decimals)
        self.statistics_panel.set_statistics(stats)

    def _refresh_best_fit_formulas(self) -> None:
        self.best_fit_formulas_panel.set_rows(self.plot_workspace.best_fit_formula_rows())
