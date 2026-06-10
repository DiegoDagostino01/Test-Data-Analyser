"""Framework-independent domain models for the Test Data Analyser.

This package is the canonical home for the application's domain dataclasses:
plot/profile/session state, requirement limits, engineering notes, runs, and
calculated channels. Nothing in this package may import a UI framework
(Tkinter or PySide6); the models are intended to be reused by the current Qt UI
and any future UI front end alike.
"""
from __future__ import annotations

from .engineering_notes import EngineeringNotes
from .limits import LimitLine, LimitPoint
from .models import PlotData
from .plot_profile import (
    PlotProfile,
    normalise_plot_profile,
    plot_profile_from_dict,
    plot_profile_to_dict,
)
from .run_model import CalculatedChannelDefinition, ComparisonSettings, RunMetadata
from .session import SessionState
from .settings import (
    AnalysisWindow,
    AxisLimits,
    AxisTickSettings,
    FilterSettings,
    LegendSettings,
    ManualLabelFlags,
    RawDataViewSettings,
)

__all__ = [
    "AnalysisWindow",
    "AxisLimits",
    "AxisTickSettings",
    "CalculatedChannelDefinition",
    "ComparisonSettings",
    "EngineeringNotes",
    "FilterSettings",
    "LegendSettings",
    "LimitLine",
    "LimitPoint",
    "ManualLabelFlags",
    "PlotData",
    "PlotProfile",
    "RawDataViewSettings",
    "RunMetadata",
    "SessionState",
    "normalise_plot_profile",
    "plot_profile_from_dict",
    "plot_profile_to_dict",
]
