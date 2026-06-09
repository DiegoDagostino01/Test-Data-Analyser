from __future__ import annotations

from typing import Any, Optional, Tuple
import json
import tkinter as tk
from tkinter import ttk, colorchooser, messagebox

import numpy as np

from .config import (
    EATON_CARD_BG,
    EATON_DARK_BLUE,
    EATON_DARK_TEXT,
    LIMIT_COLOR_PRESETS,
)
from .models import PlotData


class LimitsMixin:
    """Requirement/limit line editing, plotting, and margin calculations."""

    def _blank_limit_line(self, name: str = "Limit 1") -> dict[str, Any]:
        return {"name": name, "type": "Upper Limit", "applies_to": "All selected Y channels", "color": EATON_DARK_BLUE, "points": []}

    def _build_limit_margins_tab(self, parent: ttk.Frame) -> None:
        """Build the dedicated margin-to-limit results tab."""
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)

        top = ttk.Frame(parent)
        top.grid(row=0, column=0, sticky="ew", padx=6, pady=(4, 2))
        ttk.Button(top, text="Refresh Margin Summary", command=self.refresh_limit_summary).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="Copy Margin Summary", command=self.copy_limit_summary_to_clipboard).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="Back to Limits", command=lambda: self._select_bottom_tab_by_text("Requirements / Limits")).pack(side="left")

        summary_frame = ttk.LabelFrame(parent, text="Margin-to-Limit Summary", style="Card.TLabelframe")
        summary_frame.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        summary_frame.rowconfigure(0, weight=1)
        summary_frame.columnconfigure(0, weight=1)

        self.limit_summary_text = tk.Text(
            summary_frame,
            height=12,
            wrap="none",
            bg=EATON_CARD_BG,
            fg=EATON_DARK_TEXT,
            relief="solid",
            bd=1,
        )
        summary_y_scroll = ttk.Scrollbar(summary_frame, orient="vertical", command=self.limit_summary_text.yview)
        summary_x_scroll = ttk.Scrollbar(summary_frame, orient="horizontal", command=self.limit_summary_text.xview)
        self.limit_summary_text.configure(yscrollcommand=summary_y_scroll.set, xscrollcommand=summary_x_scroll.set)
        self.limit_summary_text.grid(row=0, column=0, sticky="nsew", padx=(4, 0), pady=(4, 0))
        summary_y_scroll.grid(row=0, column=1, sticky="ns", pady=(4, 0), padx=(0, 4))
        summary_x_scroll.grid(row=1, column=0, sticky="ew", padx=(4, 0), pady=(0, 4))

        self._set_text_widget(
            self.limit_summary_text,
            "Define at least one limit line with two or more X/Y points, then generate a plot to calculate margins.",
        )

    def _build_requirements_limits_tab(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)
        top = ttk.Frame(parent)
        top.grid(row=0, column=0, sticky="ew", padx=6, pady=(4, 2))
        ttk.Button(top, text="+ New Limit", command=self.add_limit_line).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="Duplicate", command=self.duplicate_limit_line).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="Delete Limit", command=self.delete_limit_line).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="Refresh Margins", command=self.refresh_limit_summary).pack(side="left", padx=(0, 6))
        ttk.Button(top, text="Open Margins Tab", command=lambda: self._select_bottom_tab_by_text("Limit Margins")).pack(side="left")

        body = ttk.PanedWindow(parent, orient="horizontal")
        body.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        left = ttk.Frame(body)
        right = ttk.Frame(body)
        body.add(left, weight=1)
        body.add(right, weight=2)

        list_frame = ttk.LabelFrame(left, text="Limit Lines", style="Card.TLabelframe")
        list_frame.pack(fill="both", expand=True, padx=4, pady=4)
        self.limit_tree = ttk.Treeview(list_frame, columns=("type", "points", "applies"), show="tree headings", height=8, style="Bordered.Treeview")
        self.limit_tree.heading("#0", text="Name")
        self.limit_tree.heading("type", text="Type")
        self.limit_tree.heading("points", text="Pts")
        self.limit_tree.heading("applies", text="Applies to")
        self.limit_tree.column("#0", width=150, stretch=True)
        self.limit_tree.column("type", width=90, stretch=False)
        self.limit_tree.column("points", width=40, stretch=False)
        self.limit_tree.column("applies", width=160, stretch=True)
        self._configure_treeview_tags(self.limit_tree)
        self.limit_tree.pack(fill="both", expand=True, padx=4, pady=4)
        self.limit_tree.bind("<<TreeviewSelect>>", self.on_limit_line_selected)

        details = ttk.LabelFrame(right, text="Selected Limit Definition", style="Card.TLabelframe")
        details.pack(fill="x", padx=4, pady=4)
        ttk.Label(details, text="Name:").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        ttk.Entry(details, textvariable=self.limit_name_var).grid(row=0, column=1, sticky="ew", padx=6, pady=3)
        ttk.Label(details, text="Type:").grid(row=0, column=2, sticky="w", padx=6, pady=3)
        self.limit_type_combo = ttk.Combobox(details, textvariable=self.limit_type_var, state="readonly", values=["Upper Limit", "Lower Limit", "Reference Line"])
        self.limit_type_combo.grid(row=0, column=3, sticky="ew", padx=6, pady=3)
        ttk.Label(details, text="Applies to:").grid(row=1, column=0, sticky="w", padx=6, pady=3)
        self.limit_applies_combo = ttk.Combobox(details, textvariable=self.limit_applies_var, state="readonly", values=["All selected Y channels"])
        self.limit_applies_combo.grid(row=1, column=1, sticky="ew", padx=6, pady=3)
        ttk.Label(details, text="Colour:").grid(row=1, column=2, sticky="w", padx=6, pady=3)
        colour_frame = ttk.Frame(details)
        colour_frame.grid(row=1, column=3, sticky="ew", padx=6, pady=3)
        colour_frame.columnconfigure(0, weight=1)
        self.limit_color_combo = ttk.Combobox(
            colour_frame,
            textvariable=self.limit_color_preset_var,
            state="readonly",
            values=list(LIMIT_COLOR_PRESETS.keys()) + ["Custom"],
            width=18,
        )
        self.limit_color_combo.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.limit_color_combo.bind("<<ComboboxSelected>>", self._on_limit_color_preset_selected)
        ttk.Button(colour_frame, text="Pick...", command=self.pick_limit_colour).grid(row=0, column=1, sticky="e", padx=(0, 4))
        self.limit_color_preview = tk.Label(colour_frame, text="", width=3, relief="solid", bd=1, bg=self.limit_color_var.get())
        self.limit_color_preview.grid(row=0, column=2, sticky="e")
        self.limit_color_entry = ttk.Entry(colour_frame, textvariable=self.limit_color_var, width=10)
        self.limit_color_entry.grid(row=1, column=0, columnspan=3, sticky="ew", pady=(3, 0))
        details.columnconfigure(1, weight=1)
        details.columnconfigure(3, weight=1)
        for var in (self.limit_name_var, self.limit_type_var, self.limit_applies_var, self.limit_color_var):
            var.trace_add("write", lambda *_: self._store_active_limit_from_form())

        point_controls = ttk.LabelFrame(right, text="X vs Y Limit Points — minimum 2 points required to plot/calculate margin", style="Card.TLabelframe")
        point_controls.pack(fill="x", padx=4, pady=4)
        ttk.Label(point_controls, text="X:").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        ttk.Entry(point_controls, textvariable=self.limit_x_var, width=14).grid(row=0, column=1, sticky="w", padx=6, pady=3)
        ttk.Label(point_controls, text="Y:").grid(row=0, column=2, sticky="w", padx=6, pady=3)
        ttk.Entry(point_controls, textvariable=self.limit_y_var, width=14).grid(row=0, column=3, sticky="w", padx=6, pady=3)
        ttk.Button(point_controls, text="Add Point", command=self.add_limit_point).grid(row=0, column=4, padx=6, pady=3)
        ttk.Button(point_controls, text="Update Selected Point", command=self.update_selected_limit_point).grid(row=0, column=5, padx=6, pady=3)
        ttk.Button(point_controls, text="Delete Selected Point", command=self.delete_selected_limit_point).grid(row=0, column=6, padx=6, pady=3)

        point_frame = ttk.Frame(right)
        point_frame.pack(fill="both", expand=True, padx=4, pady=4)
        self.limit_points_tree = ttk.Treeview(point_frame, columns=("x", "y"), show="headings", height=7, style="Bordered.Treeview")
        self.limit_points_tree.heading("x", text="X")
        self.limit_points_tree.heading("y", text="Y Limit")
        self.limit_points_tree.column("x", width=120, anchor="e")
        self.limit_points_tree.column("y", width=120, anchor="e")
        self._configure_treeview_tags(self.limit_points_tree)
        self.limit_points_tree.pack(side="left", fill="both", expand=True)
        point_scroll = ttk.Scrollbar(point_frame, orient="vertical", command=self.limit_points_tree.yview)
        self.limit_points_tree.configure(yscrollcommand=point_scroll.set)
        point_scroll.pack(side="right", fill="y")
        self.limit_points_tree.bind("<<TreeviewSelect>>", self.on_limit_point_selected)

        self._refresh_limit_widgets()

    def _refresh_limit_applies_options(self) -> None:
        if not hasattr(self, "limit_applies_combo"):
            return
        selected = self.selected_y_columns() if hasattr(self, "y_vars") else []
        options = ["All selected Y channels"] + selected
        self.limit_applies_combo.configure(values=options)
        if self.limit_applies_var.get() not in options:
            self.limit_applies_var.set("All selected Y channels")

    def _normalise_colour_to_preset(self, colour: str) -> str:
        colour_upper = str(colour).strip().upper()
        for name, value in LIMIT_COLOR_PRESETS.items():
            if value.upper() == colour_upper:
                return name
        return "Custom"

    def _update_limit_colour_preview(self) -> None:
        if self.limit_color_preview is None:
            return
        colour = self.limit_color_var.get().strip() or EATON_DARK_BLUE
        try:
            self.limit_color_preview.configure(bg=colour)
        except Exception:
            self.limit_color_preview.configure(bg=EATON_DARK_BLUE)
        preset = self._normalise_colour_to_preset(colour)
        if preset != "Custom" and self.limit_color_preset_var.get() != preset:
            self.limit_color_preset_var.set(preset)
        elif preset == "Custom" and self.limit_color_preset_var.get() != "Custom":
            self.limit_color_preset_var.set("Custom")

    def _on_limit_color_preset_selected(self, _event=None) -> None:
        preset = self.limit_color_preset_var.get()
        colour = LIMIT_COLOR_PRESETS.get(preset)
        if colour:
            self.limit_color_var.set(colour)
            self._store_active_limit_from_form()

    def pick_limit_colour(self) -> None:
        initial = self.limit_color_var.get().strip() or EATON_DARK_BLUE
        _rgb, colour = colorchooser.askcolor(color=initial, title="Select requirement / limit line colour")
        if colour:
            self.limit_color_var.set(colour)
            self.limit_color_preset_var.set(self._normalise_colour_to_preset(colour))
            self._store_active_limit_from_form()

    def _active_limit_line(self) -> Optional[dict[str, Any]]:
        if not self.limit_lines:
            return None
        self.active_limit_line_index = max(0, min(self.active_limit_line_index, len(self.limit_lines) - 1))
        return self.limit_lines[self.active_limit_line_index]

    def _store_active_limit_from_form(self) -> None:
        if not hasattr(self, "limit_tree") or getattr(self, "_limit_form_loading", False):
            return
        line = self._active_limit_line()
        if line is None:
            return
        line["name"] = self.limit_name_var.get().strip() or f"Limit {self.active_limit_line_index + 1}"
        line["type"] = self.limit_type_var.get() or "Upper Limit"
        line["applies_to"] = self.limit_applies_var.get() or "All selected Y channels"
        line["color"] = self.limit_color_var.get().strip() or EATON_DARK_BLUE
        self._update_limit_colour_preview()
        self._refresh_limit_tree()
        self._capture_current_plot_profile()

    def _refresh_limit_widgets(self) -> None:
        self._refresh_limit_applies_options()
        self._refresh_limit_tree()
        self._load_active_limit_into_form()
        self._refresh_limit_points_tree()

    def _refresh_limit_tree(self) -> None:
        if not hasattr(self, "limit_tree"):
            return
        children = self.limit_tree.get_children()
        if children:
            self.limit_tree.delete(*children)
        for i, line in enumerate(self.limit_lines):
            item = self.limit_tree.insert(
                "",
                "end",
                iid=str(i),
                text=line.get("name", f"Limit {i+1}"),
                values=(
                    line.get("type", "Upper Limit"),
                    len(line.get("points", [])),
                    line.get("applies_to", "All selected Y channels"),
                ),
                tags=(self._tree_row_tag(i),),
            )
            if i == self.active_limit_line_index:
                self.limit_tree.selection_set(item)

    def _load_active_limit_into_form(self) -> None:
        if not hasattr(self, "limit_name_var"):
            return
        line = self._active_limit_line()
        self._limit_form_loading = True
        try:
            if line is None:
                self.limit_name_var.set("Limit 1")
                self.limit_type_var.set("Upper Limit")
                self.limit_applies_var.set("All selected Y channels")
                self.limit_color_var.set(EATON_DARK_BLUE)
                self.limit_color_preset_var.set(self._normalise_colour_to_preset(EATON_DARK_BLUE))
            else:
                self.limit_name_var.set(line.get("name", "Limit"))
                self.limit_type_var.set(line.get("type", "Upper Limit"))
                self.limit_applies_var.set(line.get("applies_to", "All selected Y channels"))
                colour = line.get("color", EATON_DARK_BLUE)
                self.limit_color_var.set(colour)
                self.limit_color_preset_var.set(self._normalise_colour_to_preset(colour))
            self._update_limit_colour_preview()
        finally:
            self._limit_form_loading = False

    def _refresh_limit_points_tree(self) -> None:
        if not hasattr(self, "limit_points_tree"):
            return
        children = self.limit_points_tree.get_children()
        if children:
            self.limit_points_tree.delete(*children)
        line = self._active_limit_line()
        if line is None:
            return
        for i, point in enumerate(sorted(line.get("points", []), key=lambda p: float(p.get("x", 0.0)))):
            self.limit_points_tree.insert(
                "",
                "end",
                iid=str(i),
                values=(
                    f"{float(point.get('x', 0.0)):.6g}",
                    f"{float(point.get('y', 0.0)):.6g}",
                ),
                tags=(self._tree_row_tag(i),),
            )

    def add_limit_line(self) -> None:
        self.limit_lines.append(self._blank_limit_line(f"Limit {len(self.limit_lines) + 1}"))
        self.active_limit_line_index = len(self.limit_lines) - 1
        self._refresh_limit_widgets()
        self._capture_current_plot_profile()

    def duplicate_limit_line(self) -> None:
        line = self._active_limit_line()
        if line is None:
            self.add_limit_line()
            return
        duplicate = json.loads(json.dumps(line))
        duplicate["name"] = f"{line.get('name', 'Limit')} Copy"
        self.limit_lines.append(duplicate)
        self.active_limit_line_index = len(self.limit_lines) - 1
        self._refresh_limit_widgets()
        self._capture_current_plot_profile()

    def delete_limit_line(self) -> None:
        if not self.limit_lines:
            return
        confirm = self._setting("general_ui", "confirm_before_delete", True) if hasattr(self, "_setting") else True
        if confirm and not messagebox.askyesno("Delete Limit", "Delete the active limit line?"):
            return
        del self.limit_lines[self.active_limit_line_index]
        self.active_limit_line_index = max(0, min(self.active_limit_line_index, len(self.limit_lines) - 1))
        self._refresh_limit_widgets()
        self._capture_current_plot_profile()
        self.refresh_limit_summary()

    def on_limit_line_selected(self, _event=None) -> None:
        if not hasattr(self, "limit_tree"):
            return
        selection = self.limit_tree.selection()
        if selection:
            self.active_limit_line_index = int(selection[0])
            self._load_active_limit_into_form()
            self._refresh_limit_points_tree()

    def _parse_limit_point_entries(self) -> tuple[float, float]:
        return float(self.limit_x_var.get()), float(self.limit_y_var.get())

    def add_limit_point(self) -> None:
        if not self.limit_lines:
            self.add_limit_line()
        line = self._active_limit_line()
        if line is None:
            return
        try:
            x, y = self._parse_limit_point_entries()
        except Exception:
            messagebox.showerror("Limit Point", "Please enter numeric X and Y values for the limit point.")
            return
        points = line.setdefault("points", [])
        points.append({"x": x, "y": y})
        points.sort(key=lambda p: float(p.get("x", 0.0)))
        self.limit_x_var.set("")
        self.limit_y_var.set("")
        self._refresh_limit_widgets()
        self._capture_current_plot_profile()

    def update_selected_limit_point(self) -> None:
        line = self._active_limit_line()
        selection = self.limit_points_tree.selection() if hasattr(self, "limit_points_tree") else []
        if line is None or not selection:
            return
        try:
            x, y = self._parse_limit_point_entries()
        except Exception:
            messagebox.showerror("Limit Point", "Please enter numeric X and Y values for the selected limit point.")
            return
        idx = int(selection[0])
        sorted_points = sorted(line.get("points", []), key=lambda p: float(p.get("x", 0.0)))
        if 0 <= idx < len(sorted_points):
            sorted_points[idx] = {"x": x, "y": y}
            line["points"] = sorted(sorted_points, key=lambda p: float(p.get("x", 0.0)))
        self._refresh_limit_widgets()
        self._capture_current_plot_profile()

    def delete_selected_limit_point(self) -> None:
        line = self._active_limit_line()
        selection = self.limit_points_tree.selection() if hasattr(self, "limit_points_tree") else []
        if line is None or not selection:
            return
        confirm = self._setting("general_ui", "confirm_before_delete", True) if hasattr(self, "_setting") else True
        if confirm and not messagebox.askyesno("Delete Limit Point", "Delete the selected limit point?"):
            return
        idx = int(selection[0])
        sorted_points = sorted(line.get("points", []), key=lambda p: float(p.get("x", 0.0)))
        if 0 <= idx < len(sorted_points):
            del sorted_points[idx]
            line["points"] = sorted_points
        self._refresh_limit_widgets()
        self._capture_current_plot_profile()
        self.refresh_limit_summary()

    def on_limit_point_selected(self, _event=None) -> None:
        line = self._active_limit_line()
        selection = self.limit_points_tree.selection() if hasattr(self, "limit_points_tree") else []
        if line is None or not selection:
            return
        idx = int(selection[0])
        sorted_points = sorted(line.get("points", []), key=lambda p: float(p.get("x", 0.0)))
        if 0 <= idx < len(sorted_points):
            self.limit_x_var.set(f"{float(sorted_points[idx].get('x', 0.0)):.6g}")
            self.limit_y_var.set(f"{float(sorted_points[idx].get('y', 0.0)):.6g}")

    def _normalised_limit_lines(self) -> list[dict[str, Any]]:
        normalised = []
        for line in self.limit_lines:
            points = []
            for p in line.get("points", []):
                try:
                    points.append({"x": float(p.get("x")), "y": float(p.get("y"))})
                except Exception:
                    continue
            points = sorted(points, key=lambda p: p["x"])
            normalised.append({"name": line.get("name", "Limit"), "type": line.get("type", "Upper Limit"), "applies_to": line.get("applies_to", "All selected Y channels"), "color": line.get("color", EATON_DARK_BLUE), "points": points})
        return normalised

    def _limit_line_applies_to_current_selection(self, line: dict[str, Any], selected_y: Optional[set[str]] = None) -> bool:
        """Return True when a limit line should influence the current plot."""
        applies_to = str(line.get("applies_to", "All selected Y channels"))
        if applies_to == "All selected Y channels":
            return True
        if selected_y is None:
            try:
                selected_y = set(self.selected_y_columns())
            except Exception:
                selected_y = set()
        return applies_to in selected_y

    def _get_active_limit_ranges(self) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
        """Return X/Y ranges for active plotted requirement limits."""
        selected_y = set(self.selected_y_columns()) if hasattr(self, "y_vars") else set()
        x_values: list[float] = []
        y_values: list[float] = []
        for line in self._normalised_limit_lines():
            points = line.get("points", [])
            if len(points) < 2:
                continue
            if not self._limit_line_applies_to_current_selection(line, selected_y):
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

    def _plot_limit_lines(self) -> None:
        if self.axes is None:
            return
        for line in self._normalised_limit_lines():
            points = line.get("points", [])
            if len(points) < 2:
                continue
            xs = [p["x"] for p in points]
            ys = [p["y"] for p in points]
            limit_type = line.get("type", "Upper Limit")
            linestyle = "--" if limit_type != "Reference Line" else ":"
            label = f"{line.get('name', 'Limit')} [{limit_type}]"
            try:
                self.axes.plot(xs, ys, linestyle=linestyle, linewidth=1.6, color=line.get("color", EATON_DARK_BLUE), label=label)
            except ValueError:
                self.axes.plot(xs, ys, linestyle=linestyle, linewidth=1.6, color=EATON_DARK_BLUE, label=label)

    def _calculate_limit_margins(self, data: Optional[PlotData] = None) -> str:
        if self.df is None:
            return "Load data and define limits to calculate margin-to-limit."
        try:
            plot_data = data or self.prepare_plot_data()
        except Exception:
            return "Select X/Y data and generate a plot to calculate margin-to-limit."
        x_values = plot_data.x.to_numpy(dtype=float, copy=False)
        selected_y = list(plot_data.y_map.keys())
        lines = ["MARGIN-TO-LIMIT SUMMARY", "Positive margin indicates the data is inside the limit for Upper/Lower limits.", ""]
        any_result = False
        for line in self._normalised_limit_lines():
            points = line.get("points", [])
            if len(points) < 2:
                lines.append(f"{line.get('name', 'Limit')}: not evaluated — at least 2 X/Y points are required.")
                continue
            applies = line.get("applies_to", "All selected Y channels")
            channels = selected_y if applies == "All selected Y channels" else [applies]
            limit_x = np.array([p["x"] for p in points], dtype=float)
            limit_y = np.array([p["y"] for p in points], dtype=float)
            unique_x, unique_idx = np.unique(limit_x, return_index=True)
            limit_x = unique_x
            limit_y = limit_y[unique_idx]
            if len(limit_x) < 2:
                lines.append(f"{line.get('name', 'Limit')}: not evaluated — X values must include at least 2 unique points.")
                continue
            eval_mask = np.isfinite(x_values) & (x_values >= float(limit_x.min())) & (x_values <= float(limit_x.max()))
            if not eval_mask.any():
                lines.append(f"{line.get('name', 'Limit')}: not evaluated — selected X data is outside the limit-line X range.")
                continue
            interpolated_limit = np.interp(x_values[eval_mask], limit_x, limit_y)
            for channel in channels:
                if channel not in plot_data.y_map:
                    continue
                y_values = plot_data.y_map[channel].to_numpy(dtype=float, copy=False)[eval_mask]
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
                lines.append(f"{line.get('name', 'Limit')} | {channel} | {status}: {descriptor} = {float(margin[worst_idx]):.6g} at X = {float(x_eval[worst_idx]):.6g}; data = {float(y_eval[worst_idx]):.6g}, limit = {float(limit_eval[worst_idx]):.6g}")
                any_result = True
        if not any_result:
            lines.append("No limit margins were calculated. Check that limits have at least 2 points and overlap the plotted X range.")
        return "\n".join(lines)

    def refresh_limit_summary(self) -> None:
        if not hasattr(self, "limit_summary_text"):
            return
        self._refresh_limit_applies_options()
        self._set_text_widget(self.limit_summary_text, self._calculate_limit_margins())
        self._capture_current_plot_profile()

    def copy_limit_summary_to_clipboard(self) -> None:
        summary = self._calculate_limit_margins()
        self.root.clipboard_clear()
        self.root.clipboard_append(summary)
        self.root.update()
        messagebox.showinfo("Requirements / Limits", "Margin-to-limit summary copied to clipboard.")
