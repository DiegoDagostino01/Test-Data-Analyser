"""Plot-profile list operations.

The service owns profile list decisions such as normalisation, unique naming,
active-index clamping, and CRUD result messages. Viewmodels remain responsible
for applying the returned update to AppState.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from ..core.indexing import clamp_index
from ..domain import normalise_plot_profile
from . import plot_render_service
from .results import OperationResult


@dataclass(frozen=True)
class PlotProfileListUpdate:
    profiles: list[dict[str, Any]]
    active_index: int
    result: OperationResult


def ensure_profiles(
    profiles: list[dict[str, Any]],
    active_index: int,
) -> tuple[list[dict[str, Any]], int]:
    """Return a non-empty normalised profile list and a valid active index."""
    if not profiles:
        normalised = [normalise_plot_profile({"name": "Plot 1"})]
    else:
        normalised = [normalise_plot_profile(profile) for profile in profiles]
    return normalised, clamp_index(active_index, len(normalised))


def reset_profiles() -> tuple[list[dict[str, Any]], int]:
    """Return the default one-plot workspace."""
    return [normalise_plot_profile({"name": "Plot 1"})], 0


def capture_working_profile(
    existing_profile: dict[str, Any],
    profile_index: int,
    *,
    x_column: str = "",
    y_columns: list[str] | None = None,
    secondary_y_columns: list[str] | None = None,
    title: str = "",
    x_label: str = "",
    y_label: str = "",
    secondary_y_label: str = "",
    plot_kind: str = "Line",
    auto_fit_axes: bool = True,
    axis_limits: dict[str, Any] | None = None,
    axis_ticks: dict[str, Any] | None = None,
    legend_settings: dict[str, Any] | None = None,
    best_fit_lines: list[dict[str, Any]] | None = None,
    annotations: list[dict[str, Any]] | None = None,
    analysis_window: dict[str, Any] | None = None,
    filter_settings: dict[str, Any] | None = None,
    generated: bool = False,
    limit_lines: list[dict[str, Any]] | None = None,
    engineering_notes: dict[str, str] | None = None,
) -> dict[str, object]:
    """Fold live selection, appearance, notes, and limits into one plot profile."""
    existing = dict(existing_profile) if isinstance(existing_profile, dict) else {}
    existing_legend = existing.get("legend", {}) if isinstance(existing.get("legend", {}), dict) else {}
    merged_legend = {**existing_legend, **dict(legend_settings or {})}
    return normalise_plot_profile(
        {
            **existing,
            "name": existing.get("name", f"Plot {profile_index + 1}"),
            "x_column": x_column,
            "y_columns": list(y_columns or []),
            "secondary_y_columns": list(secondary_y_columns or []),
            "title": title.strip() or "Engineering Test Data",
            "x_label": x_label.strip(),
            "y_label": y_label.strip() or "Selected Signals",
            "secondary_y_label": secondary_y_label.strip(),
            "plot_kind": plot_kind or "Line",
            "auto_fit_axes": auto_fit_axes,
            "axis_limits": dict(axis_limits or {}),
            "axis_ticks": dict(axis_ticks or {}),
            "legend": merged_legend,
            "best_fit_lines": [dict(line) for line in best_fit_lines or []],
            "annotations": [
                dict(annotation)
                for annotation in (annotations if annotations is not None else existing.get("annotations", []))
            ],
            "analysis_window": dict(analysis_window or {}),
            "filter": dict(filter_settings or {}),
            "generated": bool(generated),
            "manual_labels": {
                "title": bool(title.strip()),
                "x_label": bool(x_label.strip()),
                "y_label": bool(y_label.strip()),
                "secondary_y_label": bool(secondary_y_label.strip()),
            },
            "limit_lines": [dict(line) for line in limit_lines or []],
            "engineering_notes": dict(engineering_notes or {}),
        }
    )


def add_profile(
    profiles: list[dict[str, Any]],
    active_index: int,
    *,
    name: str = "",
    x_column: str = "",
) -> PlotProfileListUpdate:
    profiles, _active_index = ensure_profiles(profiles, active_index)
    profile_name = unique_profile_name(profiles, name.strip() or next_plot_name(profiles))
    updated = [
        *profiles,
        normalise_plot_profile({"name": profile_name, "x_column": str(x_column).strip()}),
    ]
    new_index = len(updated) - 1
    return PlotProfileListUpdate(
        updated,
        new_index,
        OperationResult.success(f"Created plot '{profile_name}'.", payload=new_index),
    )


def duplicate_profile(
    profiles: list[dict[str, Any]],
    active_index: int,
    *,
    index: int | None = None,
) -> PlotProfileListUpdate:
    profiles, active_index = ensure_profiles(profiles, active_index)
    source_index = clamp_index(active_index if index is None else index, len(profiles))
    source = deepcopy(profiles[source_index])
    source_name = str(source.get("name", f"Plot {source_index + 1}")).strip() or f"Plot {source_index + 1}"
    source["name"] = unique_profile_name(profiles, f"{source_name} Copy")
    insert_index = source_index + 1
    updated = [*profiles[:insert_index], normalise_plot_profile(source), *profiles[insert_index:]]
    return PlotProfileListUpdate(
        updated,
        insert_index,
        OperationResult.success(f"Duplicated plot '{source_name}'.", payload=insert_index),
    )


def rename_profile(
    profiles: list[dict[str, Any]],
    active_index: int,
    index: int,
    name: str,
) -> PlotProfileListUpdate:
    profiles, active_index = ensure_profiles(profiles, active_index)
    target_index = clamp_index(index, len(profiles))
    new_name = name.strip()
    if not new_name:
        return PlotProfileListUpdate(profiles, active_index, OperationResult.failure("Enter a plot name."))
    existing_names = {
        str(profile.get("name", "")).strip()
        for current, profile in enumerate(profiles)
        if current != target_index
    }
    if new_name in existing_names:
        return PlotProfileListUpdate(
            profiles,
            active_index,
            OperationResult.failure(f"A plot named '{new_name}' already exists."),
        )
    updated = [dict(profile) for profile in profiles]
    updated[target_index]["name"] = new_name
    return PlotProfileListUpdate(
        updated,
        active_index,
        OperationResult.success(f"Renamed plot to '{new_name}'.", payload=target_index),
    )


def delete_profile(
    profiles: list[dict[str, Any]],
    active_index: int,
    *,
    index: int | None = None,
) -> PlotProfileListUpdate:
    profiles, active_index = ensure_profiles(profiles, active_index)
    if len(profiles) <= 1:
        return PlotProfileListUpdate(
            profiles,
            active_index,
            OperationResult.failure("At least one plot must remain in the session."),
        )
    target_index = clamp_index(active_index if index is None else index, len(profiles))
    deleted = profiles[target_index]
    updated = [*profiles[:target_index], *profiles[target_index + 1:]]
    if active_index > target_index:
        active_index -= 1
    elif active_index == target_index:
        active_index = min(target_index, len(updated) - 1)
    active_index = clamp_index(active_index, len(updated))
    deleted_name = str(deleted.get("name", f"Plot {target_index + 1}"))
    return PlotProfileListUpdate(
        updated,
        active_index,
        OperationResult.success(f"Deleted plot '{deleted_name}'.", payload=active_index),
    )


def select_profile(
    profiles: list[dict[str, Any]],
    active_index: int,
    index: int,
) -> PlotProfileListUpdate:
    profiles, active_index = ensure_profiles(profiles, active_index)
    if not 0 <= index < len(profiles):
        return PlotProfileListUpdate(profiles, active_index, OperationResult.failure("Plot tab is out of range."))
    profile = profiles[index]
    return PlotProfileListUpdate(
        profiles,
        index,
        OperationResult.success(f"Selected plot '{profile.get('name', index + 1)}'.", payload=index),
    )


def next_plot_name(profiles: list[dict[str, Any]]) -> str:
    return unique_profile_name(profiles, f"Plot {len(profiles) + 1}")


def unique_profile_name(profiles: list[dict[str, Any]], base_name: str) -> str:
    existing = {str(profile.get("name", "")).strip() for profile in profiles}
    candidate = base_name.strip() or "Plot"
    if candidate not in existing:
        return candidate
    counter = 2
    while f"{candidate} {counter}" in existing:
        counter += 1
    return f"{candidate} {counter}"


def update_legend_channel_override(
    profiles: list[dict[str, Any]],
    active_index: int,
    channel: str,
    style: dict[str, Any],
) -> OperationResult:
    """Store a legend-row style override on the active profile."""
    channel_name = str(channel).strip()
    channel_key = plot_render_service.normalise_channel_name(channel_name)
    if not channel_key:
        return OperationResult.failure("Select a plotted channel to edit.")
    if not profiles:
        return OperationResult.failure("Select a plotted channel to edit.")

    index = clamp_index(active_index, len(profiles))
    profile = profiles[index]
    overrides = profile_legend_channel_overrides(profile)
    current = dict(overrides.get(channel_key, {}))
    updated = normalise_legend_channel_style(style)
    updated.setdefault("channel", channel_name or current.get("channel", ""))
    overrides[channel_key] = {**current, **updated}
    set_profile_legend_channel_overrides(profile, overrides)

    colour = overrides[channel_key].get("colour", "")
    if colour:
        propagate_channel_colour_override(
            profiles,
            channel_key,
            overrides[channel_key].get("channel", channel_name),
            colour,
        )
    label = overrides[channel_key].get("label") or channel_name
    return OperationResult.success(f"Updated legend style for '{label}'.")


def legend_channel_colour_overrides(profiles: list[dict[str, Any]]) -> dict[str, str]:
    """Return persisted legend colour overrides keyed by normalised channel."""
    colours: dict[str, str] = {}
    for profile in profiles:
        for channel_key, style in profile_legend_channel_overrides(profile).items():
            colour = str(style.get("colour", "")).strip()
            if colour:
                colours[channel_key] = colour
    return colours


def propagate_channel_colour_override(
    profiles: list[dict[str, Any]],
    channel_key: str,
    channel: str,
    colour: str,
) -> None:
    colour_text = str(colour).strip()
    if not colour_text:
        return
    for profile in profiles:
        overrides = profile_legend_channel_overrides(profile)
        if channel_key not in overrides and not profile_references_channel(profile, channel_key):
            continue
        style = dict(overrides.get(channel_key, {}))
        style.setdefault("channel", str(channel).strip())
        style["colour"] = colour_text
        overrides[channel_key] = style
        set_profile_legend_channel_overrides(profile, overrides)


def profile_references_channel(profile: dict[str, Any], channel_key: str) -> bool:
    channels = [*profile.get("y_columns", []), *profile.get("secondary_y_columns", [])]
    return any(plot_render_service.normalise_channel_name(channel) == channel_key for channel in channels)


def profile_legend_channel_overrides(profile: dict[str, Any]) -> dict[str, dict[str, str]]:
    legend = profile.get("legend", {}) if isinstance(profile, dict) else {}
    raw_overrides = legend.get("channel_overrides", {}) if isinstance(legend, dict) else {}
    if not isinstance(raw_overrides, dict):
        return {}
    overrides: dict[str, dict[str, str]] = {}
    for raw_key, raw_style in raw_overrides.items():
        if not isinstance(raw_style, dict):
            continue
        style = normalise_legend_channel_style(raw_style)
        channel_key = plot_render_service.normalise_channel_name(style.get("channel") or raw_key)
        if channel_key and style:
            overrides[channel_key] = style
    return overrides


def set_profile_legend_channel_overrides(profile: dict[str, Any], overrides: dict[str, dict[str, str]]) -> None:
    legend = profile.get("legend", {}) if isinstance(profile.get("legend", {}), dict) else {}
    profile["legend"] = {**legend, "channel_overrides": dict(overrides)}


def normalise_legend_channel_style(style: dict[str, Any]) -> dict[str, str]:
    if not isinstance(style, dict):
        return {}
    normalised: dict[str, str] = {}
    for key in (
        "channel",
        "label",
        "colour",
        "plot_kind",
        "line_style",
        "draw_style",
        "line_width",
        "marker_style",
        "marker_size",
        "marker_face_colour",
        "marker_edge_colour",
    ):
        value = str(style.get(key, "")).strip()
        if not value:
            continue
        normalised[key] = "Line + Markers" if key == "plot_kind" and value == "Line + Marker" else value
    if not normalised.get("label"):
        label = str(style.get("name", "")).strip()
        if label:
            normalised["label"] = label
    if not normalised.get("colour"):
        colour = str(style.get("color", "")).strip()
        if colour:
            normalised["colour"] = colour
    for source, target in (("marker_face_color", "marker_face_colour"), ("marker_edge_color", "marker_edge_colour")):
        if not normalised.get(target):
            value = str(style.get(source, "")).strip()
            if value:
                normalised[target] = value
    if "hidden" in style:
        value = style.get("hidden")
        hidden = value if isinstance(value, bool) else str(value).strip().casefold() in {"1", "true", "yes", "on"}
        normalised["hidden"] = "true" if hidden else "false"
    return normalised