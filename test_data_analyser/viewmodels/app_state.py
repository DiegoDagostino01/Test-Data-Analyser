"""UI-independent application state.

``AppState`` is the single source of truth for the framework-independent state
that the viewmodels coordinate: the loaded dataframe, source file/sheet, plot
profiles, runs, calculated channels, limits, notes, and comparison settings. It
holds no Tkinter or PySide6 objects. The data shapes intentionally match the
saved-session dictionaries so domain/service helpers and saved sessions stay
compatible.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import pandas as pd

from ..domain import ComparisonSettings


@dataclass
class AppState:
    df: Optional[pd.DataFrame] = None
    filepath: Optional[Path] = None
    sheet_name: str = ""
    plot_profiles: list[dict[str, Any]] = field(default_factory=list)
    active_plot_profile_index: int = 0
    runs: list[dict[str, Any]] = field(default_factory=list)
    active_run_index: int = -1
    calculated_channels: dict[str, dict[str, Any]] = field(default_factory=dict)
    limit_lines: list[dict[str, Any]] = field(default_factory=list)
    active_limit_line_index: int = 0
    engineering_notes: dict[str, str] = field(default_factory=dict)
    comparison: ComparisonSettings = field(default_factory=ComparisonSettings)
    settings_manager: Any = None

    # ------------------------------------------------------------------
    # Derived, read-only views
    # ------------------------------------------------------------------
    @property
    def has_data(self) -> bool:
        return self.df is not None

    def column_names(self) -> list[str]:
        if self.df is None:
            return []
        return [str(column) for column in self.df.columns]

    def active_plot_profile(self) -> Optional[dict[str, Any]]:
        if not self.plot_profiles:
            return None
        index = max(0, min(self.active_plot_profile_index, len(self.plot_profiles) - 1))
        return self.plot_profiles[index]

    def active_run(self) -> Optional[dict[str, Any]]:
        if not (0 <= self.active_run_index < len(self.runs)):
            return None
        return self.runs[self.active_run_index]
