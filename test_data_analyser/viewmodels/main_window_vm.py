"""Main-window viewmodel.

The top-level coordinator the application shell builds on. It owns the
:class:`AppState` and the feature viewmodels, and provides session save/load
coordination through ``session_service``. It holds no Tkinter or PySide6 objects
and opens no dialogs; the UI supplies an explicit path for session I/O.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from ..core.config import __version__
from ..domain import normalise_plot_profile
from ..services import session_service
from ..services.results import OperationResult
from .app_state import AppState
from .cursor_compare_vm import CursorCompareViewModel
from .data_loading_vm import DataLoadingViewModel
from .engineering_notes_vm import EngineeringNotesViewModel
from .limits_vm import LimitsViewModel
from .maths_channels_vm import MathsChannelsViewModel
from .plot_workspace_vm import PlotWorkspaceViewModel
from .raw_data_vm import RawDataViewModel
from .runs_comparison_vm import RunsComparisonViewModel
from .settings_vm import SettingsViewModel


class MainWindowViewModel:
    def __init__(self, settings_manager: Any = None) -> None:
        self.state = AppState(settings_manager=settings_manager)
        self.settings = SettingsViewModel(settings_manager)
        self.data_loading = DataLoadingViewModel(self.state)
        self.plot_workspace = PlotWorkspaceViewModel(self.state)
        self.raw_data = RawDataViewModel(self.state)
        self.maths_channels = MathsChannelsViewModel(self.state)
        self.runs_comparison = RunsComparisonViewModel(self.state)
        self.limits = LimitsViewModel(self.state)
        self.engineering_notes = EngineeringNotesViewModel(self.state)
        self.cursor_compare = CursorCompareViewModel()

    # ------------------------------------------------------------------
    # Session persistence
    # ------------------------------------------------------------------
    def build_session(self) -> dict[str, Any]:
        """Assemble a normalised session dictionary from the current state."""
        return session_service.build_session_dict(
            version=__version__,
            file_path=str(self.state.filepath) if self.state.filepath else "",
            sheet_name=self.state.sheet_name,
            runs=self.runs_comparison.serialise_runs(),
            comparison=self.state.comparison.to_dict(),
            active_plot_profile_index=self.state.active_plot_profile_index,
            plot_profiles=[normalise_plot_profile(profile) for profile in self.state.plot_profiles],
            calculated_channels=self.maths_channels.normalise_definitions(self.state.calculated_channels),
        )

    def save_session(self, path: str | Path) -> OperationResult:
        try:
            session = self.build_session()
            saved_path = session_service.save_session_dict(path, session)
        except Exception as exc:
            return OperationResult.failure(f"Could not save the analysis session: {exc}")
        return OperationResult.success(f"Session saved successfully:\n{saved_path}", payload=str(saved_path))

    def load_session(self, path: str | Path) -> OperationResult:
        """Load a session file and apply its UI-independent state.

        Plot profiles, the active profile index, calculated-channel definitions,
        and comparison settings are applied to the state. Run dataframes and the
        source file are not reloaded here (that requires file I/O the UI/loading
        layer coordinates); the normalised :class:`SessionState` is returned in
        the payload so the caller can complete run/file restoration.
        """
        try:
            raw = session_service.load_session_dict(path)
        except Exception as exc:
            return OperationResult.failure(str(exc))
        session = session_service.normalise_session(raw)

        self.state.plot_profiles = [normalise_plot_profile(profile.to_dict()) for profile in session.plot_profiles]
        if not self.state.plot_profiles:
            self.state.plot_profiles = [normalise_plot_profile({"name": "Plot 1"})]
        self.state.active_plot_profile_index = max(
            0, min(session.active_plot_profile_index, len(self.state.plot_profiles) - 1)
        )
        self.state.calculated_channels = {
            name: definition.to_dict() for name, definition in session.calculated_channels.items()
        }
        self.state.comparison = session.comparison
        self.state.active_run_index = session.comparison.active_run_index
        return OperationResult.success("Session loaded.", payload=session)

    # ------------------------------------------------------------------
    # Qt working-state capture / full restoration
    # ------------------------------------------------------------------
    def capture_working_state(
        self,
        *,
        x_column: str = "",
        y_columns: list[str] | None = None,
        secondary_y_columns: list[str] | None = None,
        title: str = "",
        x_label: str = "",
        y_label: str = "",
        secondary_y_label: str = "",
        plot_kind: str = "Line",
        auto_fit_axes: bool = True,
        axis_limits: dict[str, Any] | None = None,
        legend_settings: dict[str, Any] | None = None,
        analysis_window: dict[str, Any] | None = None,
        filter_settings: dict[str, Any] | None = None,
        generated: bool = False,
    ) -> None:
        """Fold the current top-level limits/notes + axis selection into one profile.

        The Qt shell keeps limit lines and engineering notes as top-level working
        state and the axis selection in the panel; this folds them into a single
        plot profile so :meth:`save_session` persists a session compatible with
        the existing on-disk format.
        """
        name = self.state.plot_profiles[0]["name"] if self.state.plot_profiles else "Plot 1"
        self.state.plot_profiles = [
            normalise_plot_profile(
                {
                    "name": name,
                    "x_column": x_column,
                    "y_columns": list(y_columns or []),
                    "secondary_y_columns": list(secondary_y_columns or []),
                    "title": title.strip() or "Engineering Test Data",
                    "x_label": x_label.strip(),
                    "y_label": y_label.strip() or "Selected Signals",
                    "secondary_y_label": secondary_y_label.strip(),
                    "plot_kind": plot_kind or "Line",
                    "auto_fit_axes": auto_fit_axes,
                    "axis_limits": dict(axis_limits or {}),
                    "legend": dict(legend_settings or {}),
                    "analysis_window": dict(analysis_window or {}),
                    "filter": dict(filter_settings or {}),
                    "generated": bool(generated),
                    "manual_labels": {
                        "title": bool(title.strip()),
                        "x_label": bool(x_label.strip()),
                        "y_label": bool(y_label.strip()),
                        "secondary_y_label": bool(secondary_y_label.strip()),
                    },
                    "limit_lines": [dict(line) for line in self.state.limit_lines],
                    "engineering_notes": dict(self.state.engineering_notes),
                }
            )
        ]
        self.state.active_plot_profile_index = 0

    def restore_session(self, path: str | Path) -> OperationResult:
        """Load a session and fully restore the file, runs, and working state.

        Reloads the source dataframe, recalculates maths channels, reloads the
        comparison runs from their saved paths, and pulls the active profile's
        limit lines / engineering notes into the top-level working state. The
        payload is the restored axis selection
        (``x_column``/``y_columns``/``secondary_y_columns``) so the UI can apply
        it; ``warnings`` lists anything that could not be reloaded.
        """
        result = self.load_session(path)
        if not result.ok:
            return result
        session = result.payload
        warnings: list[str] = []

        profile = self.state.active_plot_profile() or {}
        self.state.limit_lines = [dict(line) for line in profile.get("limit_lines", [])]
        self.state.active_limit_line_index = 0
        self.state.engineering_notes = dict(profile.get("engineering_notes", {}))

        if session.file_path:
            load_result = self.data_loading.load_file(session.file_path, session.sheet_name or None)
            if not load_result.ok:
                warnings.append(f"Main data file: {load_result.message}")

        if self.state.df is not None and self.state.calculated_channels:
            warnings.extend(self.maths_channels.recalculate().errors)

        self.state.runs = []
        self.state.active_run_index = -1
        for run_meta in session.runs:
            if not run_meta.filepath:
                continue
            add_result = self.runs_comparison.add_run(run_meta.filepath, run_meta.sheet_name or None)
            if not add_result.ok:
                warnings.append(f"Run '{run_meta.name}': {add_result.message}")
                continue
            run = self.state.runs[add_result.payload]
            run["name"] = run_meta.name or run["name"]
            run["enabled"] = run_meta.enabled
            if run_meta.colour:
                run["colour"] = run_meta.colour
        self.state.active_run_index = session.comparison.active_run_index

        selection = {
            "x_column": profile.get("x_column", ""),
            "y_columns": list(profile.get("y_columns", [])),
            "secondary_y_columns": list(profile.get("secondary_y_columns", [])),
        }
        message = "Session loaded."
        if warnings:
            message += f" {len(warnings)} item(s) could not be fully restored."
        return OperationResult.success(message, payload=selection, warnings=warnings)
