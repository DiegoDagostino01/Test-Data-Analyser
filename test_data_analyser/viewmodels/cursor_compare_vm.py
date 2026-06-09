"""Cursor / locked-point comparison viewmodel.

Holds the plotted data and the user's locked comparison points, and builds the
comparison table through ``cursor_service``. Framework-independent: the Qt panel
owns the Matplotlib click/key wiring and the table widget, while this viewmodel
owns the point list and the table data.
"""
from __future__ import annotations

from typing import Any, Optional

import pandas as pd

from ..domain import PlotData
from ..services import cursor_service


class CursorCompareViewModel:
    def __init__(self) -> None:
        self._x: Optional[pd.Series] = None
        self._y_map: dict[str, pd.Series] = {}
        self._points: list[dict[str, Any]] = []

    def set_data(self, data: Optional[PlotData]) -> None:
        """Set the plotted data (called after each plot) and clear locked points."""
        if data is None:
            self._x = None
            self._y_map = {}
        else:
            self._x = data.x
            self._y_map = dict(data.y_map)
        self._points.clear()

    @property
    def has_data(self) -> bool:
        return self._x is not None and not self._x.empty

    @property
    def points(self) -> list[dict[str, Any]]:
        return self._points

    def lock_at(self, xdata: float) -> bool:
        """Lock the nearest plotted point to ``xdata``. Returns True on success."""
        if not self.has_data:
            return False
        point = cursor_service.nearest_point(self._x, self._y_map, xdata)
        if point is None:
            return False
        point["point_no"] = len(self._points) + 1
        self._points.append(point)
        return True

    def clear(self) -> None:
        self._points.clear()

    def comparison_frame(self, decimals: int = 4) -> pd.DataFrame:
        return cursor_service.cursor_comparison_frame(self._points, decimals)

    def analysis_window_from_points(self) -> Optional[tuple[float, float]]:
        """Return the sorted ``(x1, x2)`` of the first two locked points, if any."""
        if len(self._points) < 2:
            return None
        x1 = float(self._points[0]["x"])
        x2 = float(self._points[1]["x"])
        return tuple(sorted([x1, x2]))  # type: ignore[return-value]
