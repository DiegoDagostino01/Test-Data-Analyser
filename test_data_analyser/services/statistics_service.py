"""Statistics calculations extracted from ``analysis.py``.

Framework-independent helpers that operate on pandas Series/mappings and return
plain objects or a :class:`pandas.DataFrame`. They must not import Tkinter or
PySide6.
"""
from __future__ import annotations

from typing import Mapping, Optional, Tuple

import numpy as np
import pandas as pd

from ..domain import PlotData

# Canonical order of the statistics produced for the statistics table.
STATISTIC_COLUMNS = [
    "Count",
    "Min",
    "Max",
    "Mean",
    "Median",
    "Std Dev",
    "RMS",
    "Peak-to-Peak",
]


def count(series: pd.Series) -> int:
    return int(series.count())


def minimum(series: pd.Series) -> float:
    return float(series.min())


def maximum(series: pd.Series) -> float:
    return float(series.max())


def mean(series: pd.Series) -> float:
    return float(series.mean())


def median(series: pd.Series) -> float:
    return float(series.median())


def std_dev(series: pd.Series) -> float:
    return float(series.std(ddof=1)) if series.count() > 1 else 0.0


def rms(series: pd.Series) -> float:
    return float(np.sqrt(np.mean(np.square(series))))


def peak_to_peak(series: pd.Series) -> float:
    return float(series.max() - series.min())


def compute_series_statistics(series: pd.Series, decimal_places: int = 4) -> dict[str, float | int]:
    """Return the full statistics row for a single numeric series."""
    return {
        "Count": count(series),
        "Min": round(minimum(series), decimal_places),
        "Max": round(maximum(series), decimal_places),
        "Mean": round(mean(series), decimal_places),
        "Median": round(median(series), decimal_places),
        "Std Dev": round(std_dev(series), decimal_places),
        "RMS": round(rms(series), decimal_places),
        "Peak-to-Peak": round(peak_to_peak(series), decimal_places),
    }


def compute_statistics(columns: Mapping[str, pd.Series], decimal_places: int = 4) -> pd.DataFrame:
    """Compute statistics for a mapping of ``{column_name: numeric_series}``.

    Empty series (after dropping NaNs) are skipped. The result is indexed by
    column name with one column per entry in :data:`STATISTIC_COLUMNS`.
    """
    rows: dict[str, dict[str, float | int]] = {}
    for name, series in columns.items():
        cleaned = series.dropna()
        if cleaned.empty:
            continue
        rows[name] = compute_series_statistics(cleaned, decimal_places)
    return pd.DataFrame.from_dict(rows, orient="index")


def selected_xy_ranges(
    data: PlotData,
    secondary_y: set[str] | None = None,
) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
    """Return ``(x_range, y_range)`` for the primary-axis data in ``data``.

    Secondary-axis channels are excluded. Returns ``None`` for a range when no
    finite data was available.
    """
    secondary_y = secondary_y or set()
    x_min: Optional[float] = None
    x_max: Optional[float] = None
    y_min: Optional[float] = None
    y_max: Optional[float] = None
    for label, series in data.y_map.items():
        if label in secondary_y:
            continue
        x_for_label = data.x_map.get(label, data.x) if data.x_map else data.x
        frame = pd.DataFrame({"x": x_for_label, "y": series}).dropna()
        if frame.empty:
            continue
        lo_x, hi_x = float(frame["x"].min()), float(frame["x"].max())
        lo_y, hi_y = float(frame["y"].min()), float(frame["y"].max())
        x_min = lo_x if x_min is None else min(x_min, lo_x)
        x_max = hi_x if x_max is None else max(x_max, hi_x)
        y_min = lo_y if y_min is None else min(y_min, lo_y)
        y_max = hi_y if y_max is None else max(y_max, hi_y)
    x_range = (x_min, x_max) if x_min is not None and x_max is not None else None
    y_range = (y_min, y_max) if y_min is not None and y_max is not None else None
    return x_range, y_range


def secondary_y_range(data: PlotData, secondary_y: set[str]) -> Optional[Tuple[float, float]]:
    """Return the ``(min, max)`` range across the secondary-axis channels."""
    if not secondary_y:
        return None
    y_min: Optional[float] = None
    y_max: Optional[float] = None
    for label, series in data.y_map.items():
        if label not in secondary_y:
            continue
        frame = pd.DataFrame({"y": series}).dropna()
        if frame.empty:
            continue
        lo_y, hi_y = float(frame["y"].min()), float(frame["y"].max())
        y_min = lo_y if y_min is None else min(y_min, lo_y)
        y_max = hi_y if y_max is None else max(y_max, hi_y)
    return (y_min, y_max) if y_min is not None and y_max is not None else None
