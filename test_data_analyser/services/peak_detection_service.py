"""Peak (and trough) detection for plotted channels.

Wraps ``scipy.signal.find_peaks`` behind a lazy import (mirroring
``core/filters.py``) so SciPy stays an optional dependency. Pure numeric logic
with no Qt; non-finite samples are dropped and the original sample index is kept
on each result.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Optional

import numpy as np

_find_peaks: Optional[Callable] = None
_import_attempted = False
SCIPY_AVAILABLE = False


def _scipy_find_peaks() -> Callable:
    global _find_peaks, _import_attempted, SCIPY_AVAILABLE
    if not _import_attempted:
        _import_attempted = True
        try:
            from scipy.signal import find_peaks as scipy_find_peaks
        except Exception:
            SCIPY_AVAILABLE = False
        else:
            _find_peaks = scipy_find_peaks
            SCIPY_AVAILABLE = True
    if _find_peaks is None:
        raise RuntimeError("SciPy is not installed, so peak detection is unavailable.")
    return _find_peaks


@dataclass(frozen=True)
class Peak:
    x: float
    y: float
    index: int
    is_trough: bool = False


def find_peaks(
    x: Any,
    y: Any,
    *,
    prominence: Optional[float] = None,
    distance: Optional[float] = None,
    find_troughs: bool = False,
) -> list[Peak]:
    """Return the peaks (and optionally troughs) of ``y`` sampled at ``x``.

    ``x`` may be ``None`` to use sample indices. Raises ``RuntimeError`` when
    SciPy is unavailable.
    """
    detector = _scipy_find_peaks()
    y_arr = np.asarray(y, dtype=float)
    x_arr = np.asarray(x, dtype=float) if x is not None else np.arange(len(y_arr), dtype=float)
    count = min(len(x_arr), len(y_arr))
    x_arr, y_arr = x_arr[:count], y_arr[:count]

    finite = np.isfinite(x_arr) & np.isfinite(y_arr)
    xf, yf = x_arr[finite], y_arr[finite]
    original_index = np.nonzero(finite)[0]
    if len(yf) == 0:
        return []

    kwargs: dict[str, Any] = {}
    if prominence is not None:
        kwargs["prominence"] = prominence
    if distance is not None and distance >= 1:
        kwargs["distance"] = distance

    peaks: list[Peak] = []
    indices, _ = detector(yf, **kwargs)
    for i in indices:
        peaks.append(Peak(x=float(xf[i]), y=float(yf[i]), index=int(original_index[i]), is_trough=False))
    if find_troughs:
        trough_indices, _ = detector(-yf, **kwargs)
        for i in trough_indices:
            peaks.append(Peak(x=float(xf[i]), y=float(yf[i]), index=int(original_index[i]), is_trough=True))

    peaks.sort(key=lambda peak: peak.index)
    return peaks
