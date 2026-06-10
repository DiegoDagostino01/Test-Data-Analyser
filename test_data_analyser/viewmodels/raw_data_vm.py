"""Raw Data viewmodel.

Coordinates Raw Data selection/filtering, edit-value coercion, cell edits with
undo, and selected-data export through ``raw_data_service``. Returns
:class:`OperationResult` for the operations that can fail validation, so the UI
decides how to present the error. Inline editing widgets remain a UI
responsibility.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import pandas as pd

from ..core.data_io import numeric_series
from ..services import raw_data_service
from ..services.results import OperationResult
from .app_state import AppState


class RawDataViewModel:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self._undo_stack: list[tuple[Any, str, Any]] = []

    def _numeric(self, column: str) -> pd.Series:
        if self.state.df is None or column not in self.state.df.columns:
            return pd.Series(dtype=float)
        return numeric_series(self.state.df[column])

    def parse_row_limit(self, text: str) -> OperationResult:
        """Parse the row-limit entry. Payload is the int limit or ``None`` (all)."""
        try:
            return OperationResult.success(payload=raw_data_service.parse_row_limit(text))
        except ValueError:
            return OperationResult.failure("Rows to display must be a positive whole number, or 'All'.")

    @staticmethod
    def empty_frame() -> pd.DataFrame:
        return pd.DataFrame()

    def select_frame(
        self,
        x_col: str,
        selected_y: list[str],
        *,
        apply_window: bool,
        xmin: Optional[float],
        xmax: Optional[float],
        drop_blank: bool,
    ) -> tuple[pd.DataFrame, int]:
        """Return ``(selected_frame, blank_rows_removed)`` for the Raw Data view."""
        return raw_data_service.select_raw_data_frame(
            self.state.df,
            x_col,
            selected_y,
            apply_window=apply_window,
            xmin=xmin,
            xmax=xmax,
            drop_blank=drop_blank,
            get_numeric=self._numeric,
        )

    def display_frame(
        self,
        x_col: str,
        selected_y: list[str],
        *,
        row_limit_text: str,
        apply_window: bool,
        xmin: Optional[float],
        xmax: Optional[float],
        drop_blank: bool,
    ) -> OperationResult:
        """Return the DataFrame and status text for the Raw Data table."""
        limit_result = self.parse_row_limit(row_limit_text)
        limit: Optional[int] = None
        warnings: list[str] = []
        row_limit_valid = limit_result.ok
        if limit_result.ok:
            payload = limit_result.payload
            limit = payload if isinstance(payload, int) else None
        else:
            warnings.append(limit_result.message)

        frame, removed = self.select_frame(
            x_col,
            selected_y,
            apply_window=apply_window,
            xmin=xmin,
            xmax=xmax,
            drop_blank=drop_blank,
        )
        if frame.empty:
            return OperationResult.failure(
                "No complete selected X/Y rows to display.",
                payload={"frame": self.empty_frame(), "row_limit_valid": row_limit_valid},
            )

        display = frame if limit is None else frame.head(limit)
        message = (
            f"Selected raw data: {len(display):,} / {len(frame):,} rows, {display.shape[1]:,} columns. "
            f"Removed {removed:,} row(s) with blank cells. Double-click a cell to edit it."
        )
        return OperationResult.success(
            message,
            payload={"frame": display, "row_limit_valid": row_limit_valid},
            warnings=warnings,
        )

    def coerce_edit_value(self, column_name: str, text: str) -> OperationResult:
        """Coerce an edited cell value. Payload is the coerced value on success."""
        try:
            value = raw_data_service.coerce_raw_edit_value(self.state.df, column_name, text)
        except ValueError as exc:
            return OperationResult.failure(str(exc))
        return OperationResult.success(payload=value)

    # ------------------------------------------------------------------
    # Inline editing with undo
    # ------------------------------------------------------------------
    @property
    def can_undo(self) -> bool:
        return bool(self._undo_stack)

    def apply_edit(self, df_index: Any, column_name: str, value: Any) -> OperationResult:
        """Write a coerced cell value back to the source dataframe.

        Records the previous value so the edit can be undone. Payload is the
        old value on success.
        """
        df = self.state.df
        if df is None or column_name not in df.columns:
            return OperationResult.failure("The edited column is no longer available.")
        try:
            old_value = df.at[df_index, column_name]
        except KeyError:
            return OperationResult.failure("The edited row is no longer available.")
        if self._values_equal(old_value, value):
            return OperationResult.failure("The value did not change.")
        if pd.api.types.is_integer_dtype(df[column_name]) and pd.isna(value):
            df[column_name] = df[column_name].astype(float)
        df.at[df_index, column_name] = value
        self._undo_stack.append((df_index, column_name, old_value))
        return OperationResult.success("Cell updated.", payload=old_value)

    def undo_last_edit(self) -> OperationResult:
        """Revert the most recent cell edit. Payload is ``(index, column)``."""
        if not self._undo_stack:
            return OperationResult.failure("There are no Raw Data edits to undo.")
        df_index, column_name, old_value = self._undo_stack.pop()
        df = self.state.df
        if df is None or column_name not in df.columns:
            return OperationResult.failure("The edited dataframe or column is no longer available.")
        if pd.api.types.is_integer_dtype(df[column_name]) and pd.isna(old_value):
            df[column_name] = df[column_name].astype(float)
        df.at[df_index, column_name] = old_value
        return OperationResult.success(f"Reverted the last edit to '{column_name}'.", payload=(df_index, column_name))

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------
    def export_selected_frame(
        self,
        path: str | Path,
        x_col: str,
        selected_y: list[str],
        *,
        apply_window: bool,
        xmin: Optional[float],
        xmax: Optional[float],
        drop_blank: bool,
    ) -> OperationResult:
        """Export the current selected/cleaned frame to ``.csv`` or ``.xlsx``."""
        frame, removed = self.select_frame(
            x_col,
            selected_y,
            apply_window=apply_window,
            xmin=xmin,
            xmax=xmax,
            drop_blank=drop_blank,
        )
        if frame.empty:
            return OperationResult.failure("No selected data is available to export.")
        target = Path(path)
        try:
            if target.suffix.lower() == ".csv":
                frame.to_csv(target, index=False)
            else:
                frame.to_excel(target, index=False, engine="openpyxl")
        except Exception as exc:
            return OperationResult.failure(f"Could not export the selected data: {exc}")
        return OperationResult.success(
            f"Exported {len(frame):,} rows and {frame.shape[1]:,} columns.\n"
            f"Removed blank rows before export: {removed:,}\n\n{target}",
            payload=str(target),
        )

    @staticmethod
    def _values_equal(first: Any, second: Any) -> bool:
        if pd.isna(first) and pd.isna(second):
            return True
        try:
            return bool(first == second)
        except Exception:
            return False
