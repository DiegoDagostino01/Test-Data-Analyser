"""Cursor / locked-point comparison helpers extracted from ``cursor_tools.py``.

Framework-independent: finding the nearest plotted sample to an X position and
building the locked-point comparison table (per-point rows plus delta-versus-
Point-1 rows). The UI owns the Matplotlib event wiring and the table widget.
"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from ..core.utils import natural_sort_key


def nearest_point(
    x_values: pd.Series,
    y_map: dict[str, pd.Series],
    xdata: float,
) -> Optional[dict[str, Any]]:
    """Return the nearest plotted sample to ``xdata``.

    The result is ``{"index", "x", "values": {channel: value_or_None}}`` or
    ``None`` when there is no valid X data.
    """
    x_valid = x_values.dropna()
    if x_valid.empty:
        return None
    idx = (x_valid - xdata).abs().idxmin()
    values = {
        name: (series.loc[idx] if pd.notna(series.loc[idx]) else None)
        for name, series in y_map.items()
    }
    return {"index": idx, "x": float(x_values.loc[idx]), "values": values}


def _format_number(value: Any, decimals: int) -> str:
    if value is None or pd.isna(value):
        return ""
    if isinstance(value, (int, float)):
        return f"{float(value):.{decimals}f}"
    return str(value)


def cursor_comparison_frame(points: list[dict[str, Any]], decimals: int = 4) -> pd.DataFrame:
    """Build the locked-point comparison table.

    Columns are ``Type, Point, Index / Ref, X / ΔX`` followed by one column per
    channel. Per-point rows are followed by delta-versus-Point-1 rows when two or
    more points are locked.
    """
    base_columns = ["Type", "Point", "Index / Ref", "X / ΔX"]
    if not points:
        return pd.DataFrame(columns=base_columns)

    channels = sorted(points[0]["values"].keys(), key=natural_sort_key)
    columns = base_columns + channels
    rows: list[dict[str, str]] = []

    for point in points:
        row = {
            "Type": "Point",
            "Point": str(point["point_no"]),
            "Index / Ref": str(point["index"]),
            "X / ΔX": _format_number(point["x"], decimals),
        }
        for channel in channels:
            row[channel] = _format_number(point["values"].get(channel), decimals)
        rows.append(row)

    if len(points) >= 2:
        base = points[0]
        for point in points[1:]:
            row = {
                "Type": "Δ vs P1",
                "Point": f"P{point['point_no']} - P1",
                "Index / Ref": f"{point['index']} - {base['index']}",
                "X / ΔX": _format_number(point["x"] - base["x"], decimals),
            }
            for channel in channels:
                a = point["values"].get(channel)
                b = base["values"].get(channel)
                row[channel] = "" if a is None or b is None else _format_number(a - b, decimals)
            rows.append(row)

    return pd.DataFrame(rows, columns=columns)
