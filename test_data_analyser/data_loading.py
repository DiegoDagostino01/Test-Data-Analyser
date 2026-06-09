from __future__ import annotations

from pathlib import Path
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

import pandas as pd

from .config import COLUMN_GROUP_ORDER, DOMAIN_CONFIG
from .data_io import get_excel_sheets, load_data, numeric_series
from .utils import (
    natural_sort_key,
    _is_temperature_channel_name,
    infer_column_by_keywords,
)


class DataLoadingMixin:
    """File loading, column population/classification, Y-channel selection, and
    column-derived axis labels.

    Relies on shared state created in ``gui_base.py`` (``self.df``,
    ``self.filepath``, the dataframe caches such as ``self._numeric_cache`` and
    ``self._column_group_cache``, the Tk variables/widgets built in
    ``_build_left_controls``) and reaches analysis/raw-data/profile/label
    behaviour through ``self`` via the method-resolution order.
    """

    # ------------------------------------------------------------------
    # File loading
    # ------------------------------------------------------------------
    def select_file(self) -> None:
        filename = filedialog.askopenfilename(
            title="Select test data file",
            filetypes=[("Data files", "*.csv *.xlsx *.xls"),
                       ("CSV", "*.csv"), ("Excel", "*.xlsx *.xls"),
                       ("All files", "*.*")])
        if not filename:
            return
        self.filepath = Path(filename)
        self.file_label.configure(text=str(self.filepath))
        try:
            sheets = get_excel_sheets(self.filepath)
            if sheets:
                self.sheet_frame.pack(fill="x", pady=(4, 0))
                self.sheet_combo.configure(values=sheets)
                self.sheet_var.set(sheets[0])
                self.load_selected_sheet()
            else:
                self.sheet_frame.pack_forget()
                self.df = load_data(self.filepath, settings_manager=getattr(self, "settings_manager", None))
                self.populate_columns()
        except Exception as exc:
            messagebox.showerror("Load error", str(exc))

    def load_selected_sheet(self) -> None:
        if self.filepath is None:
            return
        try:
            self.df = load_data(self.filepath, self.sheet_var.get() or None, settings_manager=getattr(self, "settings_manager", None))
            self.populate_columns()
        except Exception as exc:
            messagebox.showerror("Load error", str(exc))

    # ------------------------------------------------------------------
    # Dataframe caches
    # ------------------------------------------------------------------
    def _reset_data_caches(self) -> None:
        """Clear all dataframe-dependent caches after loading a new file/sheet."""
        self._numeric_cache.clear()
        self._column_group_cache.clear()
        self._likely_numeric_cache.clear()
        if self.df is None:
            self._column_lower_cache = {}
            self._sorted_columns_cache = []
            return
        columns = [str(col) for col in self.df.columns]
        self._column_lower_cache = {col: col.lower() for col in columns}
        self._sorted_columns_cache = sorted(columns, key=natural_sort_key)

    def _invalidate_column_caches(self, columns: object) -> None:
        """Drop cached numeric/classification data for specific columns only.

        Used when a small number of columns change (e.g. a calculated channel is
        added or recalculated) so the expensive numeric conversions cached for
        every other column are preserved.
        """
        for col in columns:
            self._numeric_cache.pop(col, None)
            self._column_group_cache.pop(col, None)
            self._likely_numeric_cache.pop(col, None)

    def refresh_columns_incrementally(self, select_columns: object = None) -> None:
        """Refresh column widgets after a small column change without reloading.

        Unlike :meth:`populate_columns`, this preserves the numeric cache, the
        current X-axis choice, and existing Y-axis selections, so adding a
        calculated channel does not reconvert every column on large datasets.
        """
        if self.df is None:
            return
        columns = [str(col) for col in self.df.columns]
        valid = set(columns)
        self._column_lower_cache = {col: col.lower() for col in columns}
        self._sorted_columns_cache = sorted(columns, key=natural_sort_key)
        self.x_combo.configure(values=columns)
        if self.x_col_var.get() not in valid and columns:
            self.x_col_var.set(columns[0])
        for col in columns:
            if col not in self.y_vars:
                self.y_vars[col] = tk.BooleanVar(value=False)
            if col not in self.secondary_y_vars:
                self.secondary_y_vars[col] = tk.BooleanVar(value=False)
        for col in list(self.y_vars):
            if col not in valid:
                del self.y_vars[col]
        for col in list(self.secondary_y_vars):
            if col not in valid:
                del self.secondary_y_vars[col]
        for cache in (self._numeric_cache, self._column_group_cache, self._likely_numeric_cache):
            for col in [c for c in cache if c not in valid]:
                cache.pop(col, None)
        current_x = self.x_col_var.get()
        for col in (select_columns or []):
            if col in self.y_vars and col != current_x:
                self.y_vars[col].set(True)
        self._rebuild_y_checkboxes()

    def _is_likely_numeric_column(self, column: str, sample_size: int = 200) -> bool:
        """Fast numeric check used by UI classification without converting full columns."""
        if self.df is None or column not in self.df.columns:
            return False
        if column in self._likely_numeric_cache:
            return self._likely_numeric_cache[column]
        series = self.df[column]
        if pd.api.types.is_numeric_dtype(series):
            result = series.notna().any()
        else:
            sample = series.dropna().head(sample_size)
            if sample.empty:
                result = False
            else:
                converted = numeric_series(sample)
                result = bool(converted.notna().mean() >= 0.70)
        self._likely_numeric_cache[column] = result
        return result

    # ------------------------------------------------------------------
    # Column population
    # ------------------------------------------------------------------
    def populate_columns(self) -> None:
        if self.df is None:
            return
        self._reset_data_caches()
        columns = [str(col) for col in self.df.columns]
        self.x_combo.configure(values=columns)
        suggested_x = (infer_column_by_keywords(columns, DOMAIN_CONFIG["Time"]) or (columns[0] if columns else ""))
        self.x_col_var.set(suggested_x)
        self.y_vars = {}
        self.secondary_y_vars = {}
        preselected = 0
        for col in columns:
            checked = (col != suggested_x and self._is_likely_numeric_column(col) and preselected < 4)
            if checked:
                preselected += 1
            self.y_vars[col] = tk.BooleanVar(value=checked)
            self.secondary_y_vars[col] = tk.BooleanVar(value=False)
        if hasattr(self, "channel_search_var"):
            self.channel_search_var.set("")
        self._rebuild_y_checkboxes()
        self.auto_fit_var.set(True)
        self.toggle_axis_entries()
        self.auto_labels_from_selection()
        self.update_range_preview()
        self.update_stats()
        self.mark_raw_data_stale()

    # ------------------------------------------------------------------
    # Y-channel checkbox rebuild
    # ------------------------------------------------------------------
    def _schedule_y_checkbox_rebuild(self, delay_ms: int = 120) -> None:
        """Debounce Y-axis checkbox rebuilds while typing in the channel search box."""
        if self._y_rebuild_after_id is not None:
            try:
                self.root.after_cancel(self._y_rebuild_after_id)
            except Exception:
                pass
        self._y_rebuild_after_id = self.root.after(delay_ms, self._run_scheduled_y_checkbox_rebuild)

    def _run_scheduled_y_checkbox_rebuild(self) -> None:
        self._y_rebuild_after_id = None
        self._rebuild_y_checkboxes()

    def _column_group(self, column: str) -> str:
        cached = self._column_group_cache.get(column)
        if cached is not None:
            return cached
        name = self._column_lower_cache.get(column, str(column).lower())
        if _is_temperature_channel_name(name):
            group = "Temperature"
        else:
            group = "Non-numeric / Metadata"
            for candidate_group, keywords in DOMAIN_CONFIG.items():
                if any(k in name for k in keywords):
                    group = candidate_group
                    break
            if group == "Non-numeric / Metadata" and self._is_likely_numeric_column(column):
                group = "Other Numeric"
        self._column_group_cache[column] = group
        return group

    def _matching_y_columns(self) -> list[str]:
        if self.df is None:
            return []
        query = self.channel_search_var.get().strip().lower() if hasattr(self, "channel_search_var") else ""
        x_col = self.x_col_var.get()
        candidates = self._sorted_columns_cache or sorted([str(col) for col in self.df.columns], key=natural_sort_key)
        if not query:
            return [col for col in candidates if col != x_col]
        lower_cache = self._column_lower_cache
        return [col for col in candidates if col != x_col and query in lower_cache.get(col, str(col).lower())]

    def _rebuild_y_checkboxes(self) -> None:
        if not hasattr(self, "y_check_inner"):
            return
        for child in self.y_check_inner.winfo_children():
            child.destroy()
        if self.df is None:
            self._visible_y_columns = []
            return
        columns = self._matching_y_columns()
        self._visible_y_columns = columns
        if not columns:
            ttk.Label(self.y_check_inner, text="No matching channels.").pack(anchor="w", padx=6, pady=4)
            return
        def _ensure_axis_vars(column: str) -> None:
            if column not in self.y_vars:
                self.y_vars[column] = tk.BooleanVar(value=False)
            if column not in self.secondary_y_vars:
                self.secondary_y_vars[column] = tk.BooleanVar(value=False)
        def _add_channel_row(parent: tk.Widget, column: str) -> None:
            _ensure_axis_vars(column)
            row = ttk.Frame(parent)
            row.pack(anchor="w", fill="x", padx=4, pady=1)
            ttk.Checkbutton(row, text=column, variable=self.y_vars[column], command=self.on_axis_selection_changed).pack(side="left", fill="x", expand=True)
            ttk.Checkbutton(row, text="Right Y", variable=self.secondary_y_vars[column], command=lambda c=column: self._on_secondary_axis_toggle(c)).pack(side="right", padx=(6, 2))
        header = ttk.Frame(self.y_check_inner)
        header.pack(fill="x", padx=6, pady=(4, 2))
        ttk.Label(header, text="Signal", font=("Segoe UI", 8, "bold")).pack(side="left")
        ttk.Label(header, text="Secondary axis", font=("Segoe UI", 8, "bold")).pack(side="right")
        grouped = self.group_channels_var.get() if hasattr(self, "group_channels_var") else True
        if not grouped:
            for col in columns:
                _add_channel_row(self.y_check_inner, col)
            return
        group_order = COLUMN_GROUP_ORDER
        grouped_cols: dict[str, list[str]] = {group: [] for group in group_order}
        for col in columns:
            grouped_cols.setdefault(self._column_group(col), []).append(col)
        for group in group_order:
            cols = grouped_cols.get(group, [])
            if not cols:
                continue
            frame = ttk.LabelFrame(self.y_check_inner, text=f"{group} ({len(cols)})")
            frame.pack(fill="x", padx=4, pady=3)
            for col in cols:
                _add_channel_row(frame, col)

    # ------------------------------------------------------------------
    # Y-column helpers
    # ------------------------------------------------------------------
    def select_all_y_columns(self) -> None:
        target_cols = self._visible_y_columns or list(self.y_vars.keys())
        for col in target_cols:
            if col != self.x_col_var.get() and col in self.y_vars:
                self.y_vars[col].set(True)
        self.on_axis_selection_changed()

    def clear_y_selection(self) -> None:
        target_cols = self._visible_y_columns or list(self.y_vars.keys())
        for col in target_cols:
            if col in self.y_vars:
                self.y_vars[col].set(False)
            if col in self.secondary_y_vars:
                self.secondary_y_vars[col].set(False)
        self.on_axis_selection_changed()

    def selected_y_columns(self) -> list[str]:
        return [col for col, var in self.y_vars.items() if var.get() and col != self.x_col_var.get()]

    def selected_secondary_y_columns(self) -> list[str]:
        return [col for col, var in self.secondary_y_vars.items()
                if var.get() and self.y_vars.get(col) is not None
                and self.y_vars[col].get() and col != self.x_col_var.get()]

    def _on_secondary_axis_toggle(self, column: str) -> None:
        if self.secondary_y_vars.get(column) is not None and self.secondary_y_vars[column].get():
            if self.y_vars.get(column) is not None:
                self.y_vars[column].set(True)
        self.on_axis_selection_changed()

    # ------------------------------------------------------------------
    # Debounced axis-selection handler
    # ------------------------------------------------------------------
    def on_axis_selection_changed(self) -> None:
        for col, secondary_var in self.secondary_y_vars.items():
            y_var = self.y_vars.get(col)
            if secondary_var.get() and (y_var is None or not y_var.get() or col == self.x_col_var.get()):
                secondary_var.set(False)
        self.auto_fit_var.set(True)
        self.toggle_axis_entries()
        self.auto_labels_from_selection()
        self.update_range_preview()
        self.update_stats()
        self.mark_raw_data_stale()
        self._capture_current_plot_profile()
        if self._debounce_id is not None:
            self.root.after_cancel(self._debounce_id)
        self._debounce_id = self.root.after(250, self._deferred_axis_update)

    def _deferred_axis_update(self) -> None:
        self._debounce_id = None
        self.update_range_preview()
        self.update_stats()

    # ------------------------------------------------------------------
    # Column-derived axis labels
    # ------------------------------------------------------------------
    def _unit_from_column_name(self, column: str) -> str:
        # Return the engineering unit from a column label when it is present.
        # Examples: "Delivery Pressure (psi)" -> "psi", "Motor Current [A]" -> "A".
        text = str(column).strip()
        matches = re.findall(r"\(([^()]+)\)|\[([^\[\]]+)\]", text)
        if matches:
            last = matches[-1]
            unit = (last[0] or last[1]).strip()
            if unit:
                return unit

        tokens = [
            "psig", "psid", "psi", "bar", "kpa", "inhg", "hg",
            "pph", "gph", "gpm", "lpm", "slpm",
            "amps", "amp", "ma", "a",
            "vdc", "vac", "volt", "volts", "v",
            "rpm", "rps",
            "deg c", "degc", "°c", "c",
            "mins", "min", "seconds", "second", "sec", "s",
        ]
        lowered = text.lower().replace("_", " ").replace("-", " ")
        for token in tokens:
            if re.search(rf"(?:^|\s){re.escape(token)}$", lowered):
                return token.upper() if len(token) <= 4 else token
        return ""

    def _axis_label_from_columns(self, columns: list[str], fallback: str) -> str:
        # Build a concise axis label using signal type and engineering units.
        if not columns:
            return fallback
        if len(columns) == 1:
            unit = self._unit_from_column_name(columns[0])
            if unit and unit not in columns[0]:
                return f"{columns[0]} ({unit})"
            return columns[0]

        units = [self._unit_from_column_name(col) for col in columns]
        unique_units = sorted({unit for unit in units if unit})
        groups = [self._column_group(col) for col in columns]
        unique_groups = sorted({group for group in groups if group and group != "Other Numeric"})

        if len(unique_groups) == 1 and len(unique_units) == 1:
            return f"{unique_groups[0]} ({unique_units[0]})"
        if len(unique_units) == 1:
            return f"Selected Signals ({unique_units[0]})"
        if len(unique_units) > 1:
            return "Selected Signals (mixed units)"
        if len(unique_groups) == 1:
            return unique_groups[0]
        return fallback
