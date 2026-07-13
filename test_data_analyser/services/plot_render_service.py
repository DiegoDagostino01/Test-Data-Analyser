"""Matplotlib-aware plot rendering helpers extracted from ``plotting.py``.

This module may import Matplotlib but must not import Tkinter or PySide6. Canvas
embedding and event handling remain in Qt adapters.
"""
from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from ..core.config import EATON_PLOT_COLORS

# Colour-blind-safe cycle used when the user selects that palette in settings.
COLOURBLIND_SAFE_COLORS = [
    "#0072B2", "#D55E00", "#009E73", "#CC79A7", "#F0E442",
    "#56B4E9", "#E69F00", "#000000",
]
PLOT_KINDS = ("Line", "Scatter", "Line + Markers")
CURVE_STYLE_KEYS = {
    "line_style",
    "draw_style",
    "line_width",
    "marker_style",
    "marker_size",
    "marker_face_colour",
    "marker_edge_colour",
}
BEST_FIT_TYPES = ("Linear", "Squared", "Polynomial")
MAX_BEST_FIT_CHANNELS = 5
MAX_BEST_FIT_ORDER = 6
ColourCycleFactory = Callable[[], Iterable[object]]
_COLOUR_CYCLE_FACTORIES: dict[str, ColourCycleFactory] = {}


def _normalise_registry_name(name: object) -> str:
    return str(name or "").strip().casefold()


def register_colour_cycle(name: str, factory: ColourCycleFactory, *, replace: bool = False) -> None:
    """Register a named plot colour-cycle provider."""
    key = _normalise_registry_name(name)
    if not key:
        raise ValueError("Colour cycle name cannot be empty.")
    if key in _COLOUR_CYCLE_FACTORIES and not replace:
        raise ValueError(f"Colour cycle '{name}' is already registered.")
    _COLOUR_CYCLE_FACTORIES[key] = factory


def available_colour_cycles() -> list[str]:
    """Return registered colour-cycle names in registration order."""
    return list(_COLOUR_CYCLE_FACTORIES)


def _fit_order(fit_type: str, order: object) -> int:
    if fit_type == "Linear":
        return 1
    if fit_type == "Squared":
        return 2
    try:
        parsed = int(float(str(order)))
    except (TypeError, ValueError):
        parsed = 1
    return max(1, min(parsed, MAX_BEST_FIT_ORDER))


def normalise_best_fit_settings(settings: object) -> list[dict[str, object]]:
    """Return at most five valid best-fit channel settings."""
    if not isinstance(settings, list):
        return []

    normalised: list[dict[str, object]] = []
    seen: set[str] = set()
    for raw_setting in settings:
        if not isinstance(raw_setting, dict):
            continue
        channel = str(raw_setting.get("channel", "")).strip()
        channel_key = normalise_channel_name(channel)
        if not channel_key or channel_key in seen:
            continue
        fit_type = str(raw_setting.get("fit_type", "Linear")).strip()
        if fit_type not in BEST_FIT_TYPES:
            fit_type = "Linear"
        order = _fit_order(fit_type, raw_setting.get("order", 1))
        normalised.append(
            {
                "channel": channel,
                "fit_type": fit_type,
                "order": order,
            }
        )
        seen.add(channel_key)
        if len(normalised) >= MAX_BEST_FIT_CHANNELS:
            break
    return normalised


def resolve_plot_colours(cycle_name: str) -> list[str]:
    """Return the plot colour cycle for the configured ``cycle_name``."""
    factory = _COLOUR_CYCLE_FACTORIES.get(_normalise_registry_name(cycle_name))
    if factory is None:
        factory = _COLOUR_CYCLE_FACTORIES["eaton"]
    colours = [str(colour).strip() for colour in factory() if str(colour).strip()]
    return colours or list(EATON_PLOT_COLORS)


def secondary_colour_cycle(colours: list[str]) -> list[str]:
    """Return an offset colour cycle for the secondary Y axis.

    Offsetting keeps right-axis series visually distinct from left-axis series.
    """
    return colours[5:] + colours[:5] if len(colours) > 5 else colours


def apply_channel_style_overrides(
    series_items: list[dict[str, Any]],
    channel_styles: dict[str, dict[str, str]] | None,
    default_plot_kind: str,
) -> list[dict[str, Any]]:
    """Return series items with per-channel legend/style overrides applied."""
    styles = normalised_channel_styles(channel_styles or {})
    fallback_plot_kind = normalise_plot_kind(default_plot_kind) or "Line"
    styled_items: list[dict[str, Any]] = []
    for item in series_items:
        styled = dict(item)
        style = styles.get(series_channel_key(item), {})
        label = series_label_with_override(item, style)
        if label:
            styled["label"] = label
        plot_kind = normalise_plot_kind(style.get("plot_kind")) or fallback_plot_kind
        styled["plot_kind"] = plot_kind
        colour = str(style.get("colour", "")).strip()
        if colour:
            styled["colour"] = colour
        for key in CURVE_STYLE_KEYS:
            value = str(style.get(key, "")).strip()
            if value:
                styled[key] = value
        if "hidden" in style:
            styled["hidden"] = style_bool(style.get("hidden"))
        styled["label_overridden"] = bool(style.get("label"))
        styled["plot_kind_overridden"] = bool(style.get("plot_kind"))
        styled_items.append(styled)
    return styled_items


def normalised_channel_styles(channel_styles: dict[str, dict[str, str]]) -> dict[str, dict[str, str]]:
    """Return channel style overrides keyed by normalised channel name."""
    normalised: dict[str, dict[str, str]] = {}
    for raw_key, raw_style in channel_styles.items():
        if not isinstance(raw_style, dict):
            continue
        style: dict[str, str] = {}
        for raw_name, raw_value in raw_style.items():
            value = str(raw_value).strip()
            if not value:
                continue
            name = "label" if raw_name == "name" else "colour" if raw_name == "color" else str(raw_name)
            if name == "plot_kind":
                value = normalise_plot_kind(value)
                if not value:
                    continue
            if name in {"channel", "label", "colour", "plot_kind", *CURVE_STYLE_KEYS}:
                style[name] = value
        if "hidden" in raw_style:
            style["hidden"] = "true" if style_bool(raw_style.get("hidden")) else "false"
        channel_key = normalise_channel_name(style.get("channel") or raw_key)
        if channel_key and style:
            normalised[channel_key] = style
    return normalised


def style_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().casefold() in {"1", "true", "yes", "on"}


def series_label_with_override(item: dict[str, Any], style: dict[str, str]) -> str:
    custom_label = str(style.get("label", "")).strip()
    if not custom_label:
        return str(item.get("label", ""))
    label = without_right_y_suffix(custom_label)
    return f"{label} [Right Y]" if item.get("secondary") else label


def normalise_plot_kind(plot_kind: object) -> str:
    text = str(plot_kind or "").strip()
    if text == "Line + Marker":
        text = "Line + Markers"
    return text if text in PLOT_KINDS else ""


def series_channel_key(item: dict[str, Any]) -> str:
    return normalise_channel_name(item.get("channel", item.get("label", "")))


def without_right_y_suffix(label: object) -> str:
    return str(label).replace(" [Right Y]", "").strip()


def resolve_axis_range(
    current_range: tuple[Any, Any],
    minimum: Any | None,
    maximum: Any | None,
) -> tuple[Any, Any] | None:
    """Return the axis range to apply, or ``None`` when it should stay unchanged.

    ``minimum`` and ``maximum`` are optional manual limits. Missing sides keep
    the current rendered range so callers can set only one side of an axis.
    Inverted or equal limits are ignored, matching the previous widget logic.
    """
    if minimum is None and maximum is None:
        return None
    current_min, current_max = current_range
    lower = current_min if minimum is None else minimum
    upper = current_max if maximum is None else maximum
    if lower < upper:
        return lower, upper
    return None


def polynomial_best_fit(
    x_values: object,
    y_values: object,
    order: int,
    *,
    sample_count: int = 200,
) -> dict[str, Any] | None:
    """Return sampled polynomial best-fit data for finite X/Y values."""
    import numpy as np

    try:
        x = np.asarray(x_values, dtype=float).ravel()
        y = np.asarray(y_values, dtype=float).ravel()
    except (TypeError, ValueError):
        return None
    if x.size != y.size or x.size == 0:
        return None
    finite_mask = np.isfinite(x) & np.isfinite(y)
    x = x[finite_mask]
    y = y[finite_mask]
    if x.size <= order or np.unique(x).size <= order:
        return None
    try:
        coefficients = np.polyfit(x, y, order)
    except Exception:
        return None

    x_min = float(np.min(x))
    x_max = float(np.max(x))
    if x_min == x_max:
        return None
    sample_total = max(2, int(sample_count))
    sampled_x = np.linspace(x_min, x_max, sample_total)
    sampled_y = np.polyval(coefficients, sampled_x)
    return {
        "x": sampled_x,
        "y": sampled_y,
        "coefficients": [float(value) for value in coefficients],
        "formula": format_polynomial_formula(coefficients),
    }


def format_polynomial_formula(coefficients: Iterable[object]) -> str:
    """Return a readable ``y = ...`` polynomial formula."""
    coefficient_values = [float(value) for value in coefficients]
    degree = len(coefficient_values) - 1
    if degree < 0:
        return "y = 0"

    terms: list[str] = []
    for index, coefficient in enumerate(coefficient_values):
        power = degree - index
        if abs(coefficient) < 1e-12:
            continue
        magnitude = abs(coefficient)
        if power == 0:
            term = f"{magnitude:.6g}"
        elif power == 1:
            term = f"{magnitude:.6g}x"
        else:
            term = f"{magnitude:.6g}x^{power}"
        if not terms:
            terms.append(term if coefficient >= 0 else f"-{term}")
        else:
            terms.append(f" {'+' if coefficient >= 0 else '-'} {term}")
    return "y = " + ("".join(terms) if terms else "0")


def normalise_channel_name(channel: object) -> str:
    """Return a stable comparison key for a plotted channel name."""
    return " ".join(str(channel).strip().split()).casefold()


def y_axis_channel_set(primary_y: Iterable[object] | None, secondary_y: Iterable[object] | None = None) -> list[str]:
    """Return primary + secondary Y channels de-duplicated by normalised name."""
    channels: list[str] = []
    seen: set[str] = set()
    primary_items = [] if primary_y is None else list(primary_y)
    secondary_items = [] if secondary_y is None else list(secondary_y)
    for channel in [*primary_items, *secondary_items]:
        key = normalise_channel_name(channel)
        if not key or key in seen:
            continue
        seen.add(key)
        channels.append(str(channel).strip())
    return channels


def persistent_channel_colour_map(
    channel_sets: Iterable[Iterable[object]],
    colours: list[str],
) -> dict[str, str]:
    """Map repeated Y-axis channels to stable colours.

    The returned keys are normalised channel names. Channels are counted at most
    once per plot set so duplicate primary/secondary selections do not trigger a
    false repeat by themselves.
    """
    if not colours:
        return {}

    counts: dict[str, int] = {}
    first_seen_order: list[str] = []
    for channel_set in channel_sets:
        seen_in_plot: set[str] = set()
        for channel in channel_set:
            key = normalise_channel_name(channel)
            if not key or key in seen_in_plot:
                continue
            seen_in_plot.add(key)
            if key not in counts:
                counts[key] = 0
                first_seen_order.append(key)
            counts[key] += 1

    repeated = [key for key in first_seen_order if counts.get(key, 0) > 1]
    return {key: colours[index % len(colours)] for index, key in enumerate(repeated)}


def series_colour_assignment(
    series_items: list[dict[str, Any]],
    channel_colours: dict[str, str] | None,
    primary_colours: list[str],
    secondary_colours: list[str],
) -> list[str | None]:
    """Assign a colour to each series item.

    Manual per-item colours and persistent per-channel colours win; the
    remaining items take the next distinct colour from the primary/secondary
    cycles, skipping colours already used or reserved. Returns ``None`` for every
    item when neither a manual nor a repeated-channel colour applies, so the
    caller can let Matplotlib cycle colours itself.
    """
    persistent_colours = _normalised_channel_colours(channel_colours or {})
    manual_colours = [_manual_series_colour(item) for item in series_items]
    has_manual_colour = any(manual_colours)
    has_repeated_channel = any(series_channel_key(item) in persistent_colours for item in series_items)
    if not has_manual_colour and not has_repeated_channel:
        return [None for _item in series_items]

    reserved = {
        _colour_key(colour)
        for item, manual_colour in zip(series_items, manual_colours)
        for colour in (manual_colour or persistent_colours.get(series_channel_key(item)),)
        if colour
    }
    assignments: list[str | None] = []
    used: set[str] = set()
    primary_index = 0
    secondary_index = 0
    for item, manual_colour in zip(series_items, manual_colours):
        is_secondary = bool(item.get("secondary"))
        channel_colour = manual_colour or persistent_colours.get(series_channel_key(item))
        if not channel_colour:
            cycle = secondary_colours if is_secondary else primary_colours
            cycle_index = secondary_index if is_secondary else primary_index
            channel_colour = _next_distinct_colour(cycle, cycle_index, used | reserved)
        assignments.append(channel_colour)
        if channel_colour:
            used.add(_colour_key(channel_colour))
        if is_secondary:
            secondary_index += 1
        else:
            primary_index += 1
    return assignments


def _normalised_channel_colours(channel_colours: dict[str, str]) -> dict[str, str]:
    normalised: dict[str, str] = {}
    for channel, colour in channel_colours.items():
        key = normalise_channel_name(channel)
        colour_text = str(colour).strip()
        if key and colour_text:
            normalised[key] = colour_text
    return normalised


def _manual_series_colour(item: dict[str, Any]) -> str:
    colour = item.get("colour", item.get("color"))
    return "" if colour is None else str(colour).strip()


def _next_distinct_colour(colours: list[str], start_index: int, blocked: set[str]) -> str | None:
    if not colours:
        return None
    for offset in range(len(colours)):
        colour = colours[(start_index + offset) % len(colours)]
        if _colour_key(colour) not in blocked:
            return colour
    return colours[start_index % len(colours)]


def _colour_key(colour: str) -> str:
    from matplotlib.colors import to_hex

    try:
        return to_hex(colour).lower()
    except Exception:
        return str(colour).strip().lower()


def _eaton_colour_cycle() -> list[str]:
    return list(EATON_PLOT_COLORS)


def _matplotlib_colour_cycle() -> list[str]:
    from matplotlib import rcParams

    return [item["color"] for item in rcParams["axes.prop_cycle"]]


def _colourblind_safe_cycle() -> list[str]:
    return list(COLOURBLIND_SAFE_COLORS)


register_colour_cycle("eaton", _eaton_colour_cycle)
register_colour_cycle("matplotlib", _matplotlib_colour_cycle)
register_colour_cycle("colourblind_safe", _colourblind_safe_cycle)
