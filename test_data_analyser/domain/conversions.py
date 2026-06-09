"""Small, framework-independent value-coercion helpers.

These helpers are shared by the domain dataclasses to defensively normalise
values that arrive from JSON sessions, the Tkinter UI, or a future Qt UI. They
intentionally accept missing/invalid input and fall back to safe defaults so old
saved sessions keep loading.
"""
from __future__ import annotations

from typing import Any


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _int(value: object, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default
