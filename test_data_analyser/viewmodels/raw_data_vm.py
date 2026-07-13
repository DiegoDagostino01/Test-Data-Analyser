"""Raw Data viewmodel.

Coordinates Raw Data selection/filtering, edit-value coercion, cell edits with
undo, and selected-data export through ``raw_data_service``. Returns
:class:`OperationResult` for the operations that can fail validation, so the UI
decides how to present the error. Inline editing widgets remain a UI
responsibility.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional, Sequence

import pandas as pd

from ..core.data_io import numeric_series
from ..services import dataset_service, find_replace_service, raw_data_service
from ..services.results import OperationResult, payload_dict
from .app_state import AppState
from .state_controller import AppStateController, DatasetCellUndo


class RawDataViewModel:
    def __init__(self, state: AppState) -> None:
        self.state = state
        self._controller = AppStateController(state)
        self._undo_stack: list[tuple | DatasetCellUndo] = []

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
        column_filters: Optional[dict[str, str]] = None,
        sort_column: Optional[str] = None,
        sort_ascending: bool = True,
    ) -> OperationResult:
        """Return the DataFrame and status text for the Raw Data table.

        ``column_filters`` and ``sort_column``/``sort_ascending`` are display-only:
        they are applied after blank-row removal and the analysis window, before
        the row limit, and they preserve the source dataframe index so cell edits
        still map back to the correct row.
        """
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

        if column_filters:
            frame = raw_data_service.filter_display_frame(frame, column_filters)
        if sort_column:
            frame = raw_data_service.sort_display_frame(frame, sort_column, sort_ascending)

        display = frame if limit is None else frame.head(limit)
        message = (
            f"Selected raw data: {len(display):,} / {len(frame):,} rows, {display.shape[1]:,} columns. "
            f"Removed {removed:,} row(s) with blank cells."
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
        self.state.invalidate_numeric_cache(column_name)
        self._undo_stack.append(("cell", df_index, column_name, old_value))
        self._controller.mark_dirty()
        return OperationResult.success("Cell updated.", payload=old_value)

    def undo_last_edit(self) -> OperationResult:
        """Revert the most recent cell edit or replace-all run."""
        if not self._undo_stack:
            return OperationResult.failure("Nothing to undo")
        entry = self._undo_stack.pop()
        if isinstance(entry, DatasetCellUndo):
            column_name = self.state.name_for_channel_id(entry.channel_id) or entry.channel_id
            if not self._controller.restore_dataset_cell(entry):
                self._undo_stack.append(entry)
                return OperationResult.failure("The edited cell could not be restored.")
            return OperationResult.success(f"Reverted the last edit to '{column_name}'.")
        if entry[0] == "snapshot":
            self._controller.restore_dataset_snapshot(entry[1])
            return OperationResult.success("Reverted the last replace.")
        _tag, df_index, column_name, old_value = entry
        df = self.state.df
        if df is None or column_name not in df.columns:
            return OperationResult.failure("The edited dataframe or column is no longer available.")
        if pd.api.types.is_integer_dtype(df[column_name]) and pd.isna(old_value):
            df[column_name] = df[column_name].astype(float)
        df.at[df_index, column_name] = old_value
        self.state.invalidate_numeric_cache(column_name)
        return OperationResult.success(f"Reverted the last edit to '{column_name}'.", payload=(df_index, column_name))

    # ------------------------------------------------------------------
    # Find & replace
    # ------------------------------------------------------------------
    def find(
        self,
        query: str,
        *,
        regex: bool = False,
        case_sensitive: bool = False,
        columns: Optional[Sequence[str]] = None,
        search_full_dataset: bool = True,
        display_frame: Optional[pd.DataFrame] = None,
    ) -> OperationResult:
        """Find matches in the full dataset or the supplied displayed frame.

        Payload is the list of ``find_replace_service.Match`` (row label, column,
        matched text). Read-only; no undo.
        """
        frame = self.state.df if (search_full_dataset or display_frame is None) else display_frame
        try:
            matches = find_replace_service.find_matches(
                frame, query, regex=regex, case_sensitive=case_sensitive, columns=columns
            )
        except re.error as exc:
            return OperationResult.failure(f"Invalid regular expression: {exc}")
        return OperationResult.success(f"{len(matches)} match(es).", payload=matches)

    def replace_all(
        self,
        query: str,
        replacement: str,
        *,
        regex: bool = False,
        case_sensitive: bool = False,
        columns: Optional[Sequence[str]] = None,
        search_full_dataset: bool = True,
        display_frame: Optional[pd.DataFrame] = None,
    ) -> OperationResult:
        """Replace every match in one undo step (snapshot of the dataset).

        Each write goes through ``dataset_service.set_cell`` so values are coerced
        to the target column type and non-numeric text is kept (with a warning)
        rather than zeroed.
        """
        if not query:
            return OperationResult.failure("Enter text to find.")
        frame = self.state.df if (search_full_dataset or display_frame is None) else display_frame
        if frame is None:
            return OperationResult.failure("There is no data to search.")
        try:
            matches = find_replace_service.find_matches(
                frame, query, regex=regex, case_sensitive=case_sensitive, columns=columns
            )
        except re.error as exc:
            return OperationResult.failure(f"Invalid regular expression: {exc}")
        if not matches:
            return OperationResult.success("No matches found.", payload={"replaced": 0})

        snapshot = self._controller.capture_dataset_snapshot("replace all")

        def _write(row: Any, column: str, new_text: str) -> OperationResult:
            channel_id = self.state.channel_id_for_name(column)
            if channel_id is None:
                return OperationResult.failure("Column is no longer available.")
            result = dataset_service.set_cell(
                self.state.df, self.state.channel_registry, channel_id, int(row), new_text
            )
            if result.ok:
                self._controller.apply_dataframe_payload(payload_dict(result))
            return result

        summary = find_replace_service.apply_replacements(
            frame, matches, replacement, query=query, regex=regex, case_sensitive=case_sensitive, write=_write
        )
        if summary.replaced == 0:
            return OperationResult.success("No occurrences replaced.", payload={"replaced": 0})
        self._controller.mark_dirty()
        self._undo_stack.append(("snapshot", snapshot))
        return OperationResult.success(
            f"Replaced {summary.replaced} occurrence(s).",
            warnings=summary.warnings,
            payload={"replaced": summary.replaced},
        )

    def replace_match(
        self,
        row: Any,
        column: str,
        query: str,
        replacement: str,
        *,
        regex: bool = False,
        case_sensitive: bool = False,
    ) -> OperationResult:
        """Replace ``query`` in a single cell as one undo step."""
        df = self.state.df
        if df is None or column not in df.columns:
            return OperationResult.failure("The cell is no longer available.")
        channel_id = self.state.channel_id_for_name(column)
        if channel_id is None:
            return OperationResult.failure("The column is no longer available.")
        try:
            current = df.at[int(row), column]
        except (KeyError, ValueError):
            return OperationResult.failure("The cell is no longer available.")
        text = "" if pd.isna(current) else str(current)
        try:
            new_text = find_replace_service.replace_in_text(
                text, query, replacement, regex=regex, case_sensitive=case_sensitive
            )
        except re.error as exc:
            return OperationResult.failure(f"Invalid regular expression: {exc}")
        if new_text == text:
            return OperationResult.success("No change.", payload={"replaced": 0})
        spec = self.state.channel_registry.spec_for_id(channel_id)
        if spec is None:
            return OperationResult.failure("The column is no longer available.")
        undo = DatasetCellUndo(
            description="replace",
            channel_id=channel_id,
            row_index=int(row),
            old_value=current,
            old_dtype=df[column].dtype,
            old_data_type=spec.data_type,
            is_dirty=self.state.is_dirty,
        )
        result = dataset_service.set_cell(
            self.state.df, self.state.channel_registry, channel_id, int(row), new_text
        )
        if not result.ok:
            return result
        self._controller.apply_dataframe_payload(payload_dict(result))
        self._controller.mark_dirty()
        self._undo_stack.append(undo)
        return OperationResult.success("Replaced 1 occurrence.", warnings=result.warnings, payload={"replaced": 1})

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
