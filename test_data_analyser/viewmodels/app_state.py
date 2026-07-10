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

from ..core.data_io import numeric_series
from ..core.indexing import clamp_index
from ..domain import SOURCE_EXCEL, SOURCE_MANUAL, ChannelRegistry, ComparisonSettings


@dataclass
class AppState:
    df: Optional[pd.DataFrame] = None
    filepath: Optional[Path] = None
    root_file_directory: str = ""
    is_dirty: bool = False
    current_x_axis: str = ""
    sheet_name: str = ""
    data_source_type: str = SOURCE_EXCEL
    channel_registry: ChannelRegistry = field(default_factory=ChannelRegistry)
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
    _numeric_cache: dict[str, pd.Series] = field(default_factory=dict, repr=False, compare=False)
    _numeric_cache_token: Any = field(default=None, repr=False, compare=False)

    # ------------------------------------------------------------------
    # Derived, read-only views
    # ------------------------------------------------------------------
    @property
    def has_data(self) -> bool:
        return self.df is not None

    @property
    def is_manual_source(self) -> bool:
        return self.data_source_type == SOURCE_MANUAL

    def column_names(self) -> list[str]:
        if self.df is None:
            return []
        return [str(column) for column in self.df.columns]

    def numeric_column_names(self) -> list[str]:
        """Return the plottable (numeric) column names.

        Uses the channel registry's per-column data-type classification when it
        is populated, falling back to every column when no registry has been
        built yet (e.g. legacy sessions before reconciliation).
        """
        if self.df is None:
            return []
        if self.channel_registry.columns:
            return [name for name in self.channel_registry.numeric_names() if name in self.df.columns]
        return self.column_names()

    def numeric_column(self, name: str) -> pd.Series:
        """Return the tolerant numeric coercion of column ``name``, cached.

        The cache is scoped to the current dataframe: it is dropped automatically
        when the dataframe object or its shape changes, and explicitly via
        :meth:`invalidate_numeric_cache` after in-place cell edits that keep the
        same shape. This avoids repeating the expensive text->number coercion for
        the same column across plotting, statistics, and range calculations.
        """
        if self.df is None or name not in self.df.columns:
            return pd.Series(dtype=float)
        token = (id(self.df), self.df.shape)
        if token != self._numeric_cache_token:
            self._numeric_cache.clear()
            self._numeric_cache_token = token
        series = self._numeric_cache.get(name)
        if series is None:
            series = numeric_series(self.df[name])
            self._numeric_cache[name] = series
        return series

    def invalidate_numeric_cache(self, column: Optional[str] = None) -> None:
        """Drop cached numeric coercions after an in-place dataframe edit.

        Pass ``column`` to drop a single column, or omit it to clear every cached
        column (used when an edit may touch several columns at once).
        """
        if column is None:
            self._numeric_cache.clear()
        else:
            self._numeric_cache.pop(column, None)

    def channel_id_for_name(self, name: str) -> Optional[str]:
        return self.channel_registry.id_for_name(name)

    def name_for_channel_id(self, channel_id: str) -> Optional[str]:
        return self.channel_registry.name_for_id(channel_id)

    def resolve_ids_to_names(self, channel_ids: list[str]) -> list[str]:
        return self.channel_registry.ids_to_names(channel_ids)

    def resolve_names_to_ids(self, names: list[str]) -> list[str]:
        return self.channel_registry.names_to_ids(names)

    def active_plot_profile(self) -> Optional[dict[str, Any]]:
        if not self.plot_profiles:
            return None
        index = clamp_index(self.active_plot_profile_index, len(self.plot_profiles))
        return self.plot_profiles[index]

    def active_run(self) -> Optional[dict[str, Any]]:
        if not (0 <= self.active_run_index < len(self.runs)):
            return None
        return self.runs[self.active_run_index]
