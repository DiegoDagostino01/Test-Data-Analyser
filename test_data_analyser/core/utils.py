from __future__ import annotations

from typing import Iterable, Optional
import re

from .config import COLUMN_GROUP_ORDER, DOMAIN_CONFIG

def safe_name(text: object) -> str:
    cleaned = "".join(c if c.isalnum() or c in "_-" else "_" for c in str(text)).strip("_")
    return cleaned or "plot"

def natural_sort_key(text: object) -> list[object]:
    """Sort engineering channel names naturally, e.g. TC1, TC2, TC10 instead of TC1, TC10, TC2."""
    parts = re.split(r"(\d+)", str(text).lower())
    return [int(part) if part.isdigit() else part for part in parts]

def _split_grouped_column_name(column: object) -> tuple[Optional[str], str]:
    text = str(column).strip()
    if " - " not in text:
        return None, text
    group, variable = text.rsplit(" - ", 1)
    return group.strip() or None, variable.strip()

def _matching_x_column_for_y(selected_x_col: str, y_col: str, columns: Iterable[object]) -> str:
    selected_group, selected_x_variable = _split_grouped_column_name(selected_x_col)
    y_group, _y_variable = _split_grouped_column_name(y_col)
    if selected_group is None or y_group is None:
        return selected_x_col
    candidate = f"{y_group} - {selected_x_variable}"
    available = {str(col) for col in columns}
    return candidate if candidate in available else selected_x_col

def _is_temperature_channel_name(name: str) -> bool:
    lowered = name.lower()
    if any(token in lowered for token in ("temp", "temperature", "deg c", "degc", "°c")):
        return True
    return re.search(r"(?<![a-z0-9])tc[\s_\-]*\d+(?![a-z0-9])", lowered) is not None

def classify_channel_name(name: object) -> str:
    """Classify a channel name into a deterministic engineering reading group.

    The classification is name-based only, so unknown columns fall back to
    ``"Other Numeric"``. UI layers with dtype information can still label truly
    non-numeric columns separately, but the common engineering terms live here.
    """
    text = str(name or "").strip()
    if not text:
        return "Other Numeric"
    if _is_temperature_channel_name(text):
        return "Temperature"
    for group in COLUMN_GROUP_ORDER:
        if group in {"Temperature", "Other Numeric", "Non-numeric / Metadata"}:
            continue
        keywords = DOMAIN_CONFIG.get(group, [])
        if any(_keyword_matches(text, keyword) for keyword in keywords):
            return group
    return "Other Numeric"

def channel_group_options() -> list[str]:
    """Return channel filter options in the configured engineering order."""
    return ["All", *COLUMN_GROUP_ORDER]

def _keyword_matches(text: str, keyword: str) -> bool:
    lowered = text.lower()
    token = str(keyword).lower().strip()
    if not token:
        return False
    if len(token) <= 2:
        return re.search(rf"(?<![a-z0-9]){re.escape(token)}(?![a-z0-9])", lowered) is not None
    return token in lowered

def _block_mousewheel(event=None) -> str:
    """Prevent mouse-wheel changes on widgets such as read-only comboboxes."""
    return "break"

def infer_column_by_keywords(columns: Iterable[str],
                             keywords: Iterable[str]) -> Optional[str]:
    keywords_lower = [k.lower() for k in keywords]
    for col in columns:
        if any(k in str(col).lower() for k in keywords_lower):
            return col
    return None

