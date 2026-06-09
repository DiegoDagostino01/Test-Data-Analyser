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
from ..domain import PlotData


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


def compute_limit_margins(data: PlotData, normalised_lines: list[dict[str, Any]]) -> LimitMarginSummary:
    """Compute the margin-to-limit summary for prepared plot data."""
    x_values = data.x.to_numpy(dtype=float, copy=False)
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
        eval_mask = np.isfinite(x_values) & (x_values >= float(limit_x.min())) & (x_values <= float(limit_x.max()))
        if not eval_mask.any():
            summary.rows.append(
                LimitMarginRow(name, None, "SKIPPED", "not evaluated — selected X data is outside the limit-line X range.")
            )
            continue
        interpolated_limit = np.interp(x_values[eval_mask], limit_x, limit_y)
        for channel in channels:
            if channel not in data.y_map:
                continue
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
                status = "PASS" if float(margin[worst_idx]) >= 0 else "FAIL"
                descriptor = "minimum margin below upper limit"
            elif limit_type == "Lower Limit":
                margin = y_eval - limit_eval
                worst_idx = int(np.nanargmin(margin))
                status = "PASS" if float(margin[worst_idx]) >= 0 else "FAIL"
                descriptor = "minimum margin above lower limit"
            else:
                margin = y_eval - limit_eval
                worst_idx = int(np.nanargmax(np.abs(margin)))
                status = "INFO"
                descriptor = "largest deviation from reference"
            message = (
                f"{descriptor} = {float(margin[worst_idx]):.6g} at X = {float(x_eval[worst_idx]):.6g}; "
                f"data = {float(y_eval[worst_idx]):.6g}, limit = {float(limit_eval[worst_idx]):.6g}"
            )
            summary.rows.append(LimitMarginRow(name, channel, status, message))
    return summary


def calculate_limit_margins_text(data: PlotData, normalised_lines: list[dict[str, Any]]) -> str:
    """Return the margin-to-limit summary as display text."""
    return compute_limit_margins(data, normalised_lines).to_text()
