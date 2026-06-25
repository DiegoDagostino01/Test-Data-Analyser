"""Fill-series generation for Excel-style drag/fill-down in the Raw Data table.

Framework-independent: infers whether a seed of cell values is a constant, an
arithmetic (linear) progression, or an arbitrary sequence, then generates the
next ``count`` values to extend it. Non-numeric or non-linear seeds repeat
verbatim.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional, Sequence

_TOL = 1e-9

FILL_CONSTANT = "constant"
FILL_LINEAR = "linear"
FILL_REPEAT = "repeat"


@dataclass(frozen=True)
class FillPattern:
    kind: str
    value: float = 0.0
    last: float = 0.0
    slope: float = 0.0
    base: tuple = field(default_factory=tuple)


def _as_floats(values: Sequence[Any]) -> Optional[list[float]]:
    floats: list[float] = []
    for value in values:
        if value is None:
            return None
        if isinstance(value, float) and math.isnan(value):
            return None
        try:
            floats.append(float(str(value).replace(",", "").strip()))
        except (TypeError, ValueError):
            return None
    return floats


def infer_fill_pattern(values: Sequence[Any]) -> FillPattern:
    """Infer the fill pattern for a seed of one or more cell ``values``."""
    floats = _as_floats(values)
    if floats:
        if len(floats) == 1:
            return FillPattern(kind=FILL_CONSTANT, value=floats[0])
        diffs = [floats[i + 1] - floats[i] for i in range(len(floats) - 1)]
        if all(abs(diff) <= _TOL for diff in diffs):
            return FillPattern(kind=FILL_CONSTANT, value=floats[-1])
        if all(abs(diff - diffs[0]) <= _TOL for diff in diffs):
            return FillPattern(kind=FILL_LINEAR, last=floats[-1], slope=diffs[0])
    return FillPattern(kind=FILL_REPEAT, base=tuple(values))


def generate_fill(pattern: FillPattern, count: int) -> list[Any]:
    """Generate the next ``count`` values that extend ``pattern``."""
    if count <= 0:
        return []
    if pattern.kind == FILL_CONSTANT:
        return [pattern.value] * count
    if pattern.kind == FILL_LINEAR:
        return [pattern.last + pattern.slope * (index + 1) for index in range(count)]
    base = pattern.base or ("",)
    return [base[index % len(base)] for index in range(count)]
