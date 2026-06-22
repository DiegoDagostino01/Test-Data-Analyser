"""Data-loading viewmodel.

Coordinates file/sheet loading through the data-I/O layer and updates
:class:`AppState`. Returns :class:`OperationResult` instead of showing dialogs or
message boxes, so any UI can drive it. The Qt shell integrates with this
viewmodel.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from ..core.config import DOMAIN_CONFIG
from ..core.data_io import get_excel_sheets, load_data
from ..domain import SOURCE_EXCEL
from ..services import dataset_service
from ..services.results import OperationResult
from ..core.utils import infer_column_by_keywords
from .app_state import AppState


class DataLoadingViewModel:
    def __init__(self, state: AppState) -> None:
        self.state = state

    def get_sheets(self, path: str | Path) -> list[str]:
        """Return the Excel sheet names for ``path`` (empty for CSV/invalid)."""
        try:
            return get_excel_sheets(path)
        except Exception:
            return []

    def load_file(self, path: str | Path, sheet_name: Optional[str] = None) -> OperationResult:
        """Load a data file into the application state.

        On success the state's ``df``/``filepath``/``sheet_name`` are updated and
        the result payload carries the loaded column names.
        """
        file_path = Path(path)
        if not file_path.exists():
            return OperationResult.failure(f"File not found: {file_path}")
        try:
            df = load_data(file_path, sheet_name or None, settings_manager=self.state.settings_manager)
        except Exception as exc:
            return OperationResult.failure(str(exc))

        new_root_file_directory = str(file_path.resolve().parent)
        previous_path = self.state.filepath
        previous_root_file_directory = self.state.root_file_directory

        self.state.df = df
        self.state.filepath = file_path
        self.state.root_file_directory = new_root_file_directory
        if previous_path != file_path or previous_root_file_directory != new_root_file_directory:
            self.state.is_dirty = True
        self.state.sheet_name = sheet_name or ""
        self.state.data_source_type = SOURCE_EXCEL
        self.state.channel_registry = dataset_service.build_registry_for_dataframe(df)
        columns = [str(column) for column in df.columns]
        return OperationResult.success(
            f"Loaded {len(df):,} rows and {len(columns):,} columns.",
            payload=columns,
        )

    def suggested_x_column(self, columns: list[str]) -> str:
        """Return the best default X column (a time-like column, else the first)."""
        if not columns:
            return ""
        return infer_column_by_keywords(columns, DOMAIN_CONFIG["Time"]) or columns[0]
