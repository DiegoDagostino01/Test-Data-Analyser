"""Best-fit line rendering adapter.

Matplotlib-aware helpers that inspect plotted series, draw polynomial best-fit
lines onto the axes, and remove them again. No Qt and no widget state: the plot
workspace widget passes the figure axes in and stores the returned formula rows
itself. Fit computation lives in ``plot_render_service``; this module only
renders the result.
"""
from __future__ import annotations

from typing import Any, cast

from ...core.config import EATON_DARK_BLUE
from ...services import legend_metadata_service, plot_render_service


def _without_right_y_suffix(label: object) -> str:
    return str(label).replace(" [Right Y]", "").strip()


def _best_fit_label(source_label: str, fit_type: str) -> str:
    return f"{_without_right_y_suffix(source_label)} {fit_type.lower()} fit"


def remove_best_fit_artists(figure_axes) -> None:
    """Remove every best-fit line previously drawn onto ``figure_axes``."""
    for axes in list(figure_axes):
        for line in list(axes.get_lines()):
            if bool(getattr(line, "_tda_best_fit", False)):
                line.remove()


def source_series(figure_axes) -> list[dict[str, Any]]:
    """Return the drawable (non best-fit, visible, channelled) plotted series."""
    sources: list[dict[str, Any]] = []
    for axes in list(figure_axes):
        for line in axes.get_lines():
            if bool(getattr(line, "_tda_best_fit", False)):
                continue
            if bool(getattr(line, "_tda_hidden", False)):
                continue
            channel = str(getattr(line, "_tda_channel", "")).strip()
            if not channel:
                continue
            sources.append(
                {
                    "axes": axes,
                    "channel": channel,
                    "label": line.get_label(),
                    "x": line.get_xdata(orig=False),
                    "y": line.get_ydata(orig=False),
                    "colour": legend_metadata_service.legend_colour(line),
                }
            )
        for collection in axes.collections:
            if bool(getattr(collection, "_tda_hidden", False)):
                continue
            channel = str(getattr(collection, "_tda_channel", "")).strip()
            if not channel:
                continue
            offsets_getter = getattr(collection, "get_offsets", None)
            if not callable(offsets_getter):
                continue
            offsets = offsets_getter()
            try:
                offset_values = list(cast(Any, offsets))
                if len(offset_values) == 0:
                    continue
                x_values = [float(point[0]) for point in offset_values]
                y_values = [float(point[1]) for point in offset_values]
            except (TypeError, ValueError, IndexError):
                continue
            sources.append(
                {
                    "axes": axes,
                    "channel": channel,
                    "label": collection.get_label(),
                    "x": x_values,
                    "y": y_values,
                    "colour": legend_metadata_service.legend_colour(collection),
                }
            )
    return sources


def draw_best_fit_lines(
    best_fit_settings: object,
    source_series: list[dict[str, Any]],
    default_axes,
    *,
    line_width: float,
    default_colour: str = EATON_DARK_BLUE,
) -> list[dict[str, object]]:
    """Draw best-fit lines for the configured channels; return formula rows."""
    settings = plot_render_service.normalise_best_fit_settings(best_fit_settings)
    formula_rows: list[dict[str, object]] = []
    if not settings:
        return formula_rows
    source_by_channel = {
        plot_render_service.normalise_channel_name(source.get("channel")): source
        for source in source_series
        if plot_render_service.normalise_channel_name(source.get("channel"))
    }
    for setting in settings:
        channel = str(setting.get("channel", ""))
        source = source_by_channel.get(plot_render_service.normalise_channel_name(channel))
        if source is None:
            continue
        try:
            order = int(cast(Any, setting.get("order", 1)))
        except (TypeError, ValueError):
            order = 1
        fit = plot_render_service.polynomial_best_fit(source.get("x"), source.get("y"), order)
        if fit is None:
            continue
        fit_type = str(setting.get("fit_type", "Linear"))
        source_label = str(source.get("label") or channel)
        label = _best_fit_label(source_label, fit_type)
        axes = source.get("axes") or default_axes
        line = axes.plot(
            fit["x"],
            fit["y"],
            linestyle="--",
            linewidth=max(1.0, line_width * 1.15),
            color=source.get("colour") or default_colour,
            label=label,
        )[0]
        setattr(line, "_tda_best_fit", True)
        try:
            line.set_gid(f"best-fit:{channel}")
        except AttributeError:
            pass
        formula_rows.append(
            {
                "Channel": _without_right_y_suffix(source_label),
                "Fit": fit_type,
                "Order": order,
                "Formula": fit.get("formula", ""),
            }
        )
    return formula_rows
