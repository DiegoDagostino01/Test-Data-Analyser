"""Plot workspace panel.

Embeds the Matplotlib Qt canvas and renders the active selection through the
framework-independent :class:`PlotWorkspaceViewModel`. Data preparation and FFT
live in the viewmodel/services; colour-cycle resolution lives in
``plot_render_service``. This panel only orchestrates rendering onto the canvas.
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd
from cycler import cycler
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QVBoxLayout, QWidget

from ...core.config import EATON_DARK_BLUE
from ...core.filters import estimate_sampling_rate, lowpass_filter
from ...services import plot_render_service
from ...services.results import OperationResult
from ...viewmodels.cursor_compare_vm import CursorCompareViewModel
from ...viewmodels.plot_workspace_vm import PlotWorkspaceViewModel
from ...viewmodels.settings_vm import SettingsViewModel
from ..adapters.matplotlib_qt_adapter import MatplotlibCanvas


class PlotWorkspace(QWidget):
    cursorPointsChanged = Signal()

    def __init__(
        self,
        plot_vm: PlotWorkspaceViewModel,
        settings_vm: SettingsViewModel,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.plot_vm = plot_vm
        self.settings_vm = settings_vm
        self._last_plot_data = None
        self._last_x_col = ""
        self._cursor_vm: CursorCompareViewModel | None = None
        self._point_compare = False
        self._cursor_artists: list = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.canvas = MatplotlibCanvas(self)
        layout.addWidget(self.canvas)

        self.canvas.canvas.mpl_connect("button_press_event", self._on_canvas_click)
        self.canvas.canvas.mpl_connect("key_press_event", self._on_canvas_key)

    # ------------------------------------------------------------------
    # Cursor / point-compare
    # ------------------------------------------------------------------
    def set_cursor_viewmodel(self, cursor_vm: CursorCompareViewModel) -> None:
        self._cursor_vm = cursor_vm

    def set_point_compare_enabled(self, enabled: bool) -> None:
        self._point_compare = bool(enabled)

    def clear_cursor_markers(self) -> None:
        if self._cursor_vm is not None:
            self._cursor_vm.clear()
        self._remove_cursor_artists()
        self.canvas.canvas.draw_idle()

    def _remove_cursor_artists(self) -> None:
        for artist in self._cursor_artists:
            try:
                artist.remove()
            except (ValueError, AttributeError):
                pass
        self._cursor_artists.clear()

    def _set_cursor_data(self, data) -> None:
        """Reset the cursor viewmodel after a (re)plot and notify listeners."""
        self._cursor_artists.clear()
        if self._cursor_vm is not None:
            self._cursor_vm.set_data(data)
            self.cursorPointsChanged.emit()

    def _on_canvas_click(self, event) -> None:
        if not self._point_compare or self._cursor_vm is None:
            return
        if event.inaxes is None or event.xdata is None or event.button != 1:
            return
        if self._cursor_vm.lock_at(event.xdata):
            point = self._cursor_vm.points[-1]
            marker = self.canvas.axes.axvline(
                point["x"], color=EATON_DARK_BLUE, linestyle="--", linewidth=1.0, alpha=0.75
            )
            self._cursor_artists.append(marker)
            self.canvas.canvas.draw_idle()
            self.cursorPointsChanged.emit()

    def _on_canvas_key(self, event) -> None:
        if event.key == "escape":
            self.clear_cursor_markers()
            self.cursorPointsChanged.emit()

    # ------------------------------------------------------------------
    # Rendering helpers
    # ------------------------------------------------------------------
    def _colours(self) -> list[str]:
        cycle_name = str(self.settings_vm.get("plot_appearance", "colour_cycle", "eaton"))
        return plot_render_service.resolve_plot_colours(cycle_name)

    def _line_width(self) -> float:
        try:
            return float(self.settings_vm.get("plot_appearance", "default_line_width", 1.5))
        except (TypeError, ValueError):
            return 1.5

    def _grid_visible(self) -> bool:
        return bool(self.settings_vm.get("plot_appearance", "grid_visible", True))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def generate_plot(
        self,
        x_col: str,
        y_cols: list[str],
        xmin: Optional[float] = None,
        xmax: Optional[float] = None,
        title: str = "Engineering Test Data",
        limit_lines: Optional[list[dict]] = None,
        secondary_y: Optional[list[str]] = None,
        plot_kind: str = "Line",
        use_filter: bool = False,
        cutoff: Optional[float] = None,
        order: int = 4,
    ) -> OperationResult:
        try:
            data = self.plot_vm.prepare_plot_data(x_col, y_cols, xmin, xmax)
        except ValueError as exc:
            return OperationResult.failure(str(exc))

        secondary_set = set(secondary_y or [])
        self.canvas.clear()
        axes = self.canvas.axes
        axes.set_prop_cycle(cycler(color=self._colours()))
        secondary_axes = None
        if secondary_set & set(data.y_map.keys()):
            secondary_axes = axes.twinx()
            secondary_axes.set_prop_cycle(
                cycler(color=plot_render_service.secondary_colour_cycle(self._colours()))
            )
        line_width = self._line_width()
        plotted = 0
        try:
            for label, series in data.y_map.items():
                x_for_label = data.x_map.get(label, data.x) if data.x_map else data.x
                frame = pd.DataFrame({"x": x_for_label, "y": series}).dropna()
                if frame.empty:
                    continue
                is_secondary = label in secondary_set and secondary_axes is not None
                target = secondary_axes if is_secondary else axes
                y_values = frame["y"].to_numpy(dtype=float)
                plot_label = label
                if use_filter:
                    fs = estimate_sampling_rate(x_for_label)
                    if fs is None:
                        return OperationResult.failure(
                            "Cannot estimate sampling frequency from the selected X-axis column."
                        )
                    if cutoff is None:
                        return OperationResult.failure("Please enter a low-pass filter cutoff frequency.")
                    y_values = lowpass_filter(y_values, cutoff_hz=cutoff, fs_hz=fs, order=order)
                    plot_label = f"{label} | LP {cutoff:g} Hz"
                if is_secondary:
                    plot_label = f"{plot_label} [Right Y]"
                self._plot_series(target, frame["x"].to_numpy(dtype=float), y_values, plot_label, plot_kind, line_width)
                plotted += 1
        except (ValueError, RuntimeError) as exc:
            return OperationResult.failure(str(exc))
        if plotted == 0:
            return OperationResult.failure("No numeric data was available for the selected columns.")

        self._draw_limit_lines(axes, limit_lines)
        axes.set_title(title)
        axes.set_xlabel(x_col)
        axes.set_ylabel("Selected Signals")
        if secondary_axes is not None:
            secondary_axes.set_ylabel("Secondary Axis Signals")
        axes.grid(self._grid_visible(), alpha=0.35)
        self._merge_legends(axes, secondary_axes)
        self.canvas.draw()
        self._last_plot_data = data
        self._last_x_col = x_col
        self._set_cursor_data(data)
        return OperationResult.success(f"Plotted {plotted} channel(s).")

    @staticmethod
    def _plot_series(axes, x, y, label: str, plot_kind: str, line_width: float) -> None:
        if plot_kind == "Scatter":
            axes.scatter(x, y, s=14, label=label)
        elif plot_kind == "Line + Markers":
            axes.plot(x, y, marker="o", markersize=3, linewidth=line_width, label=label)
        else:
            axes.plot(x, y, linewidth=line_width, label=label)

    @staticmethod
    def _merge_legends(axes, secondary_axes) -> None:
        handles, labels = axes.get_legend_handles_labels()
        if secondary_axes is not None:
            extra_handles, extra_labels = secondary_axes.get_legend_handles_labels()
            handles += extra_handles
            labels += extra_labels
        if handles:
            axes.legend(handles, labels, loc="best", fontsize=8)

    @staticmethod
    def _draw_limit_lines(axes, limit_lines: Optional[list[dict]]) -> None:
        """Overlay requirement limit lines (already normalised) with >=2 points."""
        for line in limit_lines or []:
            points = line.get("points", [])
            if len(points) < 2:
                continue
            xs = [point["x"] for point in points]
            ys = [point["y"] for point in points]
            limit_type = line.get("type", "Upper Limit")
            linestyle = ":" if limit_type == "Reference Line" else "--"
            label = f"{line.get('name', 'Limit')} [{limit_type}]"
            colour = line.get("color", EATON_DARK_BLUE)
            try:
                axes.plot(xs, ys, linestyle=linestyle, linewidth=1.6, color=colour, label=label)
            except (ValueError, KeyError):
                axes.plot(xs, ys, linestyle=linestyle, linewidth=1.6, color=EATON_DARK_BLUE, label=label)

    def generate_comparison_plot(
        self,
        items: list[dict],
        x_col: str,
        title: str = "Run Comparison",
        limit_lines: Optional[list[dict]] = None,
    ) -> OperationResult:
        """Draw prepared comparison items (one line per run/channel).

        Each item is ``{"label", "x", "y", "colour"}`` from
        :meth:`RunsComparisonViewModel.comparison_plot_items`.
        """
        if not items:
            return OperationResult.failure("No numeric comparison data was available for the enabled runs.")

        self.canvas.clear()
        axes = self.canvas.axes
        axes.set_prop_cycle(cycler(color=self._colours()))
        line_width = self._line_width()
        plotted = 0
        for item in items:
            frame = pd.DataFrame({"x": item.get("x"), "y": item.get("y")}).dropna()
            if frame.empty:
                continue
            axes.plot(frame["x"], frame["y"], label=item.get("label", ""), linewidth=line_width, color=item.get("colour"))
            plotted += 1
        if plotted == 0:
            return OperationResult.failure("No numeric comparison data was available for the enabled runs.")

        self._draw_limit_lines(axes, limit_lines)
        axes.set_title(title)
        axes.set_xlabel(x_col)
        axes.set_ylabel("Selected Signals")
        axes.grid(self._grid_visible(), alpha=0.35)
        axes.legend(loc="best", fontsize=8)
        self.canvas.draw()
        self._set_cursor_data(None)
        return OperationResult.success(f"Comparison plot generated for {plotted} series.")

    def generate_fft(self, x_col: str, y_cols: list[str]) -> OperationResult:
        try:
            data = self.plot_vm.prepare_plot_data(x_col, y_cols)
        except ValueError as exc:
            return OperationResult.failure(str(exc))
        fs = estimate_sampling_rate(data.x)
        if fs is None:
            return OperationResult.failure("Cannot estimate sampling frequency from the selected X-axis column.")

        window = str(self.settings_vm.get("engineering_analysis", "fft_window_function", "hanning"))
        overlap = int(self.settings_vm.get("engineering_analysis", "fft_overlap_percent", 50) or 0)

        self.canvas.clear()
        axes = self.canvas.axes
        axes.set_prop_cycle(cycler(color=self._colours()))
        plotted = 0
        for label, series in data.y_map.items():
            frame = pd.DataFrame({"y": series}).dropna()
            if len(frame) < 4:
                continue
            values = frame["y"].to_numpy(dtype=float)
            values = values - np.mean(values)
            freqs, amp = self.plot_vm.fft(values, fs, window, overlap)
            axes.plot(freqs, amp, label=label, linewidth=self._line_width())
            plotted += 1
        if plotted == 0:
            return OperationResult.failure("Not enough numeric data to generate FFT.")

        axes.set_title(f"FFT | {x_col}")
        axes.set_xlabel("Frequency [Hz]")
        axes.set_ylabel("Amplitude")
        axes.grid(self._grid_visible(), alpha=0.35)
        axes.legend(loc="best", fontsize=8)
        self.canvas.draw()
        self._set_cursor_data(None)
        return OperationResult.success(f"FFT plotted for {plotted} channel(s).")
