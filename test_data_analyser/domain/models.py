"""Framework-independent runtime data containers.

This module holds plain data containers that are used while the application is
running (as opposed to the persistence-focused dataclasses in the sibling
modules). It must not import any UI framework (Tkinter or PySide6).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import pandas as pd


@dataclass
class PlotData:
    x: pd.Series
    y_map: dict[str, pd.Series]
    # Optional per-series X data. This allows wide Excel files where each test/run
    # has its own Flow Rate column to plot every Y channel against the matching
    # Flow Rate from the same test block, instead of forcing all Y channels to use
    # one global X column.
    x_map: Optional[dict[str, pd.Series]] = None
