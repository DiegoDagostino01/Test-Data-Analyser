from __future__ import annotations

from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import matplotlib.figure as mfig
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
from matplotlib.colors import to_hex
from cycler import cycler
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.backends._backend_tk import NavigationToolbar2Tk
import numpy as np
import pandas as pd

from .config import (
    EATON_DARK_BLUE,
    EATON_DARK_GREY,
    EATON_MID_GREY,
    EATON_PLOT_COLORS,
    EATON_WHITE,
)
from .filters import estimate_sampling_rate, lowpass_filter
from .models import PlotData
from .utils import safe_name, _matching_x_column_for_y


COLOURBLIND_SAFE_COLORS = [
    "#0072B2", "#D55E00", "#009E73", "#CC79A7", "#F0E442",
    "#56B4E9", "#E69F00", "#000000",
]


class PlottingMixin:
    """Figure/canvas management, data preparation, plotting, FFT, legend and saving.

    Pure data preparation (``prepare_plot_data``) is kept separate from the
    Tkinter event handlers. Axis-limit helpers and numeric caching remain in
    ``gui_base.py`` and are reached through ``self`` via the method-resolution
    order.
    """

    # ------------------------------------------------------------------
    # Figure / Canvas reuse
    # ------------------------------------------------------------------
    def _plot_colours(self) -> list[str]:
        cycle_name = str(self._setting("plot_appearance", "colour_cycle", "eaton"))
        if cycle_name == "matplotlib":
            return [item["color"] for item in plt.rcParams["axes.prop_cycle"]]
        if cycle_name == "colourblind_safe":
            return COLOURBLIND_SAFE_COLORS
        return EATON_PLOT_COLORS

    def _plot_background_colour(self) -> str:
        configured = str(self._setting("plot_appearance", "plot_background_colour", EATON_WHITE) or EATON_WHITE)
        if self._is_dark_theme() and configured.upper() in ("#FFFFFF", "WHITE"):
            return self._theme_palette()["plot_bg"]
        return configured

    def _default_line_width(self) -> float:
        try:
            return float(self._setting("plot_appearance", "default_line_width", 1.5))
        except Exception:
            return 1.5

    def _default_marker_style(self) -> str | None:
        marker = str(self._setting("plot_appearance", "default_marker_style", "None"))
        return None if marker == "None" else marker

    def _apply_plot_text_settings(self) -> None:
        if self.axes is None:
            return
        title_size = int(self._setting("plot_appearance", "font_size_title", 14))
        axis_size = int(self._setting("plot_appearance", "font_size_axis_label", 12))
        tick_size = int(self._setting("plot_appearance", "font_size_tick_label", 10))
        scientific_enabled = bool(self._setting("axis_scaling", "scientific_notation_enabled", True))
        threshold = float(self._setting("axis_scaling", "scientific_notation_threshold", 1e4) or 1e4)
        exponent = max(1, int(np.floor(np.log10(abs(threshold))))) if threshold else 4
        for axis in (self.axes, self.secondary_axes):
            if axis is None:
                continue
            axis.title.set_fontsize(title_size)
            axis.xaxis.label.set_fontsize(axis_size)
            axis.yaxis.label.set_fontsize(axis_size)
            axis.tick_params(labelsize=tick_size)
            for axis_obj in (axis.xaxis, axis.yaxis):
                formatter = ticker.ScalarFormatter(useMathText=True)
                formatter.set_scientific(scientific_enabled)
                formatter.set_useOffset(scientific_enabled)
                if scientific_enabled:
                    formatter.set_powerlimits((exponent, exponent))
                axis_obj.set_major_formatter(formatter)

    def _style_axes(self) -> None:
        if self.axes is None:
            return
        palette = self._theme_palette()
        self.axes.set_facecolor(self._plot_background_colour())
        self.axes.title.set_color(palette["plot_text"])
        self.axes.xaxis.label.set_color(palette["plot_axis"])
        self.axes.yaxis.label.set_color(palette["plot_axis"])
        self.axes.tick_params(colors=palette["plot_axis"], which="both")
        for spine in self.axes.spines.values():
            spine.set_color(palette["plot_spine"])
        self.axes.set_prop_cycle(cycler(color=self._plot_colours()))

    def _ensure_figure_canvas(self) -> None:
        """Create figure + canvas once; on subsequent calls just clear & re-add axes."""
        if self.figure is None:
            # Destroy placeholder
            for child in self.plot_frame.winfo_children():
                child.destroy()
            self.figure = mfig.Figure(figsize=(9.5, 6.0), dpi=100,
                                      facecolor=self._plot_background_colour())
            self.canvas = FigureCanvasTkAgg(self.figure, master=self.plot_frame)
            self.toolbar_frame = ttk.Frame(self.plot_frame)
            try:
                self.toolbar = NavigationToolbar2Tk(self.canvas, self.toolbar_frame, pack_toolbar=False)
                self.toolbar.update()
                self.toolbar.pack(side="left", fill="x")
            except TypeError:
                self.toolbar = NavigationToolbar2Tk(self.canvas, self.toolbar_frame)
                self.toolbar.update()
            self._create_cursor_compare_button()
            if hasattr(self, "_apply_clickable_cursors"):
                self._apply_clickable_cursors(self.toolbar_frame)
            self.toolbar_frame.pack(side="bottom", fill="x")
            self.canvas.get_tk_widget().pack(side="top", fill="both", expand=True)
        else:
            self.figure.clear()

        self.figure.set_facecolor(self._plot_background_colour())
        self.axes = self.figure.add_subplot(111)
        self.secondary_axes = None
        self._style_axes()
        self.current_lines = []
        self.external_legend_required = False

    def _draw_figure(self) -> None:
        if self.canvas is not None:
            self.canvas.draw()

    # ------------------------------------------------------------------
    # Data preparation
    # ------------------------------------------------------------------
    def _x_series_for_y_column(self, selected_x_col: str, y_col: str) -> pd.Series:
        """Return the appropriate X series for a Y channel."""
        if self.df is None:
            return pd.Series(dtype=float)
        x_col = _matching_x_column_for_y(selected_x_col, y_col, self.df.columns)
        return self._get_numeric(x_col)

    def prepare_plot_data(self) -> PlotData:
        if self.df is None:
            raise ValueError("Please load a data file first.")
        x_col = self.x_col_var.get()
        y_cols = self.selected_y_columns()
        if not x_col:
            raise ValueError("Please select an X-axis column.")
        if not y_cols:
            raise ValueError("Please select at least one Y-axis column.")

        x = self._get_numeric(x_col)
        y_map = {col: self._get_numeric(col) for col in y_cols}
        x_map = {col: self._x_series_for_y_column(x_col, col) for col in y_cols}

        xmin = self.parse_limit(self.analysis_xmin_var.get()) if hasattr(self, "analysis_xmin_var") else None
        xmax = self.parse_limit(self.analysis_xmax_var.get()) if hasattr(self, "analysis_xmax_var") else None
        if xmin is not None or xmax is not None:
            if xmin is not None and xmax is not None and xmin > xmax:
                raise ValueError("Analysis Window Start X must be less than or equal to End X.")
            for col in list(y_map):
                x_for_col = x_map.get(col, x)
                mask = x_for_col.notna()
                if xmin is not None:
                    mask &= x_for_col >= xmin
                if xmax is not None:
                    mask &= x_for_col <= xmax
                x_map[col] = x_for_col.where(mask)
                y_map[col] = y_map[col].where(mask)
            global_mask = x.notna()
            if xmin is not None:
                global_mask &= x >= xmin
            if xmax is not None:
                global_mask &= x <= xmax
            x = x.where(global_mask)
        return PlotData(x=x, y_map=y_map, x_map=x_map)

    # ------------------------------------------------------------------
    # Plot generation
    # ------------------------------------------------------------------
    def generate_plot(self) -> None:
        if (
            hasattr(self, "comparison_mode_enabled")
            and self.comparison_mode_enabled.get()
        ):
            return self.generate_comparison_plot()
        try:
            data = self.prepare_plot_data()
            limits = self.manual_limits()
            y2min, y2max = self.secondary_manual_limits()
            if (not self.auto_fit_var.get() and not self.limits_have_visible_data(data, limits)):
                if not messagebox.askyesno("Axis limit warning", "The current manual axis limits appear to hide all selected data. Continue anyway?"):
                    return
            self._ensure_figure_canvas()
            assert self.axes is not None
            assert self.figure is not None
            secondary_y = set(self.selected_secondary_y_columns())
            if secondary_y:
                self.secondary_axes = self.axes.twinx()
                self.secondary_axes.set_facecolor("none")
                secondary_palette = self._theme_palette()
                self.secondary_axes.tick_params(colors=secondary_palette["plot_axis"], which="both")
                self.secondary_axes.yaxis.label.set_color(secondary_palette["plot_axis"])
                self.secondary_axes.spines["right"].set_color(secondary_palette["plot_spine"])
                colours = self._plot_colours()
                secondary_cycle = colours[5:] + colours[:5] if len(colours) > 5 else colours
                self.secondary_axes.set_prop_cycle(cycler(color=secondary_cycle))
            else:
                self.secondary_axes = None
            plot_kind = self.plot_kind_var.get()
            use_filter = self.use_filter_var.get()
            cutoff = float(self.cutoff_var.get()) if self.cutoff_var.get().strip() else None
            order = int(float(self.filter_order_var.get())) if self.filter_order_var.get().strip() else 4
            line_width = self._default_line_width()
            marker_style = self._default_marker_style()
            for label, y in data.y_map.items():
                target_axes = self.secondary_axes if label in secondary_y and self.secondary_axes is not None else self.axes
                x_for_label = data.x_map.get(label, data.x) if data.x_map else data.x
                fs = estimate_sampling_rate(x_for_label)
                frame = pd.DataFrame({"x": x_for_label, "y": y}).dropna()
                if frame.empty:
                    continue
                y_values = frame["y"].to_numpy(dtype=float)
                label_to_use = label
                if use_filter:
                    if fs is None:
                        raise ValueError("Cannot estimate sampling frequency from the selected X-axis column.")
                    if cutoff is None:
                        raise ValueError("Please enter a low-pass filter cutoff frequency.")
                    y_values = lowpass_filter(y_values, cutoff_hz=cutoff, fs_hz=fs, order=order)
                    label_to_use = f"{label} | LP {cutoff:g} Hz"
                if target_axes is self.secondary_axes:
                    label_to_use = f"{label_to_use} [Right Y]"
                if plot_kind == "Scatter":
                    artist = target_axes.scatter(frame["x"], y_values, s=14, label=label_to_use)
                elif plot_kind == "Line + Markers":
                    (artist,) = target_axes.plot(frame["x"], y_values, marker=marker_style or "o", markersize=3, linewidth=line_width, label=label_to_use)
                else:
                    (artist,) = target_axes.plot(frame["x"], y_values, marker=marker_style, linewidth=line_width, label=label_to_use)
                self.current_lines.append(artist)
            if not self.current_lines:
                raise ValueError("No numeric data was available for the selected columns.")
            self.axes.set_title(self.title_var.get() or "Engineering Test Data")
            self.axes.set_xlabel(self.x_label_var.get() or self.x_col_var.get())
            self.axes.set_ylabel(self.y_label_var.get() or "Primary Axis Signals")
            if self.secondary_axes is not None:
                self.secondary_axes.set_ylabel(self.y2_label_var.get() or "Secondary Axis Signals")
                self.secondary_axes.yaxis.set_major_locator(ticker.MaxNLocator(nbins=10))
            self._apply_plot_text_settings()
            self.axes.grid(self.grid_var.get(), which="both", alpha=0.35, color=self._theme_palette()["plot_grid"])
            self.axes.xaxis.set_major_locator(ticker.MaxNLocator(nbins=10))
            self.axes.yaxis.set_major_locator(ticker.MaxNLocator(nbins=10))
            if self.auto_fit_var.get():
                # Keep the plotted axes consistent with the values displayed in
                # Section 6. Manual Axis Limits. This is especially important
                # when a secondary Y-axis exists: Matplotlib autoscale would
                # otherwise override the filled-in limit fields.
                self.fill_axis_limits_from_data()
                xmin = self.parse_limit(self.xmin_var.get())
                xmax = self.parse_limit(self.xmax_var.get())
                ymin = self.parse_limit(self.ymin_var.get())
                ymax = self.parse_limit(self.ymax_var.get())
                y2min, y2max = self.secondary_manual_limits()
                if xmin is not None or xmax is not None:
                    self.axes.set_xlim(left=xmin, right=xmax)
                    if self.secondary_axes is not None:
                        self.secondary_axes.set_xlim(left=xmin, right=xmax)
                if ymin is not None or ymax is not None:
                    self.axes.set_ylim(bottom=ymin, top=ymax)
                if self.secondary_axes is not None and (y2min is not None or y2max is not None):
                    self.secondary_axes.set_ylim(bottom=y2min, top=y2max)
            else:
                xmin, xmax, ymin, ymax = limits
                if xmin is not None or xmax is not None:
                    self.axes.set_xlim(left=xmin, right=xmax)
                    if self.secondary_axes is not None:
                        self.secondary_axes.set_xlim(left=xmin, right=xmax)
                if ymin is not None or ymax is not None:
                    self.axes.set_ylim(bottom=ymin, top=ymax)
                if self.secondary_axes is not None and (y2min is not None or y2max is not None):
                    self.secondary_axes.set_ylim(bottom=y2min, top=y2max)
            self._plot_limit_lines()
            # Do not call relim/autoscale_view() after applying explicit limits;
            # doing so would make the graph disagree with the Manual Axis Limits
            # fields shown in the UI.
            self._apply_legend_or_panel()
            self.figure.tight_layout()
            self._draw_figure()
            self._connect_cursor_readout(data)
            self.update_stats()
            self.update_raw_data_view()
            if hasattr(self, "limit_summary_text"):
                self._set_text_widget(self.limit_summary_text, self._calculate_limit_margins(data))
            self._current_plot_profile()["generated"] = True
            self._capture_current_plot_profile()
        except Exception as exc:
            messagebox.showerror("Plot error", str(exc))

    def _fft_window(self, size: int) -> np.ndarray:
        window_name = str(self._setting("engineering_analysis", "fft_window_function", "hanning"))
        if window_name == "hamming":
            return np.hamming(size)
        if window_name == "blackman":
            return np.blackman(size)
        if window_name == "rectangular":
            return np.ones(size)
        return np.hanning(size)

    def _fft_spectrum(self, values: np.ndarray, fs: float) -> tuple[np.ndarray, np.ndarray]:
        n = len(values)
        overlap_percent = int(self._setting("engineering_analysis", "fft_overlap_percent", 50) or 0)
        overlap_percent = max(0, min(90, overlap_percent))
        if overlap_percent <= 0 or n < 128:
            segment_length = n
        else:
            segment_length = max(64, n // 4)
        step = max(1, int(segment_length * (1.0 - overlap_percent / 100.0)))

        spectra: list[np.ndarray] = []
        freqs = np.fft.rfftfreq(segment_length, d=1.0 / fs)
        for start in range(0, n - segment_length + 1, step):
            segment = values[start:start + segment_length]
            window = self._fft_window(segment_length)
            correction = float(np.mean(window)) or 1.0
            spectra.append(np.abs(np.fft.rfft(segment * window)) * 2.0 / (segment_length * correction))
        if not spectra:
            window = self._fft_window(n)
            correction = float(np.mean(window)) or 1.0
            return np.fft.rfftfreq(n, d=1.0 / fs), np.abs(np.fft.rfft(values * window)) * 2.0 / (n * correction)
        return freqs, np.mean(spectra, axis=0)

    # ------------------------------------------------------------------
    # FFT plot
    # ------------------------------------------------------------------
    def generate_fft_plot(self) -> None:
        try:
            data = self.prepare_plot_data()
            fs = estimate_sampling_rate(data.x)
            if fs is None:
                raise ValueError(
                    "Cannot estimate sampling frequency from "
                    "the selected X-axis column.")

            self._ensure_figure_canvas()
            assert self.axes is not None
            assert self.figure is not None

            for label, y in data.y_map.items():
                frame = pd.DataFrame({"x": data.x, "y": y}).dropna()
                if len(frame) < 4:
                    continue
                values = frame["y"].to_numpy(dtype=float)
                values = values - np.mean(values)
                freqs, amp = self._fft_spectrum(values, fs)
                (line,) = self.axes.plot(freqs, amp, linewidth=self._default_line_width(), label=label)
                self.current_lines.append(line)
            if not self.current_lines:
                raise ValueError(
                    "Not enough numeric data to generate FFT.")
            self.axes.set_title(
                f"FFT | {self.title_var.get() or 'Engineering Test Data'}")
            self.axes.set_xlabel("Frequency [Hz]")
            self.axes.set_ylabel("Amplitude")
            self._apply_plot_text_settings()
            self.axes.grid(self.grid_var.get(), which="both", alpha=0.35)
            self._apply_legend_or_panel()
            self.figure.tight_layout()
            self._draw_figure()
            self.update_raw_data_view()
            self._current_plot_profile()["generated"] = True
            self._capture_current_plot_profile()
        except Exception as exc:
            messagebox.showerror("FFT error", str(exc))

    # ------------------------------------------------------------------
    # Legend
    # ------------------------------------------------------------------
    def _legend_handle_colour(self, handle: object) -> str:
        colour = None
        if hasattr(handle, "get_color"):
            colour = handle.get_color()
        elif hasattr(handle, "get_facecolor"):
            colours = handle.get_facecolor()
            if len(colours):
                colour = colours[0]
        elif hasattr(handle, "get_edgecolor"):
            colours = handle.get_edgecolor()
            if len(colours):
                colour = colours[0]
        try:
            return to_hex(colour)
        except Exception:
            return EATON_DARK_BLUE

    def _update_legend_panel(self, handles: list[object], labels: list[str]) -> None:
        for child in self.legend_inner.winfo_children():
            child.destroy()
        if not labels:
            ttk.Label(
                self.legend_inner,
                text="Legend will appear here when more than the "
                     "in-plot threshold is selected.",
                wraplength=220).pack(anchor="w", padx=8, pady=8)
            return
        for i, (handle, label) in enumerate(zip(handles, labels), start=1):
            row = ttk.Frame(self.legend_inner)
            row.pack(anchor="w", fill="x", padx=8, pady=2)
            tk.Label(
                row,
                width=2,
                height=1,
                bg=self._legend_handle_colour(handle),
                relief="solid",
                bd=1,
            ).pack(side="left", padx=(0, 6), pady=2)
            ttk.Label(row, text=f"{i}. {label}", wraplength=220).pack(side="left", anchor="w", fill="x", expand=True)

    def _style_legend(self, legend) -> None:
        if legend is None:
            return
        palette = self._theme_palette()
        frame = legend.get_frame()
        frame.set_facecolor(palette["plot_bg"])
        frame.set_edgecolor(palette["plot_spine"])
        for text in legend.get_texts():
            text.set_color(palette["plot_text"])

    def _apply_legend_or_panel(self) -> None:
        if self.axes is None:
            return
        handles, labels = self.axes.get_legend_handles_labels()
        if self.secondary_axes is not None:
            handles2, labels2 = self.secondary_axes.get_legend_handles_labels()
            handles += handles2
            labels += labels2
        max_in_plot = max(1, int(self.legend_threshold_var.get() or 10))
        self.external_legend_required = len(labels) > max_in_plot
        for axis in (self.axes, self.secondary_axes):
            if axis is None:
                continue
            legend = axis.get_legend()
            if legend:
                legend.remove()
        if self.external_legend_required:
            self._update_legend_panel(handles, labels)
        else:
            self._update_legend_panel([], [])
            legend_size = int(self._setting("plot_appearance", "font_size_legend", 10))
            legend = self.axes.legend(handles, labels, loc=self.legend_location_var.get() or "best", fontsize=legend_size)
            self._style_legend(legend)

    # ------------------------------------------------------------------
    # Save helpers
    # ------------------------------------------------------------------
    def _save_figure_with_legend(self, filename: str | Path) -> None:
        if self.figure is None or self.axes is None:
            raise ValueError("No plot is available to save.")
        temp_legend = None
        if self.external_legend_required:
            handles, labels = self.axes.get_legend_handles_labels()
            if self.secondary_axes is not None:
                handles2, labels2 = self.secondary_axes.get_legend_handles_labels()
                handles += handles2
                labels += labels2
            legend_size = int(self._setting("plot_appearance", "font_size_legend", 10))
            temp_legend = self.figure.legend(handles, labels, loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=legend_size, frameon=True)
            self._style_legend(temp_legend)
            self.figure.subplots_adjust(right=0.78)
        try:
            dpi = int(self._setting("export", "default_dpi", 150))
            self.figure.savefig(filename, dpi=dpi, bbox_inches="tight")
        finally:
            if temp_legend is not None:
                temp_legend.remove()
                self.figure.subplots_adjust(right=0.95)
                if self.canvas:
                    self.canvas.draw_idle()

    def save_current_plot(self) -> None:
        if self.figure is None:
            messagebox.showwarning("No plot",
                                   "Please generate a plot first.")
            return
        image_format = str(self._setting("export", "default_image_format", "png") or "png")
        initial_name = safe_name(self.title_var.get())
        if bool(self._setting("export", "auto_timestamp_filenames", True)):
            initial_name = f"{initial_name}_{datetime.now():%Y%m%d_%H%M%S}"
        export_dir = str(self._setting("export", "default_export_directory", "") or "")
        available_formats = self._setting("export", "available_image_formats", ["png", "svg", "pdf"])
        filetypes = [(fmt.upper(), f"*.{fmt}") for fmt in available_formats]
        filename = filedialog.asksaveasfilename(
            title="Save plot", defaultextension=f".{image_format}",
            filetypes=filetypes + [("JPEG", "*.jpg")],
            initialdir=export_dir if export_dir and Path(export_dir).exists() else None,
            initialfile=f"{initial_name}.{image_format}")
        if not filename:
            return
        try:
            self._save_figure_with_legend(filename)
            messagebox.showinfo("Saved", f"Saved plot:\n{filename}")
        except Exception as exc:
            messagebox.showerror("Save error", str(exc))

    def save_outputs(self) -> None:
        if self.df is None:
            messagebox.showwarning("No data", "Please load data first.")
            return
        base = filedialog.asksaveasfilename(
            title="Save outputs as", defaultextension=".xlsx",
            filetypes=[("Excel workbook", "*.xlsx")],
            initialdir=str(self._setting("export", "default_export_directory", "") or "") or None,
            initialfile="test_data_analysis_outputs.xlsx")
        if not base:
            return
        xlsx_path = Path(base)
        fig_path = xlsx_path.with_suffix(".png")
        try:
            y_cols = self.selected_y_columns()
            stats = self._compute_statistics(y_cols)
            with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
                self.df.to_excel(writer, sheet_name="Cleaned Data", index=False)
                if bool(self._setting("export", "include_statistics_in_export", False)):
                    stats.to_excel(writer, sheet_name="Statistics")
            if self.figure is not None:
                self._save_figure_with_legend(fig_path)
            saved_msg = f"Saved:\n{xlsx_path}"
            if self.figure is not None:
                saved_msg += f"\n{fig_path}"
            messagebox.showinfo("Saved", saved_msg)
        except Exception as exc:
            messagebox.showerror("Save error", str(exc))

    # ------------------------------------------------------------------
    # Clear plot
    # ------------------------------------------------------------------
    def clear_plot(self) -> None:
        if self.figure is not None:
            plt.close(self.figure)
        self.figure = None
        self.axes = None
        self.canvas = None
        self.toolbar = None
        self.current_lines = []
        self.external_legend_required = False
        if hasattr(self, "plot_frame"):
            for child in self.plot_frame.winfo_children():
                child.destroy()
            ttk.Label(
                self.plot_frame,
                text="Load a data file, choose X/Y columns, "
                     "then click Generate Plot.",
                anchor="center",
                font=("Segoe UI", 12),
                foreground=EATON_MID_GREY,
            ).pack(fill="both", expand=True)
        if hasattr(self, "legend_inner"):
            self._update_legend_panel([], [])
