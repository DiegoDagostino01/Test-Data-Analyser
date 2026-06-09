"""Runs / comparison viewmodel.

Coordinates the multi-run comparison state through ``run_comparison_service``:
run CRUD, enabled-run filtering, common-X range, comparison statistics, run-entry
creation, comparison-item preparation, and run metadata serialisation. Returns
:class:`OperationResult` for the operations that can fail. Holds no UI objects
and opens no dialogs; the panel supplies file paths/sheets and draws the plot.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

import pandas as pd

from ..core.config import EATON_PLOT_COLORS
from ..core.data_io import get_excel_sheets, load_data
from ..services import run_comparison_service
from ..services.results import OperationResult
from ..core.utils import _matching_x_column_for_y
from .app_state import AppState


class RunsComparisonViewModel:
    def __init__(self, state: AppState) -> None:
        self.state = state

    def enabled_runs(self) -> list[dict[str, Any]]:
        return run_comparison_service.enabled_runs(self.state.runs)

    def next_run_colour(self) -> str:
        return EATON_PLOT_COLORS[len(self.state.runs) % len(EATON_PLOT_COLORS)]

    def make_run_entry(
        self,
        name: str,
        filepath: str | Path,
        sheet_name: str,
        df: pd.DataFrame,
        enabled: bool = True,
        colour: Optional[str] = None,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "filepath": str(filepath),
            "sheet_name": sheet_name or "",
            "df": df,
            "enabled": bool(enabled),
            "colour": colour or self.next_run_colour(),
        }

    # ------------------------------------------------------------------
    # Run loading / CRUD
    # ------------------------------------------------------------------
    def get_sheets(self, path: str | Path) -> list[str]:
        """Return the Excel sheet names for ``path`` (empty for CSV/invalid)."""
        try:
            return get_excel_sheets(path)
        except Exception:
            return []

    def add_run(self, path: str | Path, sheet_name: Optional[str] = None) -> OperationResult:
        """Load ``path`` and append it as a new run. Payload is the new index."""
        file_path = Path(path)
        if not file_path.exists():
            return OperationResult.failure(f"File not found: {file_path}")
        try:
            df = load_data(file_path, sheet_name or None, settings_manager=self.state.settings_manager)
        except Exception as exc:
            return OperationResult.failure(f"Could not load the selected run:\n\n{exc}")
        run = self.make_run_entry(
            name=f"Run {len(self.state.runs) + 1}",
            filepath=file_path,
            sheet_name=sheet_name or "",
            df=df,
            enabled=True,
        )
        self.state.runs.append(run)
        index = len(self.state.runs) - 1
        if self.state.active_run_index < 0:
            self.state.active_run_index = index
        return OperationResult.success(f"Added {run['name']}.", payload=index)

    def remove_run(self, index: int) -> OperationResult:
        if not (0 <= index < len(self.state.runs)):
            return OperationResult.failure("Select a run to remove.")
        removed = self.state.runs.pop(index)
        if index == self.state.active_run_index:
            self.state.active_run_index = min(index, len(self.state.runs) - 1)
        elif index < self.state.active_run_index:
            self.state.active_run_index -= 1
        return OperationResult.success(f"Removed '{removed.get('name', 'Run')}'.")

    def duplicate_run(self, index: int) -> OperationResult:
        if not (0 <= index < len(self.state.runs)):
            return OperationResult.failure("Select a run to duplicate.")
        source = self.state.runs[index]
        df = source.get("df")
        duplicate = self.make_run_entry(
            name=f"{source.get('name', f'Run {index + 1}')} Copy",
            filepath=source.get("filepath", ""),
            sheet_name=source.get("sheet_name", ""),
            df=df.copy(deep=False) if isinstance(df, pd.DataFrame) else df,
            enabled=bool(source.get("enabled", True)),
        )
        self.state.runs.append(duplicate)
        return OperationResult.success(f"Duplicated '{source.get('name', 'Run')}'.", payload=len(self.state.runs) - 1)

    def rename_run(self, index: int, new_name: str) -> OperationResult:
        if not (0 <= index < len(self.state.runs)):
            return OperationResult.failure("Select a run to rename.")
        name = str(new_name).strip()
        if not name:
            return OperationResult.failure("Please enter a run name.")
        self.state.runs[index]["name"] = name
        return OperationResult.success(f"Renamed to '{name}'.")

    def set_active(self, index: int) -> OperationResult:
        if not (0 <= index < len(self.state.runs)):
            return OperationResult.failure("Select a run to make active.")
        self.state.active_run_index = index
        return OperationResult.success(f"'{self.state.runs[index].get('name', 'Run')}' is now the active run.")

    def toggle_enabled(self, index: int) -> OperationResult:
        if not (0 <= index < len(self.state.runs)):
            return OperationResult.failure("Select a run to toggle.")
        run = self.state.runs[index]
        run["enabled"] = not bool(run.get("enabled", True))
        state = "enabled" if run["enabled"] else "disabled"
        return OperationResult.success(f"'{run.get('name', 'Run')}' {state}.")

    def run_rows(self) -> list[dict[str, Any]]:
        """Return one display row per run for the runs table."""
        rows: list[dict[str, Any]] = []
        for index, run in enumerate(self.state.runs):
            df = run.get("df")
            rows.append(
                {
                    "Name": run.get("name", f"Run {index + 1}"),
                    "Enabled": "Yes" if run.get("enabled", True) else "No",
                    "Active": "Yes" if index == self.state.active_run_index else "",
                    "File": str(run.get("filepath", "")),
                    "Sheet": run.get("sheet_name", ""),
                    "Rows": f"{len(df):,}" if isinstance(df, pd.DataFrame) else "0",
                    "Columns": f"{len(df.columns):,}" if isinstance(df, pd.DataFrame) else "0",
                }
            )
        return rows

    # ------------------------------------------------------------------
    # Comparison settings (stored on AppState.comparison)
    # ------------------------------------------------------------------
    def get_setting(self, name: str) -> bool:
        return bool(getattr(self.state.comparison, name, False))

    def set_setting(self, name: str, value: bool) -> None:
        if hasattr(self.state.comparison, name):
            setattr(self.state.comparison, name, bool(value))

    # ------------------------------------------------------------------
    # Comparison data
    # ------------------------------------------------------------------
    def common_x_range(self, selected_x: str) -> Optional[tuple[float, float]]:
        return run_comparison_service.comparison_common_x_range(self.enabled_runs(), selected_x)

    def comparison_plot_items(
        self,
        selected_x: str,
        y_columns: list[str],
        *,
        use_common_x: bool,
        xmin: Optional[float] = None,
        xmax: Optional[float] = None,
        prefix_legend: bool = True,
    ) -> tuple[list[dict[str, Any]], list[str]]:
        """Prepare drawable comparison items for the enabled runs.

        Returns ``(items, skipped)`` where each item is
        ``{"label", "x", "y", "colour"}`` and ``skipped`` lists human-readable
        reasons a run/channel produced no data.
        """
        items: list[dict[str, Any]] = []
        skipped: list[str] = []
        runs = self.enabled_runs()
        common_range = self.common_x_range(selected_x) if use_common_x else None
        for run in runs:
            df = run.get("df")
            name = run.get("name", "Run")
            if not isinstance(df, pd.DataFrame):
                skipped.append(f"{name}: no dataframe")
                continue
            for channel in y_columns:
                if channel not in df.columns:
                    skipped.append(f"{name}: missing '{channel}'")
                    continue
                x_column = _matching_x_column_for_y(selected_x, channel, df.columns)
                if x_column not in df.columns:
                    skipped.append(f"{name}: missing X column '{selected_x}' for '{channel}'")
                    continue
                frame = run_comparison_service.comparison_channel_frame(
                    df, x_column, channel, common_range, xmin, xmax
                )
                if frame.empty:
                    skipped.append(f"{name}: no numeric data for '{channel}'")
                    continue
                label = f"{name} | {channel}" if prefix_legend else channel
                items.append(
                    {
                        "label": label,
                        "x": frame["x"].to_numpy(dtype=float),
                        "y": frame["y"].to_numpy(dtype=float),
                        "colour": run.get("colour") or None,
                    }
                )
        return items, skipped

    def comparison_statistics(self, y_columns: list[str]) -> list[dict[str, Any]]:
        """Return one stats row per enabled run / available channel.

        Each row is ``{"run", "channel", "Count", "Min", "Max", "Mean", "Std Dev"}``
        with raw numeric values; the UI applies any number formatting.
        """
        rows: list[dict[str, Any]] = []
        for run in self.enabled_runs():
            df = run.get("df")
            if not isinstance(df, pd.DataFrame):
                continue
            for channel in y_columns:
                stats = run_comparison_service.run_channel_statistics(df, channel)
                if stats is None:
                    continue
                rows.append({"run": run.get("name", "Run"), "channel": channel, **stats})
        return rows

    def serialise_runs(self) -> list[dict[str, Any]]:
        return run_comparison_service.serialise_runs(self.state.runs)
