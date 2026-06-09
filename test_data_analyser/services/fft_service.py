"""FFT calculation extracted from ``plotting.py``.

Framework-independent numpy helpers for windowing and averaged spectra. No
Matplotlib or UI imports.
"""
from __future__ import annotations

import numpy as np


def fft_window(window_name: str, size: int) -> np.ndarray:
    """Return the window of ``size`` for the named window function."""
    if window_name == "hamming":
        return np.hamming(size)
    if window_name == "blackman":
        return np.blackman(size)
    if window_name == "rectangular":
        return np.ones(size)
    return np.hanning(size)


def fft_spectrum(
    values: np.ndarray,
    fs: float,
    window_name: str = "hanning",
    overlap_percent: int = 50,
) -> tuple[np.ndarray, np.ndarray]:
    """Return ``(frequencies, amplitudes)`` using optionally overlapped averaging."""
    n = len(values)
    overlap_percent = max(0, min(90, int(overlap_percent)))
    if overlap_percent <= 0 or n < 128:
        segment_length = n
    else:
        segment_length = max(64, n // 4)
    step = max(1, int(segment_length * (1.0 - overlap_percent / 100.0)))

    spectra: list[np.ndarray] = []
    freqs = np.fft.rfftfreq(segment_length, d=1.0 / fs)
    for start in range(0, n - segment_length + 1, step):
        segment = values[start:start + segment_length]
        window = fft_window(window_name, segment_length)
        correction = float(np.mean(window)) or 1.0
        spectra.append(np.abs(np.fft.rfft(segment * window)) * 2.0 / (segment_length * correction))
    if not spectra:
        window = fft_window(window_name, n)
        correction = float(np.mean(window)) or 1.0
        return np.fft.rfftfreq(n, d=1.0 / fs), np.abs(np.fft.rfft(values * window)) * 2.0 / (n * correction)
    return freqs, np.mean(spectra, axis=0)
