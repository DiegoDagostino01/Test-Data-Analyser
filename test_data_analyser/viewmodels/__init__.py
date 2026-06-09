"""UI-independent viewmodels for the Test Data Analyser.

Viewmodels coordinate domain state (``AppState``) and the service layer. They
expose plain Python data structures, return structured :class:`OperationResult`
objects, hold UI-independent state, and must not import Tkinter or PySide6, open
file dialogs, or show message boxes.

These viewmodels are designed to be driven by the new PySide6 shell (Phase 4
onward); the existing Tkinter UI continues to operate during the migration.
"""
from __future__ import annotations

from .app_state import AppState
from .cursor_compare_vm import CursorCompareViewModel
from .data_loading_vm import DataLoadingViewModel
from .engineering_notes_vm import EngineeringNotesViewModel
from .limits_vm import LimitsViewModel
from .main_window_vm import MainWindowViewModel
from .maths_channels_vm import MathsChannelsViewModel
from .plot_workspace_vm import PlotWorkspaceViewModel
from .raw_data_vm import RawDataViewModel
from .runs_comparison_vm import RunsComparisonViewModel
from .settings_vm import SettingsViewModel

__all__ = [
    "AppState",
    "CursorCompareViewModel",
    "DataLoadingViewModel",
    "EngineeringNotesViewModel",
    "LimitsViewModel",
    "MainWindowViewModel",
    "MathsChannelsViewModel",
    "PlotWorkspaceViewModel",
    "RawDataViewModel",
    "RunsComparisonViewModel",
    "SettingsViewModel",
]
