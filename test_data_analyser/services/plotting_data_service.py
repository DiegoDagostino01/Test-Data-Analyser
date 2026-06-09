"""Plot data preparation extracted from ``plotting.py``.

Framework-independent: this module prepares the X/Y data structures for plotting
and applies the analysis-window filtering. It must not import Matplotlib or any
UI framework. Matplotlib rendering lives in ``plot_render_service`` / UI
adapters.
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from ..domain import PlotData


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
