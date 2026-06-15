"""Matplotlib-aware plot rendering helpers extracted from ``plotting.py``.

This module may import Matplotlib but must not import Tkinter or PySide6. Canvas
embedding and event handling remain in Qt adapters.
"""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from ..core.config import EATON_PLOT_COLORS

# Colour-blind-safe cycle used when the user selects that palette in settings.
COLOURBLIND_SAFE_COLORS = [
    "#0072B2", "#D55E00", "#009E73", "#CC79A7", "#F0E442",
    "#56B4E9", "#E69F00", "#000000",
]
BEST_FIT_TYPES = ("Linear", "Squared", "Polynomial")
MAX_BEST_FIT_CHANNELS = 5
MAX_BEST_FIT_ORDER = 6


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
    if cycle_name == "matplotlib":
        from matplotlib import rcParams

        return [item["color"] for item in rcParams["axes.prop_cycle"]]
    if cycle_name == "colourblind_safe":
        return COLOURBLIND_SAFE_COLORS
    return list(EATON_PLOT_COLORS)


def secondary_colour_cycle(colours: list[str]) -> list[str]:
    """Return an offset colour cycle for the secondary Y axis.

    Offsetting keeps right-axis series visually distinct from left-axis series.
    """
    return colours[5:] + colours[:5] if len(colours) > 5 else colours


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
