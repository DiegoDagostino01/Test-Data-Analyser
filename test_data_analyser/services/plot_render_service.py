"""Matplotlib-aware plot rendering helpers extracted from ``plotting.py``.

This module may import Matplotlib but must not import Tkinter or PySide6. Canvas
embedding and event handling remain in Qt adapters.
"""
from __future__ import annotations

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
