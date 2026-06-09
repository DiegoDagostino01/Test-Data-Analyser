from __future__ import annotations

from typing import Any
import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
import pandas as pd


class RawDataEditorMixin:
    """Inline editing for visible Raw Data cells."""

    def __init__(self, *args, **kwargs):
        self._raw_edit_bindings_installed = False
        self._raw_edit_entry: ttk.Entry | None = None
        self._raw_edit_context: tuple[str, Any, str] | None = None
        self._raw_tree_item_to_df_index: dict[str, Any] = {}
        self._raw_edit_undo_stack: list[dict[str, Any]] = []
        super().__init__(*args, **kwargs)

    def populate_columns(self) -> None:
        self._cancel_raw_cell_edit()
        self._raw_tree_item_to_df_index.clear()
        self._raw_edit_undo_stack.clear()
        super().populate_columns()

    def update_raw_data_view(self) -> None:
        self._cancel_raw_cell_edit()
        super().update_raw_data_view()
        self._ensure_raw_editor_bindings()
        self._refresh_raw_editor_row_mapping()
        self._refresh_raw_undo_button()
        self._append_raw_editor_status_hint()

    def _ensure_raw_editor_bindings(self) -> None:
        if self._raw_edit_bindings_installed or not hasattr(self, "raw_tree"):
            return
        self.raw_tree.bind("<Double-1>", self._on_raw_tree_double_click, add="+")
        self.raw_tree.bind("<F2>", self._on_raw_tree_f2, add="+")
        self._raw_edit_bindings_installed = True

    def _refresh_raw_editor_row_mapping(self) -> None:
        self._raw_tree_item_to_df_index.clear()
        if not hasattr(self, "raw_tree") or self.df is None:
            return
        raw_df, _removed = self._selected_raw_data_frame()
        if raw_df.empty:
            return
        limit = self._raw_data_row_limit()
        display_df = raw_df if limit is None else raw_df.head(limit)
        for item_id, df_index in zip(self.raw_tree.get_children(), display_df.index):
            self._raw_tree_item_to_df_index[str(item_id)] = df_index

    def _append_raw_editor_status_hint(self) -> None:
        if not hasattr(self, "raw_status_var"):
            return
        if not getattr(self, "raw_tree", None) or not self.raw_tree.get_children():
            return
        status = self.raw_status_var.get()
        hint = " Double-click a visible cell to edit it; use Undo Edit to restore the most recent edit."
        if hint.strip() not in status:
            self.raw_status_var.set(status + hint)

    def _refresh_raw_undo_button(self) -> None:
        button = getattr(self, "raw_undo_button", None)
        if button is None:
            return
        button.configure(state="normal" if self._raw_edit_undo_stack else "disabled")

    def _on_raw_tree_f2(self, _event=None) -> str:
        if not hasattr(self, "raw_tree"):
            return "break"
        selection = self.raw_tree.selection()
        if not selection:
            return "break"
        columns = list(self.raw_tree["columns"])
        if not columns:
            return "break"
        self._begin_raw_cell_edit(str(selection[0]), "#1")
        return "break"

    def _on_raw_tree_double_click(self, event) -> str | None:
        if not hasattr(self, "raw_tree"):
            return None
        region = self.raw_tree.identify_region(event.x, event.y)
        if region != "cell":
            return None
        item_id = self.raw_tree.identify_row(event.y)
        column_id = self.raw_tree.identify_column(event.x)
        if not item_id or not column_id:
            return None
        self._begin_raw_cell_edit(str(item_id), str(column_id))
        return "break"

    def _begin_raw_cell_edit(self, item_id: str, column_id: str) -> None:
        if self.df is None or not hasattr(self, "raw_tree"):
            return
        if item_id not in self._raw_tree_item_to_df_index:
            return
        try:
            column_position = int(column_id.replace("#", "")) - 1
        except ValueError:
            return
        columns = list(self.raw_tree["columns"])
        if column_position < 0 or column_position >= len(columns):
            return
        column_name = str(columns[column_position])
        if column_name not in self.df.columns:
            return
        bbox = self.raw_tree.bbox(item_id, column_id)
        if not bbox:
            return

        self._cancel_raw_cell_edit()
        df_index = self._raw_tree_item_to_df_index[item_id]
        entry = ttk.Entry(self.raw_tree)
        entry.insert(0, self._edit_display_value(self.df.at[df_index, column_name]))
        entry.select_range(0, tk.END)
        entry.place(x=bbox[0], y=bbox[1], width=bbox[2], height=bbox[3])
        entry.focus_set()

        self._raw_edit_entry = entry
        self._raw_edit_context = (item_id, df_index, column_name)
        entry.bind("<Return>", self._commit_raw_cell_edit)
        entry.bind("<KP_Enter>", self._commit_raw_cell_edit)
        entry.bind("<Escape>", self._cancel_raw_cell_edit)
        entry.bind("<FocusOut>", self._commit_raw_cell_edit)

    def _edit_display_value(self, value: Any) -> str:
        if pd.isna(value):
            return ""
        return str(value)

    def _coerce_raw_edit_value(self, column_name: str, text: str) -> Any:
        text = text.strip()
        if text == "":
            return np.nan
        if self.df is None:
            return text
        if pd.api.types.is_numeric_dtype(self.df[column_name]):
            try:
                return float(text.replace(",", ""))
            except ValueError as exc:
                raise ValueError(f"'{column_name}' is numeric. Enter a numeric value or leave the cell blank.") from exc
        return text

    def _commit_raw_cell_edit(self, _event=None) -> str:
        if self._raw_edit_entry is None or self._raw_edit_context is None or self.df is None:
            self._cancel_raw_cell_edit()
            return "break"
        _item_id, df_index, column_name = self._raw_edit_context
        new_text = self._raw_edit_entry.get()
        try:
            new_value = self._coerce_raw_edit_value(column_name, new_text)
        except ValueError as exc:
            messagebox.showerror("Raw Data Edit", str(exc))
            self._raw_edit_entry.focus_set()
            self._raw_edit_entry.select_range(0, tk.END)
            return "break"

        old_value = self.df.at[df_index, column_name]
        if self._raw_values_equal(old_value, new_value):
            self._cancel_raw_cell_edit()
            if hasattr(self, "raw_status_var"):
                self.raw_status_var.set("Raw Data edit cancelled because the value did not change.")
            return "break"

        self._raw_edit_undo_stack.append(
            {
                "df": self.df,
                "index": df_index,
                "column": column_name,
                "old_value": old_value,
                "new_value": new_value,
            }
        )
        if pd.api.types.is_integer_dtype(self.df[column_name]) and pd.isna(new_value):
            self.df[column_name] = self.df[column_name].astype(float)
        self.df.at[df_index, column_name] = new_value
        self._cancel_raw_cell_edit()
        self._refresh_after_raw_data_edit(column_name, df_index)
        return "break"

    def _raw_values_equal(self, first: Any, second: Any) -> bool:
        if pd.isna(first) and pd.isna(second):
            return True
        try:
            return bool(first == second)
        except Exception:
            return False

    def undo_raw_data_edit(self) -> None:
        self._cancel_raw_cell_edit()
        if not self._raw_edit_undo_stack:
            messagebox.showinfo("Raw Data Undo", "There are no Raw Data edits to undo.")
            return
        edit = self._raw_edit_undo_stack.pop()
        df = edit.get("df")
        column_name = edit.get("column")
        df_index = edit.get("index")
        if not isinstance(df, pd.DataFrame) or column_name not in df.columns:
            messagebox.showwarning("Raw Data Undo", "The edited dataframe or column is no longer available.")
            self._refresh_raw_undo_button()
            return

        old_value = edit.get("old_value")
        if pd.api.types.is_integer_dtype(df[column_name]) and pd.isna(old_value):
            df[column_name] = df[column_name].astype(float)
        df.at[df_index, column_name] = old_value
        self._refresh_after_raw_data_edit(column_name, df_index, action="Undid raw data edit")

    def _cancel_raw_cell_edit(self, _event=None) -> str:
        if self._raw_edit_entry is not None:
            try:
                self._raw_edit_entry.destroy()
            except Exception:
                pass
        self._raw_edit_entry = None
        self._raw_edit_context = None
        return "break"

    def _refresh_after_raw_data_edit(
        self,
        column_name: str,
        df_index: Any,
        action: str = "Edited raw data",
    ) -> None:
        if hasattr(self, "_invalidate_column_caches"):
            self._invalidate_column_caches([column_name])

        calculated_errors: list[str] = []
        if getattr(self, "calculated_channels", None) and hasattr(self, "recalculate_calculated_channels"):
            calculated_errors = self.recalculate_calculated_channels(
                show_success=False,
                show_errors=False,
                refresh=False,
            )

        self.update_range_preview()
        self.update_stats()
        if hasattr(self, "update_comparison_stats"):
            self.update_comparison_stats()
        if hasattr(self, "refresh_runs_view"):
            self.refresh_runs_view()
        if hasattr(self, "_refresh_limit_applies_options"):
            self._refresh_limit_applies_options()
        if hasattr(self, "_capture_current_plot_profile"):
            self._capture_current_plot_profile()
        self.update_raw_data_view()
        self._refresh_raw_undo_button()

        message = f"{action} row {df_index}, column '{column_name}'. Generate Plot to refresh any existing graph."
        if calculated_errors:
            message += " Some Maths Channels could not be recalculated."
        if hasattr(self, "raw_status_var"):
            self.raw_status_var.set(message)
        if hasattr(self, "status_var"):
            self.status_var.set(message)
