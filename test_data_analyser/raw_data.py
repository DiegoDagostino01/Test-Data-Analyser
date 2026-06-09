from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
from tkinter import filedialog, messagebox

import numpy as np
import pandas as pd

from .utils import _matching_x_column_for_y


class RawDataMixin:
    """Raw Data tab filtering, display, and selected-data export behaviour."""

    def mark_raw_data_stale(self) -> None:
        if hasattr(self, "raw_status_var"):
            self.raw_status_var.set("Raw data selection changed. Generate Plot or click Refresh to update the Raw Data tab.")

    def _raw_data_row_limit(self) -> Optional[int]:
        raw = self.raw_data_row_limit_var.get().strip()
        if not raw or raw.lower() in {"all", "none", "no limit", "unlimited", "*"}:
            return None
        try:
            return max(1, int(raw.replace(",", "")))
        except ValueError:
            messagebox.showwarning("Raw Data", "Rows to display must be a positive whole number, or 'All'.")
            self.raw_data_row_limit_var.set("All")
            return None

    def _selected_raw_data_frame(self) -> tuple[pd.DataFrame, int]:
        if self.df is None:
            return pd.DataFrame(), 0

        cols: list[str] = []
        x_col = self.x_col_var.get()
        if x_col and x_col in self.df.columns:
            cols.append(x_col)
        for col in self.selected_y_columns():
            if x_col:
                paired_x_col = _matching_x_column_for_y(x_col, col, self.df.columns)
                if paired_x_col in self.df.columns and paired_x_col not in cols:
                    cols.append(paired_x_col)
            if col in self.df.columns and col not in cols:
                cols.append(col)
        if not cols:
            return pd.DataFrame(), 0

        raw_df = self.df.loc[:, cols].copy()
        if self.raw_data_apply_window_var.get() and x_col and x_col in self.df.columns:
            xmin = self.parse_limit(self.analysis_xmin_var.get()) if hasattr(self, "analysis_xmin_var") else None
            xmax = self.parse_limit(self.analysis_xmax_var.get()) if hasattr(self, "analysis_xmax_var") else None
            if xmin is not None or xmax is not None:
                x = self._get_numeric(x_col)
                mask = pd.Series(True, index=self.df.index)
                if xmin is not None:
                    mask &= x >= xmin
                if xmax is not None:
                    mask &= x <= xmax
                raw_df = raw_df.loc[mask]

        removed = 0
        if self.raw_data_drop_blank_rows_var.get() and not raw_df.empty:
            before = len(raw_df)
            raw_df = raw_df.replace(r"^\s*$", np.nan, regex=True).dropna(axis=0, how="any")
            removed = before - len(raw_df)
        return raw_df, removed

    def update_raw_data_view(self) -> None:
        if not hasattr(self, "raw_tree"):
            return

        children = self.raw_tree.get_children()
        if children:
            self.raw_tree.delete(*children)
        self.raw_tree["columns"] = ()

        raw_df, removed = self._selected_raw_data_frame()
        if raw_df.empty:
            if hasattr(self, "raw_status_var"):
                self.raw_status_var.set("No complete selected X/Y rows to display.")
            return

        limit = self._raw_data_row_limit()
        display_df = raw_df if limit is None else raw_df.head(limit)
        columns = [str(c) for c in display_df.columns]
        self.raw_tree["columns"] = columns
        for col in columns:
            self.raw_tree.heading(col, text=col)
            self.raw_tree.column(col, width=max(90, min(260, len(col) * 9)), anchor="w", stretch=False)

        def _format_cell(value: Any) -> str:
            if pd.isna(value):
                return ""
            if isinstance(value, (float, np.floating)):
                return f"{float(value):.6g}"
            return str(value)

        insert = self.raw_tree.insert
        for index, row in enumerate(display_df.itertuples(index=False, name=None)):
            insert(
                "",
                "end",
                values=[_format_cell(value) for value in row],
                tags=(self._tree_row_tag(index),),
            )
        if hasattr(self, "raw_status_var"):
            self.raw_status_var.set(f"Selected raw data: {len(display_df):,} / {len(raw_df):,} rows, {len(columns):,} columns. Removed {removed:,} row(s) with blank cells.")

    def export_selected_data(self) -> None:
        raw_df, removed = self._selected_raw_data_frame()
        if raw_df.empty:
            messagebox.showwarning("Export Selected Data", "No selected data is available to export.")
            return

        filename = filedialog.asksaveasfilename(title="Export selected/cleaned data", defaultextension=".xlsx", filetypes=[("Excel workbook", "*.xlsx"), ("CSV", "*.csv"), ("All files", "*.*")])
        if not filename:
            return

        path = Path(filename)
        if path.suffix.lower() == ".csv":
            raw_df.to_csv(path, index=False)
        else:
            raw_df.to_excel(path, index=False, engine="openpyxl")
        messagebox.showinfo("Export Selected Data", f"Exported {len(raw_df):,} rows and {len(raw_df.columns):,} columns.\nRemoved blank rows before export: {removed:,}\n\n{path}")
