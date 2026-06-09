"""Run / comparison helpers extracted from ``multi_run.py``.

Framework-independent: enabled-run filtering, common-X-range calculation,
per-channel comparison framing, comparison statistics, and run metadata
serialisation. The UI owns the trees, dialogs, and Matplotlib drawing.
"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from ..core.config import EATON_PLOT_COLORS
from ..core.data_io import numeric_series
from ..domain import RunMetadata
from ..core.utils import _matching_x_column_for_y


def enabled_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return runs that are enabled and carry a dataframe."""
    return [
        run
        for run in runs
        if run.get("enabled", True) and isinstance(run.get("df"), pd.DataFrame)
    ]


def comparison_common_x_range(
    runs: list[dict[str, Any]],
    selected_x: str,
) -> Optional[tuple[float, float]]:
    """Return the overlapping X range shared by all runs containing ``selected_x``."""
    mins: list[float] = []
    maxes: list[float] = []
    for run in runs:
        df = run.get("df")
        if not isinstance(df, pd.DataFrame) or selected_x not in df.columns:
            continue
        x = numeric_series(df[selected_x]).dropna()
        if x.empty:
            continue
        mins.append(float(x.min()))
        maxes.append(float(x.max()))
    if not mins or not maxes:
        return None
    common_min = max(mins)
    common_max = min(maxes)
    if common_min >= common_max:
        return None
    return common_min, common_max


def comparison_channel_frame(
    df: pd.DataFrame,
    x_column: str,
    y_column: str,
    common_range: Optional[tuple[float, float]],
    xmin: Optional[float] = None,
    xmax: Optional[float] = None,
) -> pd.DataFrame:
    """Return a cleaned ``{x, y}`` frame for a run channel within the windows."""
    x = numeric_series(df[x_column])
    y = numeric_series(df[y_column])
    mask = x.notna() & y.notna()
    if xmin is not None:
        mask &= x >= xmin
    if xmax is not None:
        mask &= x <= xmax
    if common_range is not None:
        mask &= x >= common_range[0]
        mask &= x <= common_range[1]
    return pd.DataFrame({"x": x[mask], "y": y[mask]}).dropna()


def matching_x_column(selected_x: str, y_column: str, columns: Any) -> str:
    """Return the X column matching ``y_column`` for wide grouped files."""
    return _matching_x_column_for_y(selected_x, y_column, columns)


def run_channel_statistics(df: pd.DataFrame, channel: str) -> Optional[dict[str, float | int]]:
    """Return comparison statistics for ``channel`` or ``None`` if no data."""
    if channel not in df.columns:
        return None
    series = numeric_series(df[channel]).dropna()
    if series.empty:
        return None
    return {
        "Count": int(series.count()),
        "Min": float(series.min()),
        "Max": float(series.max()),
        "Mean": float(series.mean()),
        "Std Dev": float(series.std(ddof=1)) if series.count() > 1 else 0.0,
    }


def serialise_runs(runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Serialise run metadata for session persistence (no dataframe copies)."""
    serialised: list[dict[str, Any]] = []
    for index, run in enumerate(runs):
        metadata = RunMetadata(
            name=run.get("name", f"Run {index + 1}"),
            filepath=str(run.get("filepath", "")),
            sheet_name=run.get("sheet_name", ""),
            enabled=bool(run.get("enabled", True)),
            colour=run.get("colour", EATON_PLOT_COLORS[index % len(EATON_PLOT_COLORS)]),
        )
        serialised.append(metadata.to_dict())
    return serialised
