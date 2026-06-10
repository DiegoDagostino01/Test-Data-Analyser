"""Plot workspace panel.

Embeds the Matplotlib Qt canvas and renders the active selection through the
framework-independent :class:`PlotWorkspaceViewModel`. Data preparation and FFT
live in the viewmodel/services; colour-cycle resolution is exposed through the
settings viewmodel. This panel only orchestrates rendering onto the canvas.
"""
from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Optional

from cycler import cycler
from matplotlib.colors import to_hex
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ...core.config import EATON_DARK_BLUE
from ...services.results import OperationResult
from ...viewmodels.cursor_compare_vm import CursorCompareViewModel
from ...viewmodels.plot_workspace_vm import PlotWorkspaceViewModel
from ...viewmodels.settings_vm import SettingsViewModel
from ..adapters.matplotlib_qt_adapter import LEGEND_DISPLAY_GRAPH, LEGEND_DISPLAY_PANEL, MatplotlibCanvas


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
        self._legend_display = LEGEND_DISPLAY_PANEL

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.canvas = MatplotlibCanvas(self)
        self.canvas.toolbar.set_legend_display_controller(self.legend_display, self.set_legend_display)
        self.canvas.toolbar.set_export_preparer(self._legend_export_context)
        self.legend_panel = self._build_legend_panel()
        layout.addWidget(self.canvas, stretch=1)
        layout.addWidget(self.legend_panel)

        self.canvas.canvas.mpl_connect("button_press_event", self._on_canvas_click)
        self.canvas.canvas.mpl_connect("key_press_event", self._on_canvas_key)

    def _build_legend_panel(self) -> QWidget:
        panel = QFrame()
        panel.setObjectName("EatonPanel")
        panel.setMinimumWidth(210)
        panel.setMaximumWidth(260)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(8, 8, 8, 8)
        heading = QLabel("Legend")
        heading.setObjectName("PanelHeading")
        layout.addWidget(heading)

        self.legend_table = QTableWidget(0, 2)
        self.legend_table.setHorizontalHeaderLabels(["", "Series"])
        self.legend_table.verticalHeader().setVisible(False)
        self.legend_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.legend_table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self.legend_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        self.legend_table.horizontalHeader().resizeSection(0, 28)
        self.legend_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self.legend_table, stretch=1)
        return panel

    def legend_display(self) -> str:
        return self._legend_display

    def set_legend_display(self, display: str) -> None:
        self._legend_display = LEGEND_DISPLAY_GRAPH if display == LEGEND_DISPLAY_GRAPH else LEGEND_DISPLAY_PANEL
        self._refresh_current_legend()

    def current_axis_appearance(self) -> dict[str, Any]:
        """Read the title, axis labels, and axis limits from the live plot.

        Captures any edits made through the Matplotlib Figure Options dialog so
        they can be persisted in the session and re-applied on load. Returns an
        empty dict when no plot has been generated. ``auto_fit_axes`` is reported
        as ``False`` because the captured limits describe the exact on-screen
        view, which should be reproduced verbatim on restore.
        """
        axes = self.canvas.axes
        if axes not in self.canvas.figure.axes:
            return {}
        secondary = self._secondary_axes()
        xmin, xmax = axes.get_xlim()
        ymin, ymax = axes.get_ylim()
        limits = {
            "xmin": self._format_limit(xmin),
            "xmax": self._format_limit(xmax),
            "ymin": self._format_limit(ymin),
            "ymax": self._format_limit(ymax),
            "y2min": "",
            "y2max": "",
        }
        if secondary is not None:
            y2min, y2max = secondary.get_ylim()
            limits["y2min"] = self._format_limit(y2min)
            limits["y2max"] = self._format_limit(y2max)
        return {
            "title": axes.get_title(),
            "x_label": axes.get_xlabel(),
            "y_label": axes.get_ylabel(),
            "secondary_y_label": secondary.get_ylabel() if secondary is not None else "",
            "axis_limits": limits,
            "auto_fit_axes": False,
        }

    @staticmethod
    def _format_limit(value: float) -> str:
        return f"{float(value):.6g}"

    def save_plot_png(self, path: str) -> OperationResult:
        """Save the current figure to an image file (PNG by default).

        Reuses the legend export context so the right-side panel legend is baked
        into the image, mirroring the toolbar's save button. Fails cleanly when
        nothing has been plotted yet.
        """
        if not self._has_plot_content():
            return OperationResult.failure("Generate a plot before saving an image.")
        target = path
        if os.path.splitext(target)[1].lower() not in (".png", ".svg", ".pdf", ".jpg", ".jpeg"):
            target = f"{target}.png"
        try:
            dpi = int(self.settings_vm.get("export", "default_dpi", 150) or 150)
        except (TypeError, ValueError):
            dpi = 150
        try:
            with self._legend_export_context():
                self.canvas.figure.savefig(target, dpi=dpi, bbox_inches="tight")
        except Exception as exc:
            return OperationResult.failure(f"Could not save the plot image: {exc}")
        return OperationResult.success(f"Plot image saved:\n{target}", payload=target)

    def _has_plot_content(self) -> bool:
        for axes in self.canvas.figure.axes:
            if axes.get_lines() or axes.collections:
                return True
        return False

    @contextmanager
    def _legend_export_context(self):
        """Temporarily draw the side-panel legend onto the figure for image export.

        In panel mode the visible legend lives in a Qt widget beside the canvas,
        so it is absent from ``savefig`` output. This adds a matching Matplotlib
        legend for the duration of the export, then removes it and repaints so
        the on-screen figure stays clean.
        """
        temporary_legend = None
        if self._legend_display == LEGEND_DISPLAY_PANEL and self.canvas.axes in self.canvas.figure.axes:
            handles, labels = self._legend_handles_and_labels(self.canvas.axes, self._secondary_axes())
            if handles:
                temporary_legend = self.canvas.axes.legend(handles, labels, loc="best", fontsize=8)
        try:
            yield
        finally:
            if temporary_legend is not None:
                temporary_legend.remove()
                self.canvas.canvas.draw_idle()

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
        resolver = getattr(self.settings_vm, "plot_colours", None)
        if callable(resolver):
            return resolver()
        return SettingsViewModel.plot_colours(self.settings_vm)

    def _secondary_colours(self, colours: list[str]) -> list[str]:
        resolver = getattr(self.settings_vm, "secondary_plot_colours", None)
        if callable(resolver):
            return resolver(colours)
        return SettingsViewModel.secondary_plot_colours(self.settings_vm, colours)

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
        x_label: str = "",
        y_label: str = "",
        secondary_y_label: str = "",
        axis_limits: Optional[dict[str, Optional[float]]] = None,
        auto_fit_axes: bool = True,
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
        colours = self._colours()
        axes.set_prop_cycle(cycler(color=colours))
        series_result = self.plot_vm.plot_series(
            data,
            secondary_y=secondary_set,
            use_filter=use_filter,
            cutoff=cutoff,
            order=order,
        )
        if not series_result.ok:
            return series_result
        series_items = series_result.payload if isinstance(series_result.payload, list) else []
        secondary_axes = None
        if any(bool(item.get("secondary")) for item in series_items):
            secondary_axes = axes.twinx()
            secondary_axes.set_prop_cycle(cycler(color=self._secondary_colours(colours)))
        line_width = self._line_width()
        plotted = 0
        for item in series_items:
            target = secondary_axes if item.get("secondary") and secondary_axes is not None else axes
            self._plot_series(target, item["x"], item["y"], str(item.get("label", "")), plot_kind, line_width)
            plotted += 1
        if plotted == 0:
            return OperationResult.failure("No numeric data was available for the selected columns.")

        self._draw_limit_lines(axes, limit_lines)
        axes.set_title(title.strip() or "Engineering Test Data")
        axes.set_xlabel(x_label.strip() or x_col)
        axes.set_ylabel(y_label.strip() or "Selected Signals")
        if secondary_axes is not None:
            secondary_axes.set_ylabel(secondary_y_label.strip() or "Secondary Axis Signals")
        self._apply_axis_padding(axes, secondary_axes, auto_fit_axes)
        self._apply_axis_limits(axes, secondary_axes, axis_limits or {}, auto_fit_axes)
        axes.grid(self._grid_visible(), alpha=0.35)
        handles, labels = self._legend_handles_and_labels(axes, secondary_axes)
        self._apply_legend_display(axes, handles, labels)
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
    def _legend_handles_and_labels(axes, secondary_axes):
        handles, labels = axes.get_legend_handles_labels()
        if secondary_axes is not None:
            extra_handles, extra_labels = secondary_axes.get_legend_handles_labels()
            handles += extra_handles
            labels += extra_labels
        return handles, labels

    def _update_legend_table(self, handles, labels) -> None:
        self.legend_table.setRowCount(0)
        for handle, label in zip(handles, labels):
            if not label:
                continue
            row = self.legend_table.rowCount()
            self.legend_table.insertRow(row)
            swatch = QTableWidgetItem("")
            swatch.setFlags(Qt.ItemFlag.ItemIsEnabled)
            swatch.setBackground(QColor(self._legend_colour(handle)))
            text = QTableWidgetItem(label)
            text.setFlags(Qt.ItemFlag.ItemIsEnabled)
            self.legend_table.setItem(row, 0, swatch)
            self.legend_table.setItem(row, 1, text)

    def _apply_legend_display(self, axes, handles, labels) -> None:
        self._update_legend_table(handles, labels)
        self.legend_panel.setVisible(self._legend_display == LEGEND_DISPLAY_PANEL)
        self._remove_canvas_legends()
        if self._legend_display == LEGEND_DISPLAY_GRAPH and handles:
            axes.legend(handles, labels, loc="best", fontsize=8)

    def _refresh_current_legend(self) -> None:
        if self.canvas.axes not in self.canvas.figure.axes:
            return
        handles, labels = self._legend_handles_and_labels(self.canvas.axes, self._secondary_axes())
        self._apply_legend_display(self.canvas.axes, handles, labels)
        self.canvas.canvas.draw_idle()

    def _secondary_axes(self):
        for axes in self.canvas.figure.axes:
            if axes is not self.canvas.axes:
                return axes
        return None

    def _remove_canvas_legends(self) -> None:
        for axes in self.canvas.figure.axes:
            legend = axes.get_legend()
            if legend is not None:
                legend.remove()

    @staticmethod
    def _legend_colour(handle) -> str:
        try:
            colour = handle.get_color()
            return to_hex(colour)
        except Exception:
            pass
        try:
            colours = handle.get_facecolors()
            if len(colours):
                return to_hex(colours[0])
        except Exception:
            pass
        return EATON_DARK_BLUE

    def _apply_axis_padding(self, axes, secondary_axes, auto_fit_axes: bool) -> None:
        """Apply the user-configured X/Y autoscale padding (margins).

        Only affects auto-fitted axes; explicit limits already define their own
        range. Disabling an axis sets its margin to zero so the data spans the
        full axis, while enabling uses the configured percentage (default 5%).
        """
        if not auto_fit_axes:
            return
        pad_x = self._axis_pad_fraction("pad_x_axis", "pad_x_percent")
        pad_y = self._axis_pad_fraction("pad_y_axis", "pad_y_percent")
        axes.margins(x=pad_x, y=pad_y)
        if secondary_axes is not None:
            secondary_axes.margins(y=pad_y)

    def _axis_pad_fraction(self, enabled_key: str, percent_key: str) -> float:
        if not bool(self.settings_vm.get("axis_scaling", enabled_key, True)):
            return 0.0
        try:
            percent = float(self.settings_vm.get("axis_scaling", percent_key, 5))
        except (TypeError, ValueError):
            percent = 5.0
        return max(0.0, percent / 100.0)

    @staticmethod
    def _apply_axis_limits(axes, secondary_axes, axis_limits: dict[str, Optional[float]], auto_fit_axes: bool) -> None:
        if auto_fit_axes:
            return
        PlotWorkspace._set_axis_range(axes.set_xlim, axes.get_xlim, axis_limits.get("xmin"), axis_limits.get("xmax"))
        PlotWorkspace._set_axis_range(axes.set_ylim, axes.get_ylim, axis_limits.get("ymin"), axis_limits.get("ymax"))
        if secondary_axes is not None:
            PlotWorkspace._set_axis_range(
                secondary_axes.set_ylim,
                secondary_axes.get_ylim,
                axis_limits.get("y2min"),
                axis_limits.get("y2max"),
            )

    @staticmethod
    def _set_axis_range(setter, getter, minimum: Optional[float], maximum: Optional[float]) -> None:
        if minimum is None and maximum is None:
            return
        current_min, current_max = getter()
        lower = current_min if minimum is None else minimum
        upper = current_max if maximum is None else maximum
        if lower < upper:
            setter(lower, upper)

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
        for item in self.plot_vm.comparison_series(items):
            axes.plot(item["x"], item["y"], label=item.get("label", ""), linewidth=line_width, color=item.get("colour"))
            plotted += 1
        if plotted == 0:
            return OperationResult.failure("No numeric comparison data was available for the enabled runs.")

        self._draw_limit_lines(axes, limit_lines)
        axes.set_title(title)
        axes.set_xlabel(x_col)
        axes.set_ylabel("Selected Signals")
        axes.grid(self._grid_visible(), alpha=0.35)
        handles, labels = self._legend_handles_and_labels(axes, None)
        self._apply_legend_display(axes, handles, labels)
        self.canvas.draw()
        self._set_cursor_data(None)
        return OperationResult.success(f"Comparison plot generated for {plotted} series.")

    def generate_fft(self, x_col: str, y_cols: list[str]) -> OperationResult:
        try:
            data = self.plot_vm.prepare_plot_data(x_col, y_cols)
        except ValueError as exc:
            return OperationResult.failure(str(exc))
        fs = self.plot_vm.sampling_rate(data)
        if fs is None:
            return OperationResult.failure("Cannot estimate sampling frequency from the selected X-axis column.")

        window = str(self.settings_vm.get("engineering_analysis", "fft_window_function", "hanning"))
        overlap = int(self.settings_vm.get("engineering_analysis", "fft_overlap_percent", 50) or 0)

        self.canvas.clear()
        axes = self.canvas.axes
        axes.set_prop_cycle(cycler(color=self._colours()))
        plotted = 0
        for item in self.plot_vm.fft_series(data, fs, window, overlap):
            axes.plot(item["x"], item["y"], label=item.get("label", ""), linewidth=self._line_width())
            plotted += 1
        if plotted == 0:
            return OperationResult.failure("Not enough numeric data to generate FFT.")

        axes.set_title(f"FFT | {x_col}")
        axes.set_xlabel("Frequency [Hz]")
        axes.set_ylabel("Amplitude")
        axes.grid(self._grid_visible(), alpha=0.35)
        handles, labels = self._legend_handles_and_labels(axes, None)
        self._apply_legend_display(axes, handles, labels)
        self.canvas.draw()
        self._set_cursor_data(None)
        return OperationResult.success(f"FFT plotted for {plotted} channel(s).")
