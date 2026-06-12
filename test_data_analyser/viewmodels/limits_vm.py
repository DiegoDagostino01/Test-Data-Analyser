"""Requirement / limits viewmodel.

Coordinates limit-line CRUD plus the limit calculations (normalisation, active
limit ranges, and the margin-to-limit summary) through ``limits_service``. The
UI only displays the structured results returned here.

The limit-line list and the active-line index live on :class:`AppState` (like
calculated channels and runs). The stateless calculation helpers keep taking an
explicit ``limit_lines`` argument so they can be used without state — the Qt
panel drives the stateful CRUD methods, while existing callers/tests still use
the pure helpers.
"""
from __future__ import annotations

import copy
from typing import Any, Optional, Tuple

import pandas as pd

from ..core.config import EATON_DARK_BLUE, LIMIT_COLOR_PRESETS
from ..core.utils import natural_sort_key
from ..domain import PlotData
from ..services import limits_service
from ..services.limits_service import LimitMarginSummary
from ..services.results import OperationResult
from .app_state import AppState

_LIMIT_TYPES = ("Upper Limit", "Lower Limit", "Reference Line")
LIMIT_LINES_TABLE_COLUMNS = ["Name", "Type", "Pts", "Applies to"]
LIMIT_POINTS_TABLE_COLUMNS = ["X", "Y Limit"]


class LimitsViewModel:
    def __init__(self, state: AppState | None = None) -> None:
        self.state = state

    # ------------------------------------------------------------------
    # Stateless calculation helpers
    # ------------------------------------------------------------------
    def normalise(self, limit_lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return limits_service.normalise_limit_lines(limit_lines)

    def active_ranges(
        self,
        limit_lines: list[dict[str, Any]],
        selected_y: set[str],
    ) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
        return limits_service.active_limit_ranges(self.normalise(limit_lines), selected_y)

    def margin_summary(self, data: PlotData, limit_lines: list[dict[str, Any]]) -> LimitMarginSummary:
        return limits_service.compute_limit_margins(data, self.normalise(limit_lines))

    def margin_text(self, data: PlotData, limit_lines: list[dict[str, Any]]) -> str:
        return limits_service.calculate_limit_margins_text(data, self.normalise(limit_lines))

    def margin_table_rows(self, data: PlotData, limit_lines: list[dict[str, Any]]) -> list[dict[str, object]]:
        return self.margin_summary(data, limit_lines).to_table_rows()

    # ------------------------------------------------------------------
    # Static metadata helpers (for the UI controls)
    # ------------------------------------------------------------------
    @staticmethod
    def limit_types() -> tuple[str, ...]:
        return _LIMIT_TYPES

    @staticmethod
    def colour_presets() -> dict[str, str]:
        return dict(LIMIT_COLOR_PRESETS)

    @staticmethod
    def preset_for_colour(colour: str) -> str:
        colour_upper = str(colour).strip().upper()
        for name, value in LIMIT_COLOR_PRESETS.items():
            if value.upper() == colour_upper:
                return name
        return "Custom"

    @staticmethod
    def colour_for_preset(preset: str) -> Optional[str]:
        return LIMIT_COLOR_PRESETS.get(preset)

    def applies_options(self, selected_y: list[str]) -> list[str]:
        return ["All selected Y channels"] + sorted(selected_y, key=natural_sort_key)

    # ------------------------------------------------------------------
    # Stateful access
    # ------------------------------------------------------------------
    @property
    def lines(self) -> list[dict[str, Any]]:
        return self.state.limit_lines if self.state is not None else []

    def active_index(self) -> int:
        if self.state is None or not self.state.limit_lines:
            return -1
        self.state.active_limit_line_index = max(
            0, min(self.state.active_limit_line_index, len(self.state.limit_lines) - 1)
        )
        return self.state.active_limit_line_index

    def active_line(self) -> Optional[dict[str, Any]]:
        index = self.active_index()
        if index < 0 or self.state is None:
            return None
        return self.state.limit_lines[index]

    def select_line(self, index: int) -> Optional[dict[str, Any]]:
        if self.state is None or not (0 <= index < len(self.state.limit_lines)):
            return None
        self.state.active_limit_line_index = index
        return self.state.limit_lines[index]

    @staticmethod
    def _blank_line(name: str) -> dict[str, Any]:
        return {
            "name": name,
            "type": "Upper Limit",
            "applies_to": "All selected Y channels",
            "color": EATON_DARK_BLUE,
            "points": [],
        }

    # ------------------------------------------------------------------
    # Stateful CRUD — limit lines
    # ------------------------------------------------------------------
    def add_line(self) -> OperationResult:
        if self.state is None:
            return OperationResult.failure("No application state is available.")
        name = f"Limit {len(self.state.limit_lines) + 1}"
        self.state.limit_lines.append(self._blank_line(name))
        self.state.active_limit_line_index = len(self.state.limit_lines) - 1
        return OperationResult.success(f"Added '{name}'.", payload=self.state.active_limit_line_index)

    def duplicate_line(self) -> OperationResult:
        if self.state is None:
            return OperationResult.failure("No application state is available.")
        line = self.active_line()
        if line is None:
            return self.add_line()
        duplicate = copy.deepcopy(line)
        duplicate["name"] = f"{line.get('name', 'Limit')} Copy"
        self.state.limit_lines.append(duplicate)
        self.state.active_limit_line_index = len(self.state.limit_lines) - 1
        return OperationResult.success(
            f"Duplicated '{line.get('name', 'Limit')}'.", payload=self.state.active_limit_line_index
        )

    def delete_line(self) -> OperationResult:
        if self.state is None or not self.state.limit_lines:
            return OperationResult.failure("Select a limit line to delete.")
        index = self.active_index()
        removed = self.state.limit_lines.pop(index)
        self.state.active_limit_line_index = max(0, min(index, len(self.state.limit_lines) - 1))
        return OperationResult.success(f"Deleted '{removed.get('name', 'Limit')}'.")

    def update_active_metadata(
        self,
        *,
        name: str,
        limit_type: str,
        applies_to: str,
        colour: str,
    ) -> OperationResult:
        line = self.active_line()
        if line is None:
            return OperationResult.failure("There is no active limit line to update.")
        index = self.active_index()
        line["name"] = name.strip() or f"Limit {index + 1}"
        line["type"] = limit_type or "Upper Limit"
        line["applies_to"] = applies_to or "All selected Y channels"
        line["color"] = colour.strip() or EATON_DARK_BLUE
        return OperationResult.success(payload=line)

    # ------------------------------------------------------------------
    # Stateful CRUD — limit points
    # ------------------------------------------------------------------
    @staticmethod
    def _parse_point(x_text: str, y_text: str) -> tuple[float, float]:
        return float(str(x_text).strip()), float(str(y_text).strip())

    @staticmethod
    def _sorted_points(line: dict[str, Any]) -> list[dict[str, float]]:
        return sorted(line.get("points", []), key=lambda p: float(p.get("x", 0.0)))

    def add_point(self, x_text: str, y_text: str) -> OperationResult:
        if self.active_line() is None:
            self.add_line()
        line = self.active_line()
        if line is None:
            return OperationResult.failure("There is no active limit line.")
        try:
            x, y = self._parse_point(x_text, y_text)
        except ValueError:
            return OperationResult.failure("Please enter numeric X and Y values for the limit point.")
        points = line.setdefault("points", [])
        points.append({"x": x, "y": y})
        points.sort(key=lambda p: float(p.get("x", 0.0)))
        return OperationResult.success("Added limit point.")

    def update_point(self, index: int, x_text: str, y_text: str) -> OperationResult:
        line = self.active_line()
        if line is None:
            return OperationResult.failure("There is no active limit line.")
        try:
            x, y = self._parse_point(x_text, y_text)
        except ValueError:
            return OperationResult.failure("Please enter numeric X and Y values for the selected limit point.")
        points = self._sorted_points(line)
        if not (0 <= index < len(points)):
            return OperationResult.failure("Select a limit point to update.")
        points[index] = {"x": x, "y": y}
        line["points"] = sorted(points, key=lambda p: float(p.get("x", 0.0)))
        return OperationResult.success("Updated limit point.")

    def delete_point(self, index: int) -> OperationResult:
        line = self.active_line()
        if line is None:
            return OperationResult.failure("There is no active limit line.")
        points = self._sorted_points(line)
        if not (0 <= index < len(points)):
            return OperationResult.failure("Select a limit point to delete.")
        del points[index]
        line["points"] = points
        return OperationResult.success("Deleted limit point.")

    def active_points(self) -> list[dict[str, float]]:
        line = self.active_line()
        if line is None:
            return []
        return self._sorted_points(line)

    def lines_table(self) -> pd.DataFrame:
        rows = []
        for line in self.lines:
            rows.append(
                {
                    "Name": line.get("name", "Limit"),
                    "Type": line.get("type", "Upper Limit"),
                    "Pts": len(line.get("points", [])),
                    "Applies to": line.get("applies_to", "All selected Y channels"),
                }
            )
        return pd.DataFrame(rows, columns=LIMIT_LINES_TABLE_COLUMNS)

    def active_points_table(self) -> pd.DataFrame:
        return pd.DataFrame(
            [{"X": f"{p['x']:.6g}", "Y Limit": f"{p['y']:.6g}"} for p in self.active_points()],
            columns=LIMIT_POINTS_TABLE_COLUMNS,
        )

