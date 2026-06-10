"""Matplotlib-aware plot rendering helpers extracted from ``plotting.py``.

This module may import Matplotlib but must not import Tkinter or PySide6. Canvas
embedding and event handling remain in Qt adapters.
"""
from __future__ import annotations

from collections.abc import Iterable

import matplotlib.pyplot as plt

from ..core.config import EATON_PLOT_COLORS

# Colour-blind-safe cycle used when the user selects that palette in settings.
COLOURBLIND_SAFE_COLORS = [
    "#0072B2", "#D55E00", "#009E73", "#CC79A7", "#F0E442",
    "#56B4E9", "#E69F00", "#000000",
]


def resolve_plot_colours(cycle_name: str) -> list[str]:
    """Return the plot colour cycle for the configured ``cycle_name``."""
    if cycle_name == "matplotlib":
        return [item["color"] for item in plt.rcParams["axes.prop_cycle"]]
    if cycle_name == "colourblind_safe":
        return COLOURBLIND_SAFE_COLORS
    return list(EATON_PLOT_COLORS)


def secondary_colour_cycle(colours: list[str]) -> list[str]:
    """Return an offset colour cycle for the secondary Y axis.

    Offsetting keeps right-axis series visually distinct from left-axis series.
    """
    return colours[5:] + colours[:5] if len(colours) > 5 else colours


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
