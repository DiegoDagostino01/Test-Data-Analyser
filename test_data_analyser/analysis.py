from __future__ import annotations

from typing import Any, Iterable, Optional, Tuple
import tkinter as tk

import numpy as np
import pandas as pd


class AnalysisMixin:
    """Statistics and selected-data range behaviour."""

    def get_selected_data_ranges(self: Any) -> Tuple[
            Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
        try:
            data = self.prepare_plot_data()
        except Exception:
            return None, None
        x_min: Optional[float] = None
        x_max: Optional[float] = None
        y_min: Optional[float] = None
        y_max: Optional[float] = None
        secondary_y = set(self.selected_secondary_y_columns()) if hasattr(self, "secondary_y_vars") else set()
        for label, s in data.y_map.items():
            if label in secondary_y:
                continue
            x_for_label = data.x_map.get(label, data.x) if data.x_map else data.x
            frame = pd.DataFrame({"x": x_for_label, "y": s}).dropna()
            if frame.empty:
                continue
            lo_x, hi_x = float(frame["x"].min()), float(frame["x"].max())
            lo_y, hi_y = float(frame["y"].min()), float(frame["y"].max())
            x_min = lo_x if x_min is None else min(x_min, lo_x)
            x_max = hi_x if x_max is None else max(x_max, hi_x)
            y_min = lo_y if y_min is None else min(y_min, lo_y)
            y_max = hi_y if y_max is None else max(y_max, hi_y)
        x_range: Optional[Tuple[float, float]] = (x_min, x_max) if x_min is not None and x_max is not None else None
        y_range: Optional[Tuple[float, float]] = (y_min, y_max) if y_min is not None and y_max is not None else None
        limit_x_range, limit_y_range = self._get_active_limit_ranges()
        if limit_x_range is not None:
            x_range = (min(x_range[0], limit_x_range[0]) if x_range else limit_x_range[0], max(x_range[1], limit_x_range[1]) if x_range else limit_x_range[1])
        if limit_y_range is not None:
            y_range = (min(y_range[0], limit_y_range[0]) if y_range else limit_y_range[0], max(y_range[1], limit_y_range[1]) if y_range else limit_y_range[1])
        return x_range, y_range

    def get_secondary_y_data_range(self: Any) -> Optional[Tuple[float, float]]:
        try:
            data = self.prepare_plot_data()
        except Exception:
            return None
        secondary_y = set(self.selected_secondary_y_columns())
        if not secondary_y:
            return None
        y_min: Optional[float] = None
        y_max: Optional[float] = None
        for label, s in data.y_map.items():
            if label not in secondary_y:
                continue
            frame = pd.DataFrame({"y": s}).dropna()
            if frame.empty:
                continue
            lo_y, hi_y = float(frame["y"].min()), float(frame["y"].max())
            y_min = lo_y if y_min is None else min(y_min, lo_y)
            y_max = hi_y if y_max is None else max(y_max, hi_y)
        return (y_min, y_max) if y_min is not None and y_max is not None else None

    def update_range_preview(self: Any) -> None:
        x_range, y_range = self.get_selected_data_ranges()
        if x_range is None or y_range is None:
            self.range_preview_var.set(
                "Load data and select numeric columns to preview ranges.")
        else:
            self.range_preview_var.set(
                f"Selected data range: X = {x_range[0]:.6g} to {x_range[1]:.6g}"
                f"; Y = {y_range[0]:.6g} to {y_range[1]:.6g}")

    def fill_axis_limits_from_data(self: Any) -> None:
        x_range, y_range = self.get_selected_data_ranges()
        if x_range:
            self.xmin_var.set(f"{x_range[0]:.6g}")
            self.xmax_var.set(f"{x_range[1]:.6g}")
        if y_range:
            self.ymin_var.set(f"{y_range[0]:.6g}")
            self.ymax_var.set(f"{self._axis_upper_margin(y_range[1], y_range[0]):.6g}")
        y2_range = self.get_secondary_y_data_range()
        if y2_range:
            self.y2min_var.set(f"{y2_range[0]:.6g}")
            self.y2max_var.set(f"{self._axis_upper_margin(y2_range[1], y2_range[0]):.6g}")

    def _compute_statistics(self: Any, y_cols: Iterable[str]) -> pd.DataFrame:
        rows: dict[str, dict[str, float | int]] = {}
        decimal_places = int(self._setting("axis_scaling", "decimal_places_statistics", 4)) if hasattr(self, "_setting") else 4
        for col in y_cols:
            s = self._get_numeric(col).dropna()
            if s.empty:
                continue
            rows[col] = {
                "Count":       int(s.count()),
                "Min":         round(float(s.min()), decimal_places),
                "Max":         round(float(s.max()), decimal_places),
                "Mean":        round(float(s.mean()), decimal_places),
                "Median":      round(float(s.median()), decimal_places),
                "Std Dev":     round(float(s.std(ddof=1)), decimal_places) if s.count() > 1 else 0.0,
                "RMS":         round(float(np.sqrt(np.mean(np.square(s)))), decimal_places),
                "Peak-to-Peak": round(float(s.max() - s.min()), decimal_places),
            }
        return pd.DataFrame.from_dict(rows, orient="index")

    def update_stats(self: Any) -> None:
        if not hasattr(self, "stats_tree"):
            return
        for row in self.stats_tree.get_children():
            self.stats_tree.delete(row)
        if self.df is None:
            return
        stats = self._compute_statistics(self.selected_y_columns())
        visible_columns = self._configured_statistics_columns() if hasattr(self, "_configured_statistics_columns") else ["Count", "Min", "Max", "Mean", "Median", "Std Dev", "RMS", "Peak-to-Peak"]
        if hasattr(self, "_configure_stats_tree_columns"):
            self._configure_stats_tree_columns()
        for index, (signal, row) in enumerate(stats.iterrows()):
            values = [signal] + [
                row.get(col, "")
                for col in visible_columns
            ]
            self.stats_tree.insert(
                "", tk.END, values=values, tags=(self._tree_row_tag(index),)
            )