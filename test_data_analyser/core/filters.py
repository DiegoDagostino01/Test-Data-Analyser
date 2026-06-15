from __future__ import annotations

from collections.abc import Callable
from typing import Optional
import numpy as np
import pandas as pd

from .data_io import numeric_series


_scipy_butter: Callable | None = None
_scipy_filtfilt: Callable | None = None
_scipy_import_attempted = False
SCIPY_AVAILABLE = False


def _scipy_signal_functions() -> tuple[Callable, Callable]:
    global SCIPY_AVAILABLE, _scipy_butter, _scipy_filtfilt, _scipy_import_attempted
    if not _scipy_import_attempted:
        _scipy_import_attempted = True
        try:
            from scipy.signal import butter, filtfilt
        except Exception:
            SCIPY_AVAILABLE = False
        else:
            _scipy_butter = butter
            _scipy_filtfilt = filtfilt
            SCIPY_AVAILABLE = True
    if _scipy_butter is None or _scipy_filtfilt is None:
        raise RuntimeError("SciPy is not installed, so low-pass filtering is unavailable.")
    return _scipy_butter, _scipy_filtfilt


def lowpass_filter(values: np.ndarray, cutoff_hz: float, fs_hz: float,
                   order: int = 4) -> np.ndarray:
    butter_fn, filtfilt_fn = _scipy_signal_functions()
    if len(values) < max(12, order * 3):
        raise ValueError("Not enough data points for low-pass filtering.")
    nyquist = 0.5 * fs_hz
    if cutoff_hz <= 0 or cutoff_hz >= nyquist:
        raise ValueError(f"Cutoff must be > 0 and < Nyquist frequency ({nyquist:.6g} Hz).")
    numerator, denominator = butter_fn(order, cutoff_hz / nyquist, btype="low")
    return filtfilt_fn(numerator, denominator, values)


def estimate_sampling_rate(x_values: pd.Series) -> Optional[float]:
    numeric_x_values = numeric_series(x_values).dropna()
    if len(numeric_x_values) < 3:
        return None
    diffs = numeric_x_values.diff().dropna()
    diffs = diffs[diffs > 0]
    if diffs.empty:
        return None
    median_dt = float(diffs.median())
    return None if median_dt <= 0 else 1.0 / median_dt

