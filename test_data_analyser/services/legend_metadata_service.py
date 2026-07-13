"""Legend metadata extraction.

Matplotlib-aware (reads live artist properties) but Qt-free: turns plotted
Line2D / collection handles into the metadata dicts the legend panel and the
channel-style dialog consume. Kept out of the plot workspace widget so the
introspection logic is unit-testable in isolation.
"""
from __future__ import annotations

import math
from typing import Any, cast

from ..core.config import EATON_DARK_BLUE
from . import plot_render_service

CURVE_STYLE_KEYS = plot_render_service.CURVE_STYLE_KEYS


def _without_right_y_suffix(label: object) -> str:
    return str(label).replace(" [Right Y]", "").strip()


def channel_metadata(handle, label: str) -> dict[str, object]:
    """Return the legend-row metadata for a plotted ``handle`` (or ``{}``)."""
    channel = str(getattr(handle, "_tda_channel", "")).strip()
    if not channel:
        return {}
    return {
        "channel": channel,
        "label": _without_right_y_suffix(label),
        "colour": legend_colour(handle),
        "plot_kind": str(getattr(handle, "_tda_plot_kind", "Line")),
        "label_overridden": bool(getattr(handle, "_tda_label_overridden", False)),
        "plot_kind_overridden": bool(getattr(handle, "_tda_plot_kind_overridden", False)),
        "hidden": bool(getattr(handle, "_tda_hidden", False)) or not bool(getattr(handle, "get_visible", lambda: True)()),
        **curve_metadata(handle),
    }


def curve_metadata(handle) -> dict[str, str]:
    """Return the per-curve style metadata read from a plotted ``handle``."""
    metadata = {key: str(getattr(handle, f"_tda_{key}", "")).strip() for key in CURVE_STYLE_KEYS}
    try:
        metadata["line_style"] = metadata["line_style"] or str(handle.get_linestyle())
        metadata["draw_style"] = metadata["draw_style"] or str(handle.get_drawstyle())
        metadata["line_width"] = metadata["line_width"] or f"{float(handle.get_linewidth()):g}"
        metadata["marker_style"] = metadata["marker_style"] or normalise_marker_style(handle.get_marker())
        metadata["marker_size"] = metadata["marker_size"] or f"{float(handle.get_markersize()):g}"
        metadata["marker_face_colour"] = metadata["marker_face_colour"] or colour_to_hex(handle.get_markerfacecolor())
        metadata["marker_edge_colour"] = metadata["marker_edge_colour"] or colour_to_hex(handle.get_markeredgecolor())
    except AttributeError:
        sizes = getattr(handle, "get_sizes", lambda: [])()
        face_colours = getattr(handle, "get_facecolors", lambda: [])()
        edge_colours = getattr(handle, "get_edgecolors", lambda: [])()
        metadata["line_style"] = metadata["line_style"] or "None"
        metadata["draw_style"] = metadata["draw_style"] or "default"
        metadata["line_width"] = metadata["line_width"] or "0"
        metadata["marker_style"] = metadata["marker_style"] or str(getattr(handle, "_tda_marker_style", "o"))
        if len(sizes):
            metadata["marker_size"] = metadata["marker_size"] or f"{math.sqrt(float(sizes[0])):g}"
        metadata["marker_face_colour"] = metadata["marker_face_colour"] or first_colour_to_hex(face_colours)
        metadata["marker_edge_colour"] = metadata["marker_edge_colour"] or first_colour_to_hex(edge_colours)
    return metadata


def legend_colour(handle) -> str:
    """Return a hex colour for a plotted ``handle``, defaulting to Eaton blue."""
    from matplotlib.colors import to_hex

    try:
        colour = handle.get_color()
        return to_hex(colour)
    except Exception:
        pass
    try:
        colours = handle.get_facecolors()
        if len(colours):
            return to_hex(colours[0])
    except Exception:
        pass
    return EATON_DARK_BLUE


def colour_to_hex(colour: object) -> str:
    from matplotlib.colors import to_hex

    try:
        return to_hex(cast(Any, colour))
    except Exception:
        return ""


def first_colour_to_hex(colours: object) -> str:
    try:
        colour_values = list(cast(Any, colours))
        if colour_values:
            return colour_to_hex(colour_values[0])
    except Exception:
        pass
    return ""


def normalise_marker_style(value: object) -> str:
    text = str(value or "").strip()
    if text in {"", "None", "none"}:
        return "none"
    return text
