"""Requirement / limit calculations extracted from ``limits.py``.

Framework-independent helpers for normalising limit lines, computing active
limit ranges, and producing the margin-to-limit summary. The UI only displays
the results returned here; it must not embed this logic.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional, Tuple

import numpy as np

from ..core.config import EATON_DARK_BLUE
from ..core.utils import natural_sort_key
from ..domain import PlotData

WARNING_MARGIN_PERCENT = 5.0
MARGIN_TABLE_COLUMNS = [
    "Limit",
    "Channel",
    "Status",
    "Margin",
    "Margin %",
    "Worst X",
    "Data Value",
    "Limit Value",
    "First Failure X",
    "Details",
]


def normalise_limit_lines(limit_lines: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return limit lines with numeric, X-sorted points and defaulted metadata."""
    normalised: list[dict[str, Any]] = []
    for line in limit_lines:
        points: list[dict[str, float]] = []
        for point in line.get("points", []):
            try:
                points.append({"x": float(point.get("x")), "y": float(point.get("y"))})
            except Exception:
                continue
        points = sorted(points, key=lambda p: p["x"])
        normalised.append(
            {
                "name": line.get("name", "Limit"),
                "type": line.get("type", "Upper Limit"),
                "applies_to": line.get("applies_to", "All selected Y channels"),
                "color": line.get("color", EATON_DARK_BLUE),
                "points": points,
            }
        )
    return normalised


def limit_line_applies_to_selection(line: dict[str, Any], selected_y: set[str]) -> bool:
    """Return True when a limit line should influence the current plot."""
    applies_to = str(line.get("applies_to", "All selected Y channels"))
    if applies_to == "All selected Y channels":
        return True
    return applies_to in selected_y


def active_limit_ranges(
    normalised_lines: list[dict[str, Any]],
    selected_y: set[str],
) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
    """Return X/Y ranges for active plotted requirement limits (>=2 points)."""
    x_values: list[float] = []
    y_values: list[float] = []
    for line in normalised_lines:
        points = line.get("points", [])
        if len(points) < 2:
            continue
        if not limit_line_applies_to_selection(line, selected_y):
            continue
        for point in points:
            try:
                x_values.append(float(point["x"]))
                y_values.append(float(point["y"]))
            except Exception:
                continue
    x_range = (min(x_values), max(x_values)) if x_values else None
    y_range = (min(y_values), max(y_values)) if y_values else None
    return x_range, y_range


@dataclass
class LimitMarginRow:
    """A single row in the margin-to-limit summary.

    ``channel`` is ``None`` for rows describing a limit line that could not be
    evaluated (for example, fewer than two points).
    """

    limit_name: str
    channel: Optional[str]
    status: str  # "PASS", "FAIL", "INFO", or "SKIPPED"
    message: str
    margin: Optional[float] = None
    margin_percent: Optional[float] = None
    worst_x: Optional[float] = None
    data_value: Optional[float] = None
    limit_value: Optional[float] = None
    first_failure_x: Optional[float] = None
    first_failure_data: Optional[float] = None
    first_failure_limit: Optional[float] = None

    @property
    def severity(self) -> str:
        if self.status == "PASS" and self.margin_percent is not None and 0.0 <= self.margin_percent <= WARNING_MARGIN_PERCENT:
            return "WARN"
        return self.status

    def to_line(self) -> str:
        if self.channel is None:
            return f"{self.limit_name}: {self.message}"
        return f"{self.limit_name} | {self.channel} | {self.status}: {self.message}"


@dataclass
class LimitMarginSummary:
    rows: list[LimitMarginRow] = field(default_factory=list)

    @property
    def any_result(self) -> bool:
        return any(row.channel is not None for row in self.rows)

    def to_text(self) -> str:
        lines = [
            "MARGIN-TO-LIMIT SUMMARY",
            "Positive margin indicates the data is inside the limit for Upper/Lower limits.",
            "",
        ]
        lines.extend(row.to_line() for row in self.rows)
        if not self.any_result:
            lines.append(
                "No limit margins were calculated. Check that limits have at least 2 points and overlap the plotted X range."
            )
        return "\n".join(lines)

    def to_table_rows(self) -> list[dict[str, object]]:
        if not self.rows:
            return [
                {
                    "Limit": "",
                    "Channel": "",
                    "Status": "INFO",
                    "Severity": "INFO",
                    "Margin": None,
                    "Margin %": None,
                    "Worst X": None,
                    "Data Value": None,
                    "Limit Value": None,
                    "First Failure X": None,
                    "Details": "No limit margins were calculated.",
                }
            ]
        return [
            {
                "Limit": row.limit_name,
                "Channel": row.channel or "",
                "Status": row.status,
                "Severity": row.severity,
                "Margin": row.margin,
                "Margin %": row.margin_percent,
                "Worst X": row.worst_x,
                "Data Value": row.data_value,
                "Limit Value": row.limit_value,
                "First Failure X": row.first_failure_x,
                "Details": row.message,
            }
            for row in sorted(self.rows, key=_margin_row_sort_key)
        ]


def _margin_row_sort_key(row: LimitMarginRow) -> list[object]:
    limit_name = " ".join(str(row.limit_name).split())
    channel_name = " ".join(str(row.channel or "").split())
    return [natural_sort_key(limit_name), natural_sort_key(channel_name)]


def compute_limit_margins(data: PlotData, normalised_lines: list[dict[str, Any]]) -> LimitMarginSummary:
    """Compute the margin-to-limit summary for prepared plot data."""
    selected_y = list(data.y_map.keys())
    summary = LimitMarginSummary()

    for line in normalised_lines:
        name = line.get("name", "Limit")
        points = line.get("points", [])
        if len(points) < 2:
            summary.rows.append(
                LimitMarginRow(name, None, "SKIPPED", "not evaluated — at least 2 X/Y points are required.")
            )
            continue
        applies = line.get("applies_to", "All selected Y channels")
        channels = selected_y if applies == "All selected Y channels" else [applies]
        limit_x = np.array([p["x"] for p in points], dtype=float)
        limit_y = np.array([p["y"] for p in points], dtype=float)
        unique_x, unique_idx = np.unique(limit_x, return_index=True)
        limit_x = unique_x
        limit_y = limit_y[unique_idx]
        if len(limit_x) < 2:
            summary.rows.append(
                LimitMarginRow(name, None, "SKIPPED", "not evaluated — X values must include at least 2 unique points.")
            )
            continue
        any_channel_overlap = False
        for channel in channels:
            if channel not in data.y_map:
                continue
            x_series = data.x_map.get(channel, data.x) if data.x_map else data.x
            x_values = x_series.to_numpy(dtype=float, copy=False)
            eval_mask = np.isfinite(x_values) & (x_values >= float(limit_x.min())) & (x_values <= float(limit_x.max()))
            if not eval_mask.any():
                continue
            any_channel_overlap = True
            interpolated_limit = np.interp(x_values[eval_mask], limit_x, limit_y)
            y_values = data.y_map[channel].to_numpy(dtype=float, copy=False)[eval_mask]
            valid = np.isfinite(y_values) & np.isfinite(interpolated_limit)
            if not valid.any():
                continue
            x_eval = x_values[eval_mask][valid]
            y_eval = y_values[valid]
            limit_eval = interpolated_limit[valid]
            limit_type = line.get("type", "Upper Limit")
            if limit_type == "Upper Limit":
                margin = limit_eval - y_eval
                worst_idx = int(np.nanargmin(margin))
                failing = margin < 0
                status = "PASS" if not failing.any() else "FAIL"
                descriptor = "minimum margin below upper limit"
            elif limit_type == "Lower Limit":
                margin = y_eval - limit_eval
                worst_idx = int(np.nanargmin(margin))
                failing = margin < 0
                status = "PASS" if not failing.any() else "FAIL"
                descriptor = "minimum margin above lower limit"
            else:
                margin = y_eval - limit_eval
                worst_idx = int(np.nanargmax(np.abs(margin)))
                status = "INFO"
                descriptor = "largest deviation from reference"
            worst_margin = float(margin[worst_idx])
            worst_x = float(x_eval[worst_idx])
            worst_data = float(y_eval[worst_idx])
            worst_limit = float(limit_eval[worst_idx])
            margin_percent = _margin_percent(worst_margin, worst_limit, worst_data) if status in {"PASS", "FAIL"} else None
            message = (
                f"{descriptor} = {worst_margin:.6g} at X = {worst_x:.6g}; "
                f"data = {worst_data:.6g}, limit = {worst_limit:.6g}"
            )
            first_failure_x = None
            first_failure_data = None
            first_failure_limit = None
            if status == "FAIL":
                first_idx = _first_failure_index(x_eval, failing)
                first_failure_x = float(x_eval[first_idx])
                first_failure_data = float(y_eval[first_idx])
                first_failure_limit = float(limit_eval[first_idx])
                message += (
                    f"; first failure at X = {first_failure_x:.6g}; "
                    f"data = {first_failure_data:.6g}, limit = {first_failure_limit:.6g}"
                )
            summary.rows.append(
                LimitMarginRow(
                    name,
                    channel,
                    status,
                    message,
                    margin=worst_margin,
                    margin_percent=margin_percent,
                    worst_x=worst_x,
                    data_value=worst_data,
                    limit_value=worst_limit,
                    first_failure_x=first_failure_x,
                    first_failure_data=first_failure_data,
                    first_failure_limit=first_failure_limit,
                )
            )
        if not any_channel_overlap:
            summary.rows.append(
                LimitMarginRow(name, None, "SKIPPED", "not evaluated — selected X data is outside the limit-line X range.")
            )
    return summary


def _first_failure_index(x_values: np.ndarray, failing: np.ndarray) -> int:
    failing_indices = np.flatnonzero(failing)
    if len(failing_indices) == 0:
        return 0
    return int(failing_indices[np.nanargmin(x_values[failing_indices])])


def _margin_percent(margin: float, limit_value: float, data_value: float) -> float:
    denominator = abs(float(data_value))
    if not np.isfinite(denominator) or denominator < 1e-9:
        denominator = max(abs(float(limit_value)), 1.0)
    return (float(margin) / denominator) * 100.0


def calculate_limit_margins_text(data: PlotData, normalised_lines: list[dict[str, Any]]) -> str:
    """Return the margin-to-limit summary as display text."""
    return compute_limit_margins(data, normalised_lines).to_text()
