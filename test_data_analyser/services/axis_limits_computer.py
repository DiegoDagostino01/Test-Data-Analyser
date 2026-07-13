"""Axis tick/limit computation.

Framework-independent helpers for validating axis tick steps and mapping ticks
between a primary and secondary Y axis. No Qt and no Matplotlib: the plot
workspace widget reads live axis limits/ticks from Matplotlib and passes plain
numbers here, so this logic stays unit-testable in isolation.
"""
from __future__ import annotations

import math

#: Cap on major ticks per axis; Matplotlib raises MAXTICKS beyond ~1000.
DEFAULT_MAX_AXIS_MAJOR_TICKS = 1000


def positive_float(value: object) -> float | None:
    """Return ``value`` as a finite positive float, or ``None`` if it is not."""
    text = str(value).strip()
    if not text:
        return None
    try:
        number = float(text)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number) or number <= 0:
        return None
    return number


def safe_major_tick(
    step: float | None,
    limits: tuple[float, float],
    *,
    max_ticks: int = DEFAULT_MAX_AXIS_MAJOR_TICKS,
) -> float | None:
    """Drop a tick step too small for the axis range to avoid a tick blow-up.

    A tiny step on a wide axis (e.g. 2 on a 0-90000 axis) would force Matplotlib
    past its MAXTICKS limit and crash rendering, so it is dropped and automatic
    ticks are kept instead. Returns ``step`` unchanged when it is safe.
    """
    if step is None:
        return None
    try:
        numeric_step = float(step)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(numeric_step) or numeric_step <= 0:
        return None
    try:
        span = abs(float(limits[1]) - float(limits[0]))
    except (TypeError, ValueError, IndexError):
        return numeric_step
    if span and span / numeric_step > max_ticks:
        return None
    return numeric_step


def mapped_secondary_ticks(
    primary_ticks,
    primary_min: float,
    primary_max: float,
    secondary_min: float,
    secondary_max: float,
) -> list[float]:
    """Map primary-axis tick positions onto the secondary axis' scale.

    Returns an empty list when the primary range is degenerate. Each primary
    tick is linearly rescaled so the secondary gridlines align with the primary.
    """
    if primary_max == primary_min:
        return []
    return [
        secondary_min + ((float(tick) - primary_min) / (primary_max - primary_min)) * (secondary_max - secondary_min)
        for tick in primary_ticks
    ]
