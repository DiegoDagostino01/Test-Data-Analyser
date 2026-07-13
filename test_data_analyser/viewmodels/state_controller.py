"""Centralised AppState mutation helpers for viewmodels."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Optional

import pandas as pd

from ..domain import ChannelRegistry
from .app_state import AppState


@dataclass
class DatasetUndoSnapshot:
    description: str
    df: Optional[pd.DataFrame]
    channel_registry: dict[str, object]
    current_x_axis: str
    plot_profiles: list[dict[str, Any]]
    calculated_channels: dict[str, dict[str, Any]]
    limit_lines: list[dict[str, Any]]
    is_dirty: bool


@dataclass(frozen=True)
class DatasetCellUndo:
    description: str
    channel_id: str
    row_index: int
    old_value: Any
    old_dtype: Any
    old_data_type: str
    is_dirty: bool


class AppStateController:
    """Apply multi-field AppState mutations in one place."""

    def __init__(self, state: AppState) -> None:
        self.state = state

    def capture_dataset_snapshot(self, description: str) -> DatasetUndoSnapshot:
        df = None if self.state.df is None else self.state.df.copy(deep=True)
        return DatasetUndoSnapshot(
            description=description,
            df=df,
            channel_registry=deepcopy(self.state.channel_registry.to_dict()),
            current_x_axis=self.state.current_x_axis,
            plot_profiles=deepcopy(self.state.plot_profiles),
            calculated_channels=deepcopy(self.state.calculated_channels),
            limit_lines=deepcopy(self.state.limit_lines),
            is_dirty=self.state.is_dirty,
        )

    def restore_dataset_snapshot(self, snapshot: DatasetUndoSnapshot) -> None:
        self.state.df = None if snapshot.df is None else snapshot.df.copy(deep=True)
        self.state.channel_registry = ChannelRegistry.from_dict(snapshot.channel_registry)
        self.state.current_x_axis = snapshot.current_x_axis
        self.state.plot_profiles = deepcopy(snapshot.plot_profiles)
        self.state.calculated_channels = deepcopy(snapshot.calculated_channels)
        self.state.limit_lines = deepcopy(snapshot.limit_lines)
        self.state.is_dirty = snapshot.is_dirty
        self.state.invalidate_numeric_cache()

    def restore_dataset_cell(self, undo: DatasetCellUndo) -> bool:
        df = self.state.df
        spec = self.state.channel_registry.spec_for_id(undo.channel_id)
        if df is None or spec is None or spec.display_name not in df.columns:
            return False
        if not (0 <= undo.row_index < len(df)):
            return False
        name = spec.display_name
        restored = df[name].copy()
        restored.at[undo.row_index] = undo.old_value
        try:
            restored = restored.astype(undo.old_dtype)
        except (TypeError, ValueError):
            return False
        df[name] = restored
        spec.data_type = undo.old_data_type
        self.state.is_dirty = undo.is_dirty
        self.state.invalidate_numeric_cache(name)
        return True

    def apply_dataframe_payload(self, payload: dict[str, object]) -> bool:
        if "df" not in payload:
            return False
        self.state.df = payload.get("df")  # type: ignore[assignment]
        self.state.invalidate_numeric_cache()
        return True

    def set_plot_profiles(self, profiles: list[dict[str, Any]], active_index: int) -> None:
        self.state.plot_profiles = profiles
        self.state.active_plot_profile_index = active_index

    def reset_plot_workspace(self, profiles: list[dict[str, Any]], active_index: int) -> None:
        self.set_plot_profiles(profiles, active_index)
        self.state.current_x_axis = ""
        self.state.limit_lines = []
        self.state.active_limit_line_index = 0
        self.state.engineering_notes = {}

    def set_active_plot_profile(self, index: int, profile: dict[str, Any]) -> None:
        self.state.plot_profiles[index] = profile
        self.state.active_plot_profile_index = index

    def mark_dirty(self) -> None:
        self.state.is_dirty = True

    def set_current_x_axis(self, value: str) -> None:
        self.state.current_x_axis = value