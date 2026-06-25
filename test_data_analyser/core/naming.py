"""General naming and sorting helpers."""
from __future__ import annotations

import re


def safe_name(text: object) -> str:
    cleaned = "".join(c if c.isalnum() or c in "_-" else "_" for c in str(text)).strip("_")
    return cleaned or "plot"


def natural_sort_key(text: object) -> list[object]:
    """Sort engineering channel names naturally, e.g. TC1, TC2, TC10 instead of TC1, TC10, TC2."""
    parts = re.split(r"(\d+)", str(text).lower())
    return [int(part) if part.isdigit() else part for part in parts]