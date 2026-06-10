"""Plot data preparation extracted from ``plotting.py``.

Framework-independent: this module prepares the X/Y data structures for plotting
and applies the analysis-window filtering. It must not import Matplotlib or any
UI framework. Matplotlib rendering lives in ``plot_render_service`` / UI
adapters.
"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from ..core.filters import estimate_sampling_rate, lowpass_filter
from ..domain import PlotData
from .results import OperationResult


def apply_analysis_window(
    x: pd.Series,
    y_map: dict[str, pd.Series],
    x_map: dict[str, pd.Series],
    xmin: Optional[float],
    xmax: Optional[float],
) -> PlotData:
    """Return a :class:`PlotData` with the analysis-window mask applied.

    When both ``xmin`` and ``xmax`` are provided and ``xmin > xmax`` a
    ``ValueError`` is raised. Each Y channel is masked using its matching X
    series so wide files with per-block X columns filter correctly.
    """
    y_map = {label: series for label, series in y_map.items()}
    x_map = {label: series for label, series in x_map.items()}

    if xmin is not None or xmax is not None:
        if xmin is not None and xmax is not None and xmin > xmax:
            raise ValueError("Analysis Window Start X must be less than or equal to End X.")
        for col in list(y_map):
            x_for_col = x_map.get(col, x)
            mask = x_for_col.notna()
            if xmin is not None:
                mask &= x_for_col >= xmin
            if xmax is not None:
                mask &= x_for_col <= xmax
            x_map[col] = x_for_col.where(mask)
            y_map[col] = y_map[col].where(mask)
        global_mask = x.notna()
        if xmin is not None:
            global_mask &= x >= xmin
        if xmax is not None:
            global_mask &= x <= xmax
        x = x.where(global_mask)
    return PlotData(x=x, y_map=y_map, x_map=x_map)


def prepare_plot_series(
    data: PlotData,
    *,
    secondary_y: set[str] | None = None,
    use_filter: bool = False,
    cutoff: Optional[float] = None,
    order: int = 4,
) -> OperationResult:
    """Return cleaned, drawable X/Y series for the selected plot data.

    This keeps NaN dropping, low-pass filtering, and secondary-axis labelling in
    the service layer so Qt widgets only render already prepared arrays.
    """
    secondary = secondary_y or set()
    prepared: list[dict[str, Any]] = []
    try:
        for label, series in data.y_map.items():
            x_for_label = data.x_map.get(label, data.x) if data.x_map else data.x
            frame = pd.DataFrame({"x": x_for_label, "y": series}).dropna()
            if frame.empty:
                continue
            x_values = frame["x"].to_numpy(dtype=float)
            y_values = frame["y"].to_numpy(dtype=float)
            plot_label = label
            if use_filter:
                if cutoff is None:
                    return OperationResult.failure("Please enter a low-pass filter cutoff frequency.")
                fs = estimate_sampling_rate(frame["x"])
                if fs is None:
                    return OperationResult.failure(
                        "Cannot estimate sampling frequency from the selected X-axis column."
                    )
                y_values = lowpass_filter(y_values, cutoff_hz=cutoff, fs_hz=fs, order=order)
                plot_label = f"{label} | LP {cutoff:g} Hz"
            is_secondary = label in secondary
            if is_secondary:
                plot_label = f"{plot_label} [Right Y]"
            prepared.append(
                {
                    "channel": label,
                    "label": plot_label,
                    "x": x_values,
                    "y": y_values,
                    "secondary": is_secondary,
                }
            )
    except (ValueError, RuntimeError) as exc:
        return OperationResult.failure(str(exc))
    return OperationResult.success(payload=prepared)


def prepare_comparison_series(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return cleaned drawable series for a run-comparison plot."""
    prepared: list[dict[str, Any]] = []
    for item in items:
        frame = pd.DataFrame({"x": item.get("x"), "y": item.get("y")}).dropna()
        if frame.empty:
            continue
        prepared.append(
            {
                "label": item.get("label", ""),
                "x": frame["x"].to_numpy(dtype=float),
                "y": frame["y"].to_numpy(dtype=float),
                "colour": item.get("colour"),
            }
        )
    return prepared
