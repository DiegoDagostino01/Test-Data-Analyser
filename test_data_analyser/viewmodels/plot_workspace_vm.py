"""Plot-workspace viewmodel.

Coordinates plot-data preparation, statistics, selected-data ranges, prepared
render series, and FFT for the active dataframe through the service layer. It
pulls numeric series from ``AppState.df`` itself (via
:func:`data_io.numeric_series`) and applies the per-channel X matching used for
wide grouped files.
"""
from __future__ import annotations

from typing import Optional, Tuple

import pandas as pd

from ..core.data_io import numeric_series
from ..core.filters import estimate_sampling_rate
from ..domain import PlotData
from ..services import fft_service, plotting_data_service, statistics_service
from ..services.results import OperationResult
from ..core.utils import _matching_x_column_for_y
from .app_state import AppState


class PlotWorkspaceViewModel:
    def __init__(self, state: AppState) -> None:
        self.state = state

    def _numeric(self, column: str) -> pd.Series:
        if self.state.df is None or column not in self.state.df.columns:
            return pd.Series(dtype=float)
        return numeric_series(self.state.df[column])

    def prepare_plot_data(
        self,
        x_col: str,
        y_cols: list[str],
        xmin: Optional[float] = None,
        xmax: Optional[float] = None,
    ) -> PlotData:
        """Prepare :class:`PlotData` for the given selection and analysis window.

        Raises ``ValueError`` for empty/invalid selections or an inverted window
        (mirroring the existing plotting behaviour).
        """
        if self.state.df is None:
            raise ValueError("Please load a data file first.")
        if not x_col:
            raise ValueError("Please select an X-axis column.")
        if not y_cols:
            raise ValueError("Please select at least one Y-axis column.")
        x = self._numeric(x_col)
        y_map = {col: self._numeric(col) for col in y_cols}
        x_map = {
            col: self._numeric(_matching_x_column_for_y(x_col, col, self.state.df.columns))
            for col in y_cols
        }
        return plotting_data_service.apply_analysis_window(x, y_map, x_map, xmin, xmax)

    def selected_ranges(
        self,
        data: PlotData,
        secondary_y: set[str] | None = None,
    ) -> Tuple[Optional[Tuple[float, float]], Optional[Tuple[float, float]]]:
        return statistics_service.selected_xy_ranges(data, secondary_y or set())

    def secondary_range(self, data: PlotData, secondary_y: set[str]) -> Optional[Tuple[float, float]]:
        return statistics_service.secondary_y_range(data, secondary_y)

    def statistics(self, y_cols: list[str], decimal_places: int = 4) -> pd.DataFrame:
        columns = {col: self._numeric(col) for col in y_cols}
        return statistics_service.compute_statistics(columns, decimal_places)

    def plot_series(
        self,
        data: PlotData,
        *,
        secondary_y: set[str] | None = None,
        use_filter: bool = False,
        cutoff: Optional[float] = None,
        order: int = 4,
    ) -> OperationResult:
        return plotting_data_service.prepare_plot_series(
            data,
            secondary_y=secondary_y,
            use_filter=use_filter,
            cutoff=cutoff,
            order=order,
        )

    def comparison_series(self, items: list[dict]) -> list[dict]:
        return plotting_data_service.prepare_comparison_series(items)

    def sampling_rate(self, data: PlotData) -> Optional[float]:
        return estimate_sampling_rate(data.x)

    def fft_series(
        self,
        data: PlotData,
        fs: float,
        window_name: str = "hanning",
        overlap_percent: int = 50,
    ) -> list[dict]:
        return fft_service.fft_plot_series(data, fs, window_name, overlap_percent)

    def fft(
        self,
        values,
        fs: float,
        window_name: str = "hanning",
        overlap_percent: int = 50,
    ):
        return fft_service.fft_spectrum(values, fs, window_name, overlap_percent)
