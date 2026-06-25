"""Raw Data framing/filtering and edit coercion extracted from ``raw_data.py``
and ``raw_data_editor.py``.

Framework-independent: the UI handles inline editing widgets and display; this
service handles selection, filtering, blank-row removal, row-limit parsing, and
edit-value coercion.
"""
from __future__ import annotations

from typing import Any, Callable, Optional

import numpy as np
import pandas as pd

from ..core.column_matching import matching_x_column_for_y
from ..core.naming import natural_sort_key


def parse_row_limit(raw: str) -> Optional[int]:
    """Parse the "rows to display" entry into a positive int or ``None`` (all).

    Raises ``ValueError`` if the entry is non-empty and not a positive whole
    number; the UI decides how to surface that.
    """
    text = (raw or "").strip()
    if not text or text.lower() in {"all", "none", "no limit", "unlimited", "*"}:
        return None
    return max(1, int(text.replace(",", "")))


def select_raw_data_frame(
    df: Optional[pd.DataFrame],
    x_col: str,
    selected_y: list[str],
    *,
    apply_window: bool,
    xmin: Optional[float],
    xmax: Optional[float],
    drop_blank: bool,
    get_numeric: Callable[[str], pd.Series],
) -> tuple[pd.DataFrame, int]:
    """Return ``(selected_frame, blank_rows_removed)`` for the Raw Data view.

    ``get_numeric`` converts a column name to its cached numeric series (used for
    the analysis-window mask).
    """
    if df is None:
        return pd.DataFrame(), 0

    cols: list[str] = []
    if x_col and x_col in df.columns:
        cols.append(x_col)
    for col in sorted(selected_y, key=natural_sort_key):
        if x_col:
            paired_x_col = matching_x_column_for_y(x_col, col, df.columns)
            if paired_x_col in df.columns and paired_x_col not in cols:
                cols.append(paired_x_col)
        if col in df.columns and col not in cols:
            cols.append(col)
    if not cols:
        return pd.DataFrame(), 0

    raw_df = df.loc[:, cols].copy()
    if apply_window and x_col and x_col in df.columns:
        if xmin is not None or xmax is not None:
            x = get_numeric(x_col)
            mask = pd.Series(True, index=df.index)
            if xmin is not None:
                mask &= x >= xmin
            if xmax is not None:
                mask &= x <= xmax
            raw_df = raw_df.loc[mask]

    removed = 0
    if drop_blank and not raw_df.empty:
        before = len(raw_df)
        raw_df = raw_df.replace(r"^\s*$", np.nan, regex=True).dropna(axis=0, how="any")
        removed = before - len(raw_df)
    return raw_df, removed


def sort_display_frame(
    frame: pd.DataFrame,
    column: Optional[str],
    ascending: bool = True,
) -> pd.DataFrame:
    """Return ``frame`` sorted by ``column`` for display only.

    Numeric columns sort numerically; other columns sort using the shared
    natural-sort key so e.g. ``TC2`` precedes ``TC10``. NaN/blank values always
    sink to the bottom regardless of direction. The original index is preserved
    so edits still map back to the source dataframe row.
    """
    if not column or frame.empty or column not in frame.columns:
        return frame
    series = frame[column]
    if pd.api.types.is_numeric_dtype(series):
        return frame.sort_values(by=column, ascending=ascending, na_position="last", kind="stable")

    str_series = series.astype(str)
    blank = (series.isna() | (str_series.str.strip() == "")).to_numpy()
    keys = [natural_sort_key(value) for value in str_series]
    present = [i for i in range(len(frame)) if not blank[i]]
    present.sort(key=lambda i: keys[i])
    if not ascending:
        present.reverse()
    missing = [i for i in range(len(frame)) if blank[i]]
    return frame.iloc[present + missing]


def filter_display_frame(frame: pd.DataFrame, filters: dict[str, str]) -> pd.DataFrame:
    """Return ``frame`` with per-column quick filters applied (display only).

    Each filter string is one of ``>N``, ``<N``, ``>=N``, ``<=N``, ``=N``,
    ``a..b`` (inclusive numeric range), or otherwise a case-insensitive substring
    match on the stringified cell value. Blank filters are ignored. The original
    index is preserved.
    """
    if frame.empty or not filters:
        return frame
    mask = pd.Series(True, index=frame.index)
    for column, raw in filters.items():
        if column not in frame.columns:
            continue
        spec = (raw or "").strip()
        if not spec:
            continue
        mask &= _column_filter_mask(frame[column], spec)
    return frame.loc[mask]


def _column_filter_mask(series: pd.Series, spec: str) -> pd.Series:
    numeric = pd.to_numeric(series, errors="coerce")
    if ".." in spec:
        low_text, high_text = spec.split("..", 1)
        low = _filter_to_float(low_text)
        high = _filter_to_float(high_text)
        if low is not None and high is not None:
            return numeric.between(low, high)
    for op in (">=", "<=", ">", "<", "="):
        if spec.startswith(op):
            value = _filter_to_float(spec[len(op):])
            if value is None:
                break
            if op == ">=":
                return numeric >= value
            if op == "<=":
                return numeric <= value
            if op == ">":
                return numeric > value
            if op == "<":
                return numeric < value
            return numeric == value
    return series.astype(str).str.contains(spec, case=False, regex=False, na=False)


def _filter_to_float(text: str) -> Optional[float]:
    try:
        return float(str(text).strip().replace(",", ""))
    except (TypeError, ValueError):
        return None


def coerce_raw_edit_value(df: Optional[pd.DataFrame], column_name: str, text: str) -> Any:
    """Coerce edited cell ``text`` to the appropriate value for ``column_name``.

    Returns ``np.nan`` for a blank entry. Raises ``ValueError`` if a numeric
    column receives a non-numeric value.
    """
    text = text.strip()
    if text == "":
        return np.nan
    if df is None:
        return text
    if pd.api.types.is_numeric_dtype(df[column_name]):
        try:
            return float(text.replace(",", ""))
        except ValueError as exc:
            raise ValueError(f"'{column_name}' is numeric. Enter a numeric value or leave the cell blank.") from exc
    return text
