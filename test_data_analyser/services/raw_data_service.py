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

from ..core.utils import _matching_x_column_for_y


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
    for col in selected_y:
        if x_col:
            paired_x_col = _matching_x_column_for_y(x_col, col, df.columns)
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
