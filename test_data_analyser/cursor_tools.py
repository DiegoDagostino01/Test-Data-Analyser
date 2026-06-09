from __future__ import annotations

from typing import Any, Optional
import tkinter as tk
from tkinter import messagebox

import numpy as np
import pandas as pd

from .config import EATON_BLUE, EATON_DARK_BLUE, EATON_DARK_GREY, EATON_WHITE
from .models import PlotData


class CursorToolsMixin:
    """Live cursor readout, locked point comparison, and related actions.

    Relies on shared state created in ``gui_base.py`` (``self.axes``,
    ``self.secondary_axes``, ``self.canvas``, ``self.toolbar_frame``,
    ``self._cursor_points`` and the cursor table/text widgets) and on the
    generic ``self._set_text_widget`` / ``self._clear_treeview`` helpers.
    """

    def _cursor_decimal_places(self) -> int:
        if not hasattr(self, "_setting"):
            return 4
        try:
            return int(self._setting("axis_scaling", "decimal_places_cursor", 4))
        except Exception:
            return 4

    def _format_cursor_number(self, value: Any) -> str:
        if value is None or pd.isna(value):
            return ""
        if isinstance(value, (float, int, np.floating, np.integer)):
            return f"{float(value):.{self._cursor_decimal_places()}f}"
        return str(value)

    def _set_cursor_text(self, content: str) -> None:
        """Compatibility wrapper: show cursor information in a table where possible."""
        if hasattr(self, "cursor_status_var"):
            first_line = content.splitlines()[0] if content else ""
            self.cursor_status_var.set(first_line)
        if hasattr(self, "cursor_tree"):
            if self._cursor_points and content.startswith("LOCKED CURSOR POINTS"):
                self._refresh_cursor_table()
            else:
                self._show_cursor_message(content)
        elif hasattr(self, "cursor_text"):
            self._set_text_widget(self.cursor_text, content)

    def _show_cursor_message(self, content: str) -> None:
        if not hasattr(self, "cursor_tree"):
            return
        self._clear_treeview(self.cursor_tree)
        self.cursor_tree["columns"] = ["Message"]
        self.cursor_tree.heading("Message", text="Cursor Readout")
        self.cursor_tree.column("Message", width=900, anchor="w", stretch=True)
        lines = content.splitlines() or [""]
        for index, line in enumerate(lines):
            self.cursor_tree.insert(
                "", "end", values=[line], tags=(self._tree_row_tag(index),)
            )

    def _refresh_cursor_table(self) -> None:
        if not hasattr(self, "cursor_tree"):
            return
        self._clear_treeview(self.cursor_tree)
        if not self._cursor_points:
            self._show_cursor_message("Generate a plot, move over the graph for live readout. Enable Point Compare to lock point(s); press ESC to clear.")
            return
        channels = list(self._cursor_points[0]["values"].keys())
        columns = ["Type", "Point", "Index / Ref", "X / ΔX"] + channels
        self.cursor_tree["columns"] = columns
        for col in columns:
            self.cursor_tree.heading(col, text=col)
            width = 110
            if col in {"Type", "Point"}:
                width = 90
            elif col == "Index / Ref":
                width = 100
            elif col == "X / ΔX":
                width = 110
            else:
                width = max(130, min(280, len(col) * 8))
            self.cursor_tree.column(col, width=width, anchor="center" if col in {"Type", "Point", "Index / Ref", "X / ΔX"} else "w", stretch=False)

        def fmt(value: Any) -> str:
            return self._format_cursor_number(value)

        row_index = 0
        for p in self._cursor_points:
            row = ["Point", p["point_no"], p["index"], fmt(p["x"])] + [fmt(p["values"].get(c)) for c in channels]
            self.cursor_tree.insert(
                "", "end", values=row, tags=(self._tree_row_tag(row_index),)
            )
            row_index += 1
        if len(self._cursor_points) >= 2:
            base = self._cursor_points[0]
            for p in self._cursor_points[1:]:
                delta_values = []
                for c in channels:
                    a, b = p["values"].get(c), base["values"].get(c)
                    delta_values.append("" if a is None or b is None or pd.isna(a) or pd.isna(b) else fmt(a - b))
                row = ["Δ vs P1", f"P{p['point_no']} - P1", f"{p['index']} - {base['index']}", fmt(p["x"] - base["x"])] + delta_values
                self.cursor_tree.insert(
                    "", "end", values=row, tags=(self._tree_row_tag(row_index),)
                )
                row_index += 1
        if hasattr(self, "cursor_status_var"):
            self.cursor_status_var.set(f"Locked cursor points: {len(self._cursor_points)}. Comparison rows show delta versus Point 1.")

    def _format_cursor_points(self) -> str:
        if not self._cursor_points:
            return "Generate a plot, move over the graph for live readout. Enable Point Compare to lock point(s); press ESC to clear."
        channels = list(self._cursor_points[0]["values"].keys())
        short_names = {c: (c[:34] + "…" if len(c) > 35 else c) for c in channels}
        lines = ["LOCKED CURSOR POINTS", "Tip: use the horizontal scrollbar for long channel names. Press ESC to clear locked points.", ""]
        header = ["Point", "Index", "X"] + [short_names[c] for c in channels]
        rows = []
        for p in self._cursor_points:
            rows.append([str(p["point_no"]), str(p["index"]), self._format_cursor_number(p["x"])] + [self._format_cursor_number(p["values"].get(c)) for c in channels])
        widths = [max(len(header[i]), *(len(r[i]) for r in rows)) for i in range(len(header))]
        lines.append("  ".join(header[i].ljust(widths[i]) for i in range(len(header))))
        lines.append("  ".join("-"*widths[i] for i in range(len(header))))
        lines += ["  ".join(r[i].ljust(widths[i]) for i in range(len(header))) for r in rows]
        if len(self._cursor_points) >= 2:
            base = self._cursor_points[0]
            lines += ["", "COMPARISON VS POINT 1"]
            ch = ["Point", "ΔX"] + [f"Δ {short_names[c]}" for c in channels]
            cr = []
            for p in self._cursor_points[1:]:
                row = [str(p["point_no"]), self._format_cursor_number(p["x"] - base["x"])]
                for c in channels:
                    a, b = p["values"].get(c), base["values"].get(c)
                    row.append("" if a is None or b is None or pd.isna(a) or pd.isna(b) else self._format_cursor_number(a - b))
                cr.append(row)
            cw = [max(len(ch[i]), *(len(r[i]) for r in cr)) for i in range(len(ch))]
            lines.append("  ".join(ch[i].ljust(cw[i]) for i in range(len(ch))))
            lines.append("  ".join("-"*cw[i] for i in range(len(ch))))
            lines += ["  ".join(r[i].ljust(cw[i]) for i in range(len(ch))) for r in cr]
        return "\n".join(lines)

    def _create_cursor_compare_button(self) -> None:
        """Create the Point Compare toggle beside the Matplotlib toolbar."""
        if self.toolbar_frame is None or self.cursor_compare_btn is not None:
            return
        self.cursor_compare_btn = tk.Button(
            self.toolbar_frame,
            text="Point Compare: OFF",
            command=self._toggle_cursor_compare_mode,
            bg=EATON_DARK_GREY,
            fg=EATON_WHITE,
            activebackground=EATON_BLUE,
            activeforeground=EATON_WHITE,
            relief="raised",
            bd=1,
            padx=8,
            pady=2,
            font=("Segoe UI", 9, "bold"),
            cursor="hand2",
        )
        self.cursor_compare_btn.pack(side="left", padx=(8, 2), pady=2)

    def _toggle_cursor_compare_mode(self) -> None:
        """Enable/disable locked cursor point comparison mode."""
        enabled = not bool(self.cursor_compare_enabled.get())
        self.cursor_compare_enabled.set(enabled)
        self._update_cursor_compare_button()
        if enabled:
            self._set_cursor_text(
                "Point Compare mode ON. Click the plot to lock comparison points. Press ESC to clear locked points."
            )
        else:
            # Keep existing locked comparison points visible/stored when disabling Point Compare.
            # OFF now only prevents new points from being added; ESC or Clear Cursor Points still clears them.
            if self._cursor_points:
                self._set_cursor_text(self._format_cursor_points())
            else:
                self._set_cursor_text(
                    "Point Compare mode OFF. Move over the plot for live readout; plot clicks will not lock points."
                )

    def _update_cursor_compare_button(self) -> None:
        """Refresh the Point Compare button text and colour."""
        if self.cursor_compare_btn is None:
            return
        if self.cursor_compare_enabled.get():
            self.cursor_compare_btn.configure(
                text="Point Compare: ON",
                bg=EATON_BLUE,
                relief="sunken",
            )
        else:
            self.cursor_compare_btn.configure(
                text="Point Compare: OFF",
                bg=EATON_DARK_GREY,
                relief="raised",
            )

    def _clear_cursor_points(self) -> None:
        self._cursor_points.clear()
        for artist in self._cursor_click_artists:
            try:
                artist.remove()
            except Exception:
                pass
        self._cursor_click_artists.clear()
        self._set_cursor_text("Locked cursor points cleared. Move over the plot for live readout. Enable Point Compare to lock point(s).")
        if self.canvas is not None:
            self.canvas.draw_idle()

    def use_cursor_points_as_analysis_window(self) -> None:
        if len(self._cursor_points) < 2:
            messagebox.showinfo("Analysis Window", "Please lock at least two cursor points first.")
            return
        x1 = float(self._cursor_points[0]["x"])
        x2 = float(self._cursor_points[1]["x"])
        start_x, end_x = sorted([x1, x2])
        self.analysis_xmin_var.set(self._format_cursor_number(start_x))
        self.analysis_xmax_var.set(self._format_cursor_number(end_x))
        self.update_range_preview()
        self.update_stats()
        self.mark_raw_data_stale()
        self._refresh_limit_applies_options()
        self._capture_current_plot_profile()
        messagebox.showinfo("Analysis Window", f"Analysis Window set from P1-P2: {self._format_cursor_number(start_x)} to {self._format_cursor_number(end_x)}")

    def _connect_cursor_readout(self, data: PlotData) -> None:
        if self.canvas is None or self.axes is None:
            return
        for cid_name in ("_cursor_cid", "_cursor_click_cid", "_cursor_key_cid"):
            cid = getattr(self, cid_name, None)
            if cid is not None:
                try:
                    self.canvas.mpl_disconnect(cid)
                except Exception:
                    pass
                setattr(self, cid_name, None)
        self._clear_cursor_points()
        x_values, y_map = data.x, data.y_map

        def nearest_point(xdata: float) -> Optional[dict[str, Any]]:
            x_valid = x_values.dropna()
            if x_valid.empty:
                return None
            idx = (x_valid - xdata).abs().idxmin()
            vals = {name: (series.loc[idx] if pd.notna(series.loc[idx]) else None) for name, series in y_map.items()}
            return {"index": idx, "x": float(x_values.loc[idx]), "values": vals}

        def _on_motion(event) -> None:
            valid_axes = (self.axes, self.secondary_axes) if self.secondary_axes is not None else (self.axes,)
            if self._cursor_points or event.inaxes not in valid_axes or event.xdata is None:
                return
            p = nearest_point(event.xdata)
            if p is None:
                return
            compare_state = "ON" if self.cursor_compare_enabled.get() else "OFF"
            lines = ["LIVE CURSOR READOUT", f"Point Compare: {compare_state}", f"Nearest index: {p['index']}", f"Nearest X: {self._format_cursor_number(p['x'])}", "", "Enable Point Compare to lock this point. Press ESC to clear locked points."]
            lines += [f"{k}: {self._format_cursor_number(v)}" for k, v in p["values"].items() if v is not None and pd.notna(v)]
            self._set_cursor_text("\n".join(lines))

        def _on_click(event) -> None:
            valid_axes = (self.axes, self.secondary_axes) if self.secondary_axes is not None else (self.axes,)
            if event.inaxes not in valid_axes or event.xdata is None or event.button != 1:
                return
            if not self.cursor_compare_enabled.get():
                return
            p = nearest_point(event.xdata)
            if p is None:
                return
            p["point_no"] = len(self._cursor_points) + 1
            self._cursor_points.append(p)
            marker = self.axes.axvline(p["x"], color=EATON_DARK_BLUE, linestyle="--", linewidth=1.0, alpha=0.75)
            label = self.axes.text(p["x"], 0.98, f"P{p['point_no']}", transform=self.axes.get_xaxis_transform(), rotation=90, va="top", ha="right", color=EATON_DARK_BLUE, fontsize=8)
            self._cursor_click_artists.extend([marker, label])
            self._set_cursor_text(self._format_cursor_points())
            self.canvas.draw_idle()

        def _on_key(event) -> None:
            if event.key == "escape":
                self._clear_cursor_points()

        self._cursor_cid = self.canvas.mpl_connect("motion_notify_event", _on_motion)
        self._cursor_click_cid = self.canvas.mpl_connect("button_press_event", _on_click)
        self._cursor_key_cid = self.canvas.mpl_connect("key_press_event", _on_key)
        try:
            self.canvas.get_tk_widget().focus_set()
        except Exception:
            pass
        self._set_cursor_text("Generate a plot, then move over the plot for live readout. Enable Point Compare to lock point(s). Press ESC to clear locked points.")
