"""Column-reference propagation helpers.

Dataset edits can rename or delete a source column that is referenced by plot
profiles, Maths Channel definitions, legend overrides, and limit lines. This
service owns those framework-free reference updates; callers provide the mutable
state sections and then store the returned current-X-axis value.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from . import maths_channel_service
from .plot_render_service import normalise_channel_name


@dataclass(frozen=True)
class ColumnReferenceUpdate:
    current_x_axis: str
    warnings: list[str] = field(default_factory=list)


def propagate_column_rename(
    *,
    current_x_axis: str,
    plot_profiles: list[dict[str, Any]],
    calculated_channels: dict[str, dict[str, Any]],
    limit_lines: list[dict[str, Any]],
    old_name: str,
    new_name: str,
) -> ColumnReferenceUpdate:
    """Rename references to a source column across mutable session state."""
    updated_x_axis = new_name if current_x_axis == old_name else current_x_axis
    for profile in plot_profiles:
        _rename_in_profile(profile, old_name, new_name)
    _rename_in_limit_lines(limit_lines, old_name, new_name)
    for definition in calculated_channels.values():
        if not isinstance(definition, dict):
            continue
        definition["formula"] = maths_channel_service.rename_column_in_formula(
            str(definition.get("formula", "")), old_name, new_name
        )
        created = definition.get("created_from_columns", [])
        if isinstance(created, list):
            definition["created_from_columns"] = [new_name if column == old_name else column for column in created]
    return ColumnReferenceUpdate(current_x_axis=updated_x_axis)


def propagate_column_delete(
    *,
    current_x_axis: str,
    plot_profiles: list[dict[str, Any]],
    calculated_channels: dict[str, dict[str, Any]],
    name: str,
) -> ColumnReferenceUpdate:
    """Delete references to a source column across mutable session state."""
    updated_x_axis = "" if current_x_axis == name else current_x_axis
    affected_plots: set[str] = set()
    for profile in plot_profiles:
        if _delete_in_profile(profile, name) and isinstance(profile, dict):
            profile_name = str(profile.get("name", "")).strip()
            if profile_name:
                affected_plots.add(profile_name)
    affected_maths = [
        channel_name
        for channel_name, definition in calculated_channels.items()
        if isinstance(definition, dict)
        and name in (definition.get("created_from_columns", []) or [])
    ]
    warnings: list[str] = []
    if affected_plots:
        warnings.append(
            f'Deleted column "{name}" was used by plot(s): {", ".join(sorted(affected_plots))}.'
        )
    if affected_maths:
        warnings.append(
            f'Deleted column "{name}" is used by Maths Channel(s): '
            f'{", ".join(sorted(affected_maths))}. They will need updating.'
        )
    return ColumnReferenceUpdate(current_x_axis=updated_x_axis, warnings=warnings)


def _rename_in_profile(profile: Any, old_name: str, new_name: str) -> None:
    if not isinstance(profile, dict):
        return
    if profile.get("x_column") == old_name:
        profile["x_column"] = new_name
    for key in ("y_columns", "secondary_y_columns"):
        values = profile.get(key)
        if isinstance(values, list):
            profile[key] = [new_name if value == old_name else value for value in values]
    for line in profile.get("best_fit_lines", []) or []:
        if isinstance(line, dict) and line.get("channel") == old_name:
            line["channel"] = new_name
    _rename_in_limit_lines(profile.get("limit_lines", []), old_name, new_name)
    overrides = _legend_overrides(profile)
    if overrides is not None:
        entry = overrides.pop(normalise_channel_name(old_name), None)
        if entry is not None:
            if isinstance(entry, dict) and entry.get("channel") == old_name:
                entry["channel"] = new_name
            overrides[normalise_channel_name(new_name)] = entry


def _delete_in_profile(profile: Any, name: str) -> bool:
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
    overrides = _legend_overrides(profile)
    if overrides is not None and overrides.pop(normalise_channel_name(name), None) is not None:
        used = True
    return used


def _legend_overrides(profile: Any) -> dict[str, Any] | None:
    if isinstance(profile, dict):
        legend = profile.get("legend")
        if isinstance(legend, dict):
            overrides = legend.get("channel_overrides")
            if isinstance(overrides, dict):
                return overrides
    return None


def _rename_in_limit_lines(limit_lines: Any, old_name: str, new_name: str) -> None:
    if not isinstance(limit_lines, list):
        return
    for line in limit_lines:
        if isinstance(line, dict) and line.get("applies_to") == old_name:
            line["applies_to"] = new_name