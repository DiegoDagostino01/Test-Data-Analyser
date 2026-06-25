"""Column-name matching helpers."""
from __future__ import annotations

from typing import Iterable, Optional


def split_grouped_column_name(column: object) -> tuple[Optional[str], str]:
    text = str(column).strip()
    if " - " not in text:
        return None, text
    group, variable = text.rsplit(" - ", 1)
    return group.strip() or None, variable.strip()


def matching_x_column_for_y(selected_x_col: str, y_col: str, columns: Iterable[object]) -> str:
    selected_group, selected_x_variable = split_grouped_column_name(selected_x_col)
    y_group, _y_variable = split_grouped_column_name(y_col)
    if selected_group is None or y_group is None:
        return selected_x_col
    candidate = f"{y_group} - {selected_x_variable}"
    available = {str(col) for col in columns}
    return candidate if candidate in available else selected_x_col


def infer_column_by_keywords(columns: Iterable[str], keywords: Iterable[str]) -> Optional[str]:
    keywords_lower = [k.lower() for k in keywords]
    for col in columns:
        if any(k in str(col).lower() for k in keywords_lower):
            return col
    return None