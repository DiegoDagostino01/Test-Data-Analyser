from __future__ import annotations

from typing import Optional
import numpy as np
import pandas as pd

try:
    from scipy.signal import butter as scipy_butter, filtfilt as scipy_filtfilt
    SCIPY_AVAILABLE = True
except Exception:
    scipy_butter = None
    scipy_filtfilt = None
    SCIPY_AVAILABLE = False

from .data_io import numeric_series

def lowpass_filter(values: np.ndarray, cutoff_hz: float, fs_hz: float,
                   order: int = 4) -> np.ndarray:
    butter_fn = scipy_butter
    filtfilt_fn = scipy_filtfilt
    if butter_fn is None or filtfilt_fn is None:
        raise RuntimeError("SciPy is not installed, so low-pass filtering is unavailable.")
    if len(values) < max(12, order * 3):
        raise ValueError("Not enough data points for low-pass filtering.")
    nyquist = 0.5 * fs_hz
    if cutoff_hz <= 0 or cutoff_hz >= nyquist:
        raise ValueError(f"Cutoff must be > 0 and < Nyquist frequency ({nyquist:.6g} Hz).")
    b, a = butter_fn(order, cutoff_hz / nyquist, btype="low")
    return filtfilt_fn(b, a, values)

def estimate_sampling_rate(x_values: pd.Series) -> Optional[float]:
    x = numeric_series(x_values).dropna()
    if len(x) < 3:
        return None
    diffs = x.diff().dropna()
    diffs = diffs[diffs > 0]
    if diffs.empty:
        return None
    median_dt = float(diffs.median())
    return None if median_dt <= 0 else 1.0 / median_dt

