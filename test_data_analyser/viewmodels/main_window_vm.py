"""Main-window viewmodel.

The top-level coordinator the application shell builds on. It owns the
:class:`AppState` and the feature viewmodels, and provides session save/load
coordination through ``session_service``. It holds no Tkinter or PySide6 objects
and opens no dialogs; the UI supplies an explicit path for session I/O.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
from difflib import SequenceMatcher
from typing import Any, Optional, cast

import pandas as pd

from ..core.config import __version__
from ..core.channel_classification import classify_channel_name
from ..core.indexing import clamp_index
from ..domain import SOURCE_EXCEL, SOURCE_MANUAL, ComparisonSettings, normalise_plot_profile
from ..services import dataset_service, plot_profile_service, plot_render_service, session_service
from ..services.results import OperationResult
from .app_state import AppState
from .cursor_compare_vm import CursorCompareViewModel
from .data_loading_vm import DataLoadingViewModel
from .dataset_vm import DatasetViewModel
from .engineering_notes_vm import EngineeringNotesViewModel
from .limits_vm import LimitsViewModel
from .maths_channels_vm import MathsChannelsViewModel
from .plot_workspace_vm import PlotWorkspaceViewModel
from .raw_data_vm import RawDataViewModel
from .runs_comparison_vm import RunsComparisonViewModel
from .settings_vm import SettingsViewModel
from .state_controller import AppStateController


class MainWindowViewModel:
    def __init__(self, settings_manager: Any = None) -> None:
        self.state = AppState(settings_manager=settings_manager)
        self._state_controller = AppStateController(self.state)
        self.settings = SettingsViewModel(settings_manager)
        self.data_loading = DataLoadingViewModel(self.state)
        self.dataset = DatasetViewModel(self.state)
        self.plot_workspace = PlotWorkspaceViewModel(self.state)
        self.raw_data = RawDataViewModel(self.state)
        self.maths_channels = MathsChannelsViewModel(self.state)
        self.runs_comparison = RunsComparisonViewModel(self.state)
        self.limits = LimitsViewModel(self.state)
        self.engineering_notes = EngineeringNotesViewModel(self.state)
        self.cursor_compare = CursorCompareViewModel()

    # ------------------------------------------------------------------
    # Recent files / sessions
    # ------------------------------------------------------------------
    RECENT_LIMIT = 10

    def recent_files(self) -> list[str]:
        """Return the stored recent data-file paths, most recent first."""
        return self._recent_list("recent_files")

    def recent_sessions(self) -> list[str]:
        """Return the stored recent session paths, most recent first."""
        return self._recent_list("recent_sessions")

    def register_recent_file(self, path: str) -> list[str]:
        """Record ``path`` as the most recently opened data file."""
        return self._register_recent("recent_files", path)

    def register_recent_session(self, path: str) -> list[str]:
        """Record ``path`` as the most recently used session."""
        return self._register_recent("recent_sessions", path)

    def _recent_list(self, key: str) -> list[str]:
        manager = getattr(self.state, "settings_manager", None)
        if manager is None:
            return []
        try:
            values = manager.get("recent", key)
        except (KeyError, AttributeError):
            return []
        if not isinstance(values, list):
            return []
        return [str(item) for item in values if isinstance(item, str) and item]

    def _register_recent(self, key: str, path: str) -> list[str]:
        manager = getattr(self.state, "settings_manager", None)
        if manager is None or not path:
            return self._recent_list(key)
        resolved = str(Path(path).resolve())
        target = os.path.normcase(resolved)
        deduped = [item for item in self._recent_list(key) if os.path.normcase(item) != target]
        updated = [resolved, *deduped][: self.RECENT_LIMIT]
        try:
            manager.set("recent", key, updated)
            manager.save()
        except (KeyError, ValueError, AttributeError):
            return self._recent_list(key)
        return updated

    # ------------------------------------------------------------------
    # Auto-save scheduling
    # ------------------------------------------------------------------
    @staticmethod
    def auto_save_due(last_saved_epoch: Optional[float], now_epoch: float, interval_minutes: int) -> bool:
        """Return whether an auto-save is due given the last-save time.

        Pure timing policy with no side effects: never due for a non-positive
        interval, always due when nothing has been saved yet, otherwise due once
        ``interval_minutes`` have elapsed since ``last_saved_epoch``.
        """
        if interval_minutes <= 0:
            return False
        if last_saved_epoch is None:
            return True
        return (now_epoch - last_saved_epoch) >= interval_minutes * 60

    def auto_save_target_path(self, current_session_path: Optional[str] = None) -> str:
        """Resolve where an auto-save should be written.

        Prefers the active session path so auto-save keeps the user's own file
        current; otherwise falls back to ``autosave.json`` beside the loaded data
        file, or in the working directory when no data file is linked.
        """
        if current_session_path:
            return current_session_path
        root = self.state.root_file_directory or self._root_directory_for_file(self.state.filepath)
        if root:
            return str(Path(root) / "autosave.json")
        return "autosave.json"

    # ------------------------------------------------------------------
    # Plot-profile list management
    # ------------------------------------------------------------------
    def ensure_plot_profiles(self) -> None:
        """Ensure the state has at least one normalised plot profile."""
        profiles, active_index = plot_profile_service.ensure_profiles(
            self.state.plot_profiles,
            self.state.active_plot_profile_index,
        )
        self._state_controller.set_plot_profiles(profiles, active_index)

    def reset_plot_profiles(self) -> None:
        """Start a fresh one-plot workspace for a newly opened data file."""
        profiles, active_index = plot_profile_service.reset_profiles()
        self._state_controller.reset_plot_workspace(profiles, active_index)

    def create_manual_session(
        self, *, columns: list[str] | None = None, rows: int = 8
    ) -> OperationResult:
        """Start a blank manual data session (no linked Excel file).

        Creates a small editable starter grid with stable channel IDs, resets the
        plot workspace, runs, and maths channels, and marks the source as manual
        so plotting/maths/session save all flow through the same pipeline as
        Excel-loaded data.
        """
        names = [str(name).strip() for name in (columns or ["Column 1", "Column 2", "Column 3"])]
        names = [name for name in names if name]
        if not names:
            names = ["Column 1"]
        row_count = max(0, int(rows))
        df = pd.DataFrame(
            {name: pd.Series([float("nan")] * row_count, dtype="float64") for name in names}
        )
        self.state.df = df
        self.state.channel_registry = dataset_service.build_registry_for_dataframe(df)
        self.state.data_source_type = SOURCE_MANUAL
        self.state.filepath = None
        self.state.sheet_name = ""
        self.state.root_file_directory = ""
        self.state.calculated_channels = {}
        self.state.runs = []
        self.state.active_run_index = -1
        self.state.comparison = ComparisonSettings()
        self.reset_plot_profiles()
        self.state.is_dirty = True
        return OperationResult.success(
            "Created a new manual data session.", payload=list(df.columns)
        )

    def add_plot_profile(self, name: str = "") -> OperationResult:
        update = plot_profile_service.add_profile(
            self.state.plot_profiles,
            self.state.active_plot_profile_index,
            name=name,
            x_column=self._current_x_axis_or_default(),
        )
        self._apply_plot_profile_update(update)
        if update.result.ok:
            self._state_controller.mark_dirty()
        return update.result

    def duplicate_plot_profile(self, index: int | None = None) -> OperationResult:
        update = plot_profile_service.duplicate_profile(
            self.state.plot_profiles,
            self.state.active_plot_profile_index,
            index=index,
        )
        self._apply_plot_profile_update(update)
        if update.result.ok:
            self._state_controller.mark_dirty()
        return update.result

    def rename_plot_profile(self, index: int, name: str) -> OperationResult:
        update = plot_profile_service.rename_profile(
            self.state.plot_profiles,
            self.state.active_plot_profile_index,
            index,
            name,
        )
        self._apply_plot_profile_update(update)
        if update.result.ok:
            self._state_controller.mark_dirty()
        return update.result

    def delete_plot_profile(self, index: int | None = None) -> OperationResult:
        update = plot_profile_service.delete_profile(
            self.state.plot_profiles,
            self.state.active_plot_profile_index,
            index=index,
        )
        self._apply_plot_profile_update(update)
        if update.result.ok:
            self._state_controller.mark_dirty()
        return update.result

    def select_plot_profile(self, index: int) -> OperationResult:
        update = plot_profile_service.select_profile(
            self.state.plot_profiles,
            self.state.active_plot_profile_index,
            index,
        )
        self._apply_plot_profile_update(update)
        return update.result

    def reorder_plot_profile(self, from_index: int, to_index: int) -> OperationResult:
        """Move a plot profile from ``from_index`` to ``to_index``.

        Pure list manipulation that keeps the active profile selected as it moves.
        """
        profiles = self.state.plot_profiles
        count = len(profiles)
        if not (0 <= from_index < count) or not (0 <= to_index < count):
            return OperationResult.failure("Invalid plot tab positions.")
        if from_index == to_index:
            return OperationResult.success("No change.")
        active = self.state.active_plot_profile_index
        moved = profiles.pop(from_index)
        profiles.insert(to_index, moved)
        if active == from_index:
            active = to_index
        elif from_index < active <= to_index:
            active -= 1
        elif to_index <= active < from_index:
            active += 1
        self.state.active_plot_profile_index = clamp_index(active, len(profiles))
        self._state_controller.mark_dirty()
        return OperationResult.success("Reordered plots.")

    def reset_active_axis_appearance(self) -> OperationResult:
        """Clear manual title/labels/axis limits/ticks for the active plot.

        Plotted data, channel selection, and best-fit settings are preserved; the
        cleared appearance fields fall back to their normalised defaults so the
        next render auto-labels and auto-fits.
        """
        index = self.state.active_plot_profile_index
        if not (0 <= index < len(self.state.plot_profiles)):
            return OperationResult.failure("There is no active plot to reset.")
        profile = self.state.plot_profiles[index]
        for key in (
            "axis_limits",
            "axis_ticks",
            "manual_labels",
            "title",
            "x_label",
            "y_label",
            "secondary_y_label",
        ):
            profile.pop(key, None)
        self.state.plot_profiles[index] = normalise_plot_profile(profile)
        self._state_controller.mark_dirty()
        return OperationResult.success("Reset axis title, labels, limits, and ticks.")

    def set_current_x_axis(self, x_column: str) -> str:
        """Remember the current X-axis selection if it is available in the active data."""
        candidate = str(x_column).strip()
        self.state.current_x_axis = candidate if candidate in self.state.column_names() else ""
        return self.state.current_x_axis

    def _clamped_profile_index(self, index: int) -> int:
        return clamp_index(index, len(self.state.plot_profiles))

    def _apply_plot_profile_update(self, update: plot_profile_service.PlotProfileListUpdate) -> None:
        self._state_controller.set_plot_profiles(update.profiles, update.active_index)

    def _current_x_axis_or_default(self) -> str:
        current = str(self.state.current_x_axis).strip()
        columns = self.state.column_names()
        if current and current in columns:
            return current
        return self.data_loading.suggested_x_column(columns)

    def persistent_plot_channel_colours(
        self,
        active_y_columns: list[str],
        active_secondary_y_columns: list[str] | None = None,
    ) -> dict[str, str]:
        """Return stable colours for channels repeated across generated plot profiles."""
        self.ensure_plot_profiles()
        active_channels = plot_render_service.y_axis_channel_set(
            active_y_columns,
            active_secondary_y_columns or [],
        )
        channel_sets: list[list[str]] = []
        for index, profile in enumerate(self.state.plot_profiles):
            if index == self.state.active_plot_profile_index:
                if active_channels:
                    channel_sets.append(active_channels)
                continue
            if not profile.get("generated"):
                continue
            profile_channels = plot_render_service.y_axis_channel_set(
                profile.get("y_columns", []),
                profile.get("secondary_y_columns", []),
            )
            if profile_channels:
                channel_sets.append(profile_channels)
        colours = plot_render_service.persistent_channel_colour_map(channel_sets, self.settings.plot_colours())
        colours.update(self._legend_channel_colour_overrides())
        return colours

    def active_legend_channel_overrides(self) -> dict[str, dict[str, str]]:
        """Return the active profile's per-channel legend style overrides."""
        self.ensure_plot_profiles()
        return plot_profile_service.profile_legend_channel_overrides(self.state.active_plot_profile() or {})

    def update_active_legend_channel_override(self, channel: str, style: dict[str, Any]) -> OperationResult:
        """Store a legend-row style override for the active profile."""
        self.ensure_plot_profiles()
        result = plot_profile_service.update_legend_channel_override(
            self.state.plot_profiles,
            self.state.active_plot_profile_index,
            channel,
            style,
        )
        if result.ok:
            self._state_controller.mark_dirty()
        return result

    def _legend_channel_colour_overrides(self) -> dict[str, str]:
        self.ensure_plot_profiles()
        return plot_profile_service.legend_channel_colour_overrides(self.state.plot_profiles)

    def plot_selection_preserves_appearance(self, previous: dict[str, Any], current: dict[str, Any]) -> bool:
        """Return whether a new Generate Plot request can keep live axis appearance.

        Plot-kind-only changes should preserve Figure Options edits. Added or
        swapped channels can also preserve appearance when their names and data
        ranges are close to channels already on the plot. A changed X column,
        analysis window, or materially different Y channel asks the UI to reset
        axis labels, axis limits, and tick settings.
        """
        previous_x = str(previous.get("x_column", "")).strip()
        current_x = str(current.get("x_column", "")).strip()
        if not previous_x or plot_render_service.normalise_channel_name(previous_x) != plot_render_service.normalise_channel_name(current_x):
            return False
        if previous.get("xmin") != current.get("xmin") or previous.get("xmax") != current.get("xmax"):
            return False
        for key in ("use_filter", "cutoff", "order"):
            if previous.get(key) != current.get(key):
                return False

        previous_channels = plot_render_service.y_axis_channel_set(
            previous.get("primary_y", []),
            previous.get("secondary_y", []),
        )
        current_channels = plot_render_service.y_axis_channel_set(
            current.get("primary_y", []),
            current.get("secondary_y", []),
        )
        if not previous_channels or not current_channels:
            return False
        if self._selection_moves_channel_between_axes(previous, current):
            return False

        previous_ranges = self._selection_channel_ranges(previous_x, previous_channels, previous.get("xmin"), previous.get("xmax"))
        current_ranges = self._selection_channel_ranges(current_x, current_channels, current.get("xmin"), current.get("xmax"))
        if not previous_ranges or not current_ranges:
            return False

        for channel in current_channels:
            current_key = plot_render_service.normalise_channel_name(channel)
            if current_key in previous_ranges:
                continue
            current_item = current_ranges.get(current_key)
            if current_item is None:
                return False
            _current_channel, current_range = current_item
            if not any(
                self._channels_preserve_appearance(channel, current_range, previous_channel, previous_range)
                for previous_channel, previous_range in previous_ranges.values()
            ):
                return False
        return True

    @staticmethod
    def _selection_moves_channel_between_axes(previous: dict[str, Any], current: dict[str, Any]) -> bool:
        previous_primary = {
            plot_render_service.normalise_channel_name(channel) for channel in previous.get("primary_y", [])
        }
        previous_secondary = {
            plot_render_service.normalise_channel_name(channel) for channel in previous.get("secondary_y", [])
        }
        current_primary = {
            plot_render_service.normalise_channel_name(channel) for channel in current.get("primary_y", [])
        }
        current_secondary = {
            plot_render_service.normalise_channel_name(channel) for channel in current.get("secondary_y", [])
        }
        return bool((current_primary & previous_secondary) or (current_secondary & previous_primary))

    def _selection_channel_ranges(
        self,
        x_column: str,
        channels: list[str],
        xmin: object,
        xmax: object,
    ) -> dict[str, tuple[str, tuple[float, float]]]:
        try:
            data = self.plot_workspace.prepare_plot_data(
                x_column,
                channels,
                self._optional_float(xmin),
                self._optional_float(xmax),
            )
        except ValueError:
            return {}
        ranges: dict[str, tuple[str, tuple[float, float]]] = {}
        for channel, series in data.y_map.items():
            values = series.dropna()
            if values.empty:
                continue
            key = plot_render_service.normalise_channel_name(channel)
            if key:
                ranges[key] = (str(channel), (float(values.min()), float(values.max())))
        return ranges

    @classmethod
    def _channels_preserve_appearance(
        cls,
        current_channel: str,
        current_range: tuple[float, float],
        previous_channel: str,
        previous_range: tuple[float, float],
    ) -> bool:
        return cls._channel_names_similar(current_channel, previous_channel) and cls._channel_ranges_similar(
            current_range,
            previous_range,
        )

    @staticmethod
    def _channel_names_similar(left: str, right: str) -> bool:
        left_key = plot_render_service.normalise_channel_name(left)
        right_key = plot_render_service.normalise_channel_name(right)
        if not left_key or not right_key:
            return False
        if left_key == right_key:
            return True
        if SequenceMatcher(None, left_key, right_key).ratio() >= 0.72:
            return True
        left_tokens = set(re.findall(r"[a-z]+", left_key))
        right_tokens = set(re.findall(r"[a-z]+", right_key))
        if not left_tokens.intersection(right_tokens):
            return False
        left_group = classify_channel_name(left)
        right_group = classify_channel_name(right)
        return left_group == right_group or left_group == "Other Numeric" or right_group == "Other Numeric"

    @staticmethod
    def _channel_ranges_similar(
        left: tuple[float, float],
        right: tuple[float, float],
        tolerance: float = 0.25,
    ) -> bool:
        left_min, left_max = min(left), max(left)
        right_min, right_max = min(right), max(right)
        left_span = max(left_max - left_min, 1e-9)
        right_span = max(right_max - right_min, 1e-9)
        scale = max(abs(left_min), abs(left_max), abs(right_min), abs(right_max), left_span, right_span, 1.0)
        center_delta = abs(((left_min + left_max) / 2.0) - ((right_min + right_max) / 2.0))
        span_delta = abs(left_span - right_span)
        return center_delta <= tolerance * scale and span_delta <= tolerance * max(left_span, right_span, 1.0)

    @staticmethod
    def _optional_float(value: object) -> Optional[float]:
        if value is None:
            return None
        try:
            return float(cast(Any, value))
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Session persistence
    # ------------------------------------------------------------------
    def build_session(self) -> dict[str, Any]:
        """Assemble a normalised session dictionary from the current state."""
        return session_service.build_runtime_session_dict(
            version=__version__,
            root_file_directory=self.state.root_file_directory or self._root_directory_for_file(self.state.filepath),
            file_path=str(self.state.filepath) if self.state.filepath else "",
            sheet_name=self.state.sheet_name,
            runs=self.runs_comparison.serialise_runs(),
            comparison=self.state.comparison.to_dict(),
            active_plot_profile_index=self.state.active_plot_profile_index,
            plot_profiles=self.state.plot_profiles,
            calculated_channels=self.state.calculated_channels,
            data_source_type=self.state.data_source_type,
            channel_registry=self.state.channel_registry,
            df=self.state.df,
        )

    def save_session(self, path: str | Path, *, mark_clean: bool = True) -> OperationResult:
        try:
            session = self.build_session()
            saved_path = session_service.save_session_dict(path, session)
        except Exception as exc:
            return OperationResult.failure(f"Could not save the analysis session: {exc}")
        if mark_clean:
            self.state.is_dirty = False
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
        self.state.data_source_type = session.data_source_type
        self.state.channel_registry = session.channel_registry
        self.state.root_file_directory = session.root_file_directory
        self.state.comparison = session.comparison
        self.state.active_run_index = session.comparison.active_run_index
        self.state.is_dirty = False
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
        axis_ticks: dict[str, Any] | None = None,
        legend_settings: dict[str, Any] | None = None,
        best_fit_lines: list[dict[str, Any]] | None = None,
        annotations: list[dict[str, Any]] | None = None,
        analysis_window: dict[str, Any] | None = None,
        filter_settings: dict[str, Any] | None = None,
        generated: bool = False,
    ) -> None:
        """Fold the current top-level limits/notes + axis selection into the active profile.

        The Qt shell keeps limit lines and engineering notes as top-level working
        state and the axis selection in the panel; this folds them into the
        active plot profile so :meth:`save_session` persists every plot tab with
        the existing on-disk format.
        """
        self.ensure_plot_profiles()
        self.set_current_x_axis(x_column)
        index = self._clamped_profile_index(self.state.active_plot_profile_index)
        profile = plot_profile_service.capture_working_profile(
            self.state.plot_profiles[index],
            index,
            x_column=x_column,
            y_columns=y_columns,
            secondary_y_columns=secondary_y_columns,
            title=title,
            x_label=x_label,
            y_label=y_label,
            secondary_y_label=secondary_y_label,
            plot_kind=plot_kind,
            auto_fit_axes=auto_fit_axes,
            axis_limits=axis_limits,
            axis_ticks=axis_ticks,
            legend_settings=legend_settings,
            best_fit_lines=best_fit_lines,
            annotations=annotations,
            analysis_window=analysis_window,
            filter_settings=filter_settings,
            generated=generated,
            limit_lines=self.state.limit_lines,
            engineering_notes=self.state.engineering_notes,
        )
        if profile != self.state.plot_profiles[index]:
            self._state_controller.mark_dirty()
        self._state_controller.set_active_plot_profile(index, profile)

    def restore_session(
        self,
        path: str | Path,
        data_file_override: str | Path | None = None,
    ) -> OperationResult:
        """Load a session and fully restore the file, runs, and working state.

        Reloads the source dataframe, recalculates maths channels, reloads the
        comparison runs from their saved paths, and pulls the active profile's
        limit lines / engineering notes into the top-level working state. The
        ``data_file_override`` lets the UI relink a moved source file without
        rewriting the session first. The payload is the restored axis selection
        plus main-data restore metadata so the UI can apply it and decide
        whether to prompt for a replacement file; ``warnings`` lists anything
        that could not be reloaded.
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

        source_file_path = ""
        main_data_warning = ""
        self.state.df = None
        self.state.filepath = None

        if session.data_source_type == SOURCE_MANUAL:
            self.state.data_source_type = SOURCE_MANUAL
            self.state.channel_registry = session.channel_registry
            self.state.df = dataset_service.dataframe_from_rows(
                session.channel_registry, session.dataset_rows
            )
            self.state.sheet_name = ""
            self.state.root_file_directory = session.root_file_directory
        else:
            self.state.data_source_type = SOURCE_EXCEL
            source_file_path = str(data_file_override) if data_file_override else self._source_file_from_session(session)
            self.state.root_file_directory = session.root_file_directory
            self.state.sheet_name = session.sheet_name
            if source_file_path:
                load_result = self.data_loading.load_file(source_file_path, session.sheet_name or None)
                if not load_result.ok:
                    main_data_warning = load_result.message
                    warnings.append(f"Main data file: {main_data_warning}")
                    self.state.root_file_directory = self._root_directory_from_text(source_file_path)
                else:
                    # Preserve saved channel IDs across the disk reload so that
                    # ID-based profile/maths references keep resolving.
                    self.state.channel_registry = dataset_service.build_registry_for_dataframe(
                        self.state.df, existing=session.channel_registry
                    )

        if self.state.df is not None and self.state.calculated_channels:
            warnings.extend(self.maths_channels.recalculate().errors)
        if self.state.df is not None:
            warnings.extend(self._missing_saved_plot_channel_warnings())

        self.state.runs = []
        self.state.active_run_index = -1
        loaded_frames: dict[tuple[str, str], pd.DataFrame] = {}
        if source_file_path and isinstance(self.state.df, pd.DataFrame):
            loaded_frames[self._dataframe_cache_key(source_file_path, session.sheet_name or None)] = self.state.df
        for run_meta in session.runs:
            if not run_meta.filepath:
                continue
            run_sheet = run_meta.sheet_name or None
            cache_key = self._dataframe_cache_key(run_meta.filepath, run_sheet)
            cached_frame = loaded_frames.get(cache_key)
            if cached_frame is not None:
                add_result = self.runs_comparison.add_loaded_run(run_meta.filepath, run_sheet, cached_frame)
            else:
                add_result = self.runs_comparison.add_run(run_meta.filepath, run_sheet)
            if not add_result.ok:
                warnings.append(f"Run '{run_meta.name}': {add_result.message}")
                continue
            run = self.state.runs[add_result.payload]
            run_df = run.get("df")
            if isinstance(run_df, pd.DataFrame):
                loaded_frames[cache_key] = run_df
            run["name"] = run_meta.name or run["name"]
            run["enabled"] = run_meta.enabled
            if run_meta.colour:
                run["colour"] = run_meta.colour
        self.state.active_run_index = session.comparison.active_run_index

        selection = {
            "x_column": profile.get("x_column", ""),
            "y_columns": list(profile.get("y_columns", [])),
            "secondary_y_columns": list(profile.get("secondary_y_columns", [])),
            "source_file_path": source_file_path,
            "main_data_loaded": self.state.df is not None,
            "main_data_warning": main_data_warning,
        }
        self.state.is_dirty = data_file_override is not None
        message = "Session loaded."
        if warnings:
            message += f" {len(warnings)} item(s) could not be fully restored."
        return OperationResult.success(message, payload=selection, warnings=warnings)

    @staticmethod
    def needs_main_data_relink(result: OperationResult) -> bool:
        """Return whether a restored session failed to load its main data file.

        Reads the restore payload produced by :meth:`restore_session`; ``True``
        means the saved source file could not be loaded, so the UI may offer to
        relink a moved file.
        """
        payload = result.payload if isinstance(result.payload, dict) else {}
        return bool(payload.get("main_data_warning")) and not bool(payload.get("main_data_loaded"))

    @staticmethod
    def _dataframe_cache_key(path: str | Path, sheet_name: str | None) -> tuple[str, str]:
        try:
            resolved_path = str(Path(path).expanduser().resolve())
        except Exception:
            resolved_path = str(path)
        return resolved_path, str(sheet_name or "")

    @classmethod
    def _source_file_from_session(cls, session: Any) -> str:
        file_path = str(getattr(session, "file_path", "") or "")
        root_file_directory = str(getattr(session, "root_file_directory", "") or "")
        if not root_file_directory or not file_path:
            return file_path
        file_name = Path(file_path).name
        if not file_name:
            return file_path
        try:
            return str(Path(root_file_directory) / file_name)
        except Exception:
            return file_path

    @staticmethod
    def _root_directory_for_file(file_path: str | Path | None) -> str:
        if not file_path:
            return ""
        try:
            parent = Path(file_path).parent
        except Exception:
            return ""
        return "" if str(parent) in {"", "."} else str(parent)

    @staticmethod
    def _root_directory_from_text(file_path: str) -> str:
        try:
            return str(Path(file_path).expanduser().parent)
        except Exception:
            return ""

    def _missing_saved_plot_channel_warnings(self) -> list[str]:
        available = set(self.state.column_names())
        if not available:
            return []
        warnings: list[str] = []
        seen: set[tuple[str, str, str]] = set()
        for index, profile in enumerate(self.state.plot_profiles):
            profile_name = str(profile.get("name", f"Plot {index + 1}")).strip() or f"Plot {index + 1}"
            x_column = str(profile.get("x_column", "")).strip()
            if x_column and x_column not in available:
                key = (profile_name, "x", x_column)
                if key not in seen:
                    warnings.append(
                        f"The saved plot '{profile_name}' references X-axis column '{x_column}', "
                        "but this channel was not found in the current data file."
                    )
                    seen.add(key)
            for channel in self._profile_y_channel_references(profile):
                if channel in available:
                    continue
                key = (profile_name, "y", channel)
                if key in seen:
                    continue
                warnings.append(
                    f"The saved plot '{profile_name}' references '{channel}', "
                    "but this channel was not found in the current data file."
                )
                seen.add(key)
        return warnings

    @staticmethod
    def _profile_y_channel_references(profile: dict[str, Any]) -> list[str]:
        channels: list[str] = []
        for key in ("y_columns", "secondary_y_columns"):
            values = profile.get(key, [])
            if not isinstance(values, list):
                continue
            for value in values:
                channel = str(value).strip()
                if channel and channel not in channels:
                    channels.append(channel)
        return channels
