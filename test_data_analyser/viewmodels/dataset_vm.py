"""Dataset editing viewmodel.

Coordinates source-agnostic structural edits — add/rename/delete columns and
rows plus cell edits — over :class:`AppState`'s dataframe and its stable-ID
:class:`~test_data_analyser.domain.ChannelRegistry`. When a column is renamed or
deleted it propagates the change across plot profiles, the current X-axis, Maths
Channel formulas, and limit lines so every reference stays consistent.

Framework-independent: it returns :class:`OperationResult` and mutates
``AppState`` in place. The Qt panel collects edits and triggers any plot/maths
refresh after calling these methods.
"""
from __future__ import annotations

from typing import Any, Iterable, Optional

from ..services import dataset_service, maths_channel_service
from ..services.plot_render_service import normalise_channel_name
from ..services.results import OperationResult
from .app_state import AppState


class DatasetViewModel:
    def __init__(self, state: AppState) -> None:
        self.state = state

    # ------------------------------------------------------------------
    # Views
    # ------------------------------------------------------------------
    def editable_columns(self) -> list[dict[str, str]]:
        """Return the editable source columns as ``{id, display_name, data_type}``."""
        return [
            {"id": spec.id, "display_name": spec.display_name, "data_type": spec.data_type}
            for spec in self.state.channel_registry.columns
        ]

    # ------------------------------------------------------------------
    # Column operations
    # ------------------------------------------------------------------
    def add_column(self, display_name: str, *, data_type: str = "numeric") -> OperationResult:
        result = dataset_service.add_column(
            self.state.df, self.state.channel_registry, display_name, data_type=data_type
        )
        if result.ok and isinstance(result.payload, dict):
            self.state.df = result.payload.get("df", self.state.df)
            self.state.is_dirty = True
        return result

    def rename_column(self, channel_id: str, new_display_name: str) -> OperationResult:
        spec = self.state.channel_registry.spec_for_id(channel_id)
        old_name = spec.display_name if spec is not None else None
        result = dataset_service.rename_column(
            self.state.df, self.state.channel_registry, channel_id, new_display_name
        )
        if result.ok and isinstance(result.payload, dict):
            self.state.df = result.payload.get("df", self.state.df)
            new_name = str(result.payload.get("new_name", new_display_name))
            if old_name and old_name != new_name:
                self._propagate_rename(old_name, new_name)
                self.state.is_dirty = True
        return result

    def delete_column(self, channel_id: str) -> OperationResult:
        spec = self.state.channel_registry.spec_for_id(channel_id)
        name = spec.display_name if spec is not None else None
        result = dataset_service.delete_column(self.state.df, self.state.channel_registry, channel_id)
        if result.ok and isinstance(result.payload, dict):
            self.state.df = result.payload.get("df", self.state.df)
            if name:
                result.warnings.extend(self._propagate_delete(name))
                self.state.is_dirty = True
        return result

    # ------------------------------------------------------------------
    # Row / cell operations
    # ------------------------------------------------------------------
    def add_row(self, at_index: Optional[int] = None) -> OperationResult:
        result = dataset_service.add_row(self.state.df, at_index=at_index)
        if result.ok and isinstance(result.payload, dict):
            self.state.df = result.payload["df"]
            self.state.is_dirty = True
        return result

    def delete_rows(self, indices: Iterable[int]) -> OperationResult:
        result = dataset_service.delete_rows(self.state.df, indices)
        if result.ok and isinstance(result.payload, dict):
            self.state.df = result.payload["df"]
            self.state.is_dirty = True
        return result

    def set_cell(self, channel_id: str, row_index: int, text: object) -> OperationResult:
        result = dataset_service.set_cell(
            self.state.df, self.state.channel_registry, channel_id, row_index, text
        )
        if result.ok and isinstance(result.payload, dict):
            self.state.df = result.payload["df"]
            self.state.is_dirty = True
        return result

    # ------------------------------------------------------------------
    # Rename / delete propagation
    # ------------------------------------------------------------------
    def _propagate_rename(self, old: str, new: str) -> None:
        if self.state.current_x_axis == old:
            self.state.current_x_axis = new
        for profile in self.state.plot_profiles:
            self._rename_in_profile(profile, old, new)
        self._rename_in_limit_lines(self.state.limit_lines, old, new)
        for definition in self.state.calculated_channels.values():
            if not isinstance(definition, dict):
                continue
            definition["formula"] = maths_channel_service.rename_column_in_formula(
                str(definition.get("formula", "")), old, new
            )
            created = definition.get("created_from_columns", [])
            if isinstance(created, list):
                definition["created_from_columns"] = [new if column == old else column for column in created]

    def _propagate_delete(self, name: str) -> list[str]:
        warnings: list[str] = []
        if self.state.current_x_axis == name:
            self.state.current_x_axis = ""
        affected_plots: set[str] = set()
        for profile in self.state.plot_profiles:
            if self._delete_in_profile(profile, name) and isinstance(profile, dict):
                profile_name = str(profile.get("name", "")).strip()
                if profile_name:
                    affected_plots.add(profile_name)
        affected_maths = [
            channel_name
            for channel_name, definition in self.state.calculated_channels.items()
            if isinstance(definition, dict)
            and name in (definition.get("created_from_columns", []) or [])
        ]
        if affected_plots:
            warnings.append(
                f'Deleted column "{name}" was used by plot(s): {", ".join(sorted(affected_plots))}.'
            )
        if affected_maths:
            warnings.append(
                f'Deleted column "{name}" is used by Maths Channel(s): '
                f'{", ".join(sorted(affected_maths))}. They will need updating.'
            )
        return warnings

    def _rename_in_profile(self, profile: Any, old: str, new: str) -> None:
        if not isinstance(profile, dict):
            return
        if profile.get("x_column") == old:
            profile["x_column"] = new
        for key in ("y_columns", "secondary_y_columns"):
            values = profile.get(key)
            if isinstance(values, list):
                profile[key] = [new if value == old else value for value in values]
        for line in profile.get("best_fit_lines", []) or []:
            if isinstance(line, dict) and line.get("channel") == old:
                line["channel"] = new
        self._rename_in_limit_lines(profile.get("limit_lines", []), old, new)
        legend = profile.get("legend")
        if isinstance(legend, dict):
            overrides = legend.get("channel_overrides")
            if isinstance(overrides, dict):
                entry = overrides.pop(normalise_channel_name(old), None)
                if entry is not None:
                    if isinstance(entry, dict) and entry.get("channel") == old:
                        entry["channel"] = new
                    overrides[normalise_channel_name(new)] = entry

    def _delete_in_profile(self, profile: Any, name: str) -> bool:
        if not isinstance(profile, dict):
            return False
        used = False
        if profile.get("x_column") == name:
            profile["x_column"] = ""
            used = True
        for key in ("y_columns", "secondary_y_columns"):
            values = profile.get(key)
            if isinstance(values, list) and name in values:
                profile[key] = [value for value in values if value != name]
                used = True
        best_fit = profile.get("best_fit_lines")
        if isinstance(best_fit, list):
            trimmed = [line for line in best_fit if not (isinstance(line, dict) and line.get("channel") == name)]
            if len(trimmed) != len(best_fit):
                profile["best_fit_lines"] = trimmed
                used = True
        legend = profile.get("legend")
        if isinstance(legend, dict):
            overrides = legend.get("channel_overrides")
            if isinstance(overrides, dict) and overrides.pop(normalise_channel_name(name), None) is not None:
                used = True
        return used

    @staticmethod
    def _rename_in_limit_lines(limit_lines: Any, old: str, new: str) -> None:
        if not isinstance(limit_lines, list):
            return
        for line in limit_lines:
            if isinstance(line, dict) and line.get("applies_to") == old:
                line["applies_to"] = new
