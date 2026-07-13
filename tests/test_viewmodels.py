"""Framework-independent tests for the viewmodel layer.

These tests exercise the UI-independent viewmodels in
``test_data_analyser.viewmodels`` (and the supporting settings/session services).
They must not require a GUI.

Run with:

    python -m unittest discover -s tests
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from test_data_analyser.core.settings_manager import SettingsManager
from test_data_analyser.domain import PlotData
from test_data_analyser.services import dataset_service, plot_render_service, session_service
from test_data_analyser.services.results import OperationResult
import test_data_analyser.viewmodels.data_loading_vm as data_loading_module
import test_data_analyser.viewmodels.runs_comparison_vm as runs_comparison_module
from test_data_analyser.viewmodels import (
    AppState,
    AppStateController,
    CursorCompareViewModel,
    DataLoadingViewModel,
    EngineeringNotesViewModel,
    LimitsViewModel,
    MainWindowViewModel,
    MathsChannelsViewModel,
    PlotWorkspaceViewModel,
    RawDataViewModel,
    RunsComparisonViewModel,
    SettingsViewModel,
)


class _FakeSettings:
    """Minimal SettingsManager double for viewmodel tests."""

    def __init__(self, values: dict | None = None) -> None:
        self._values = values or {}
        self.saved = False

    def get(self, section: str, key: str):
        try:
            return self._values[section][key]
        except KeyError as exc:
            raise KeyError(f"{section}.{key}") from exc

    def set(self, section: str, key: str, value) -> None:
        if key.startswith("available_"):
            raise ValueError("read-only")
        self._values.setdefault(section, {})[key] = value

    def save(self) -> None:
        self.saved = True


def _sample_df() -> pd.DataFrame:
    return pd.DataFrame({"Time": [0.0, 1.0, 2.0, 3.0], "A": [10.0, 20.0, 30.0, 40.0], "B": [1.0, 2.0, 3.0, 4.0]})


class AppStateTests(unittest.TestCase):
    def test_derived_views(self) -> None:
        state = AppState(df=_sample_df(), plot_profiles=[{"name": "P1"}, {"name": "P2"}], active_plot_profile_index=1)
        self.assertTrue(state.has_data)
        self.assertEqual(state.column_names(), ["Time", "A", "B"])
        self.assertEqual(state.active_plot_profile()["name"], "P2")

    def test_active_profile_index_clamped(self) -> None:
        state = AppState(plot_profiles=[{"name": "P1"}], active_plot_profile_index=9)
        self.assertEqual(state.active_plot_profile()["name"], "P1")

    def test_active_run_none_when_out_of_range(self) -> None:
        state = AppState(runs=[{"name": "R1"}], active_run_index=-1)
        self.assertIsNone(state.active_run())

    def test_state_controller_restores_dataset_snapshot(self) -> None:
        state = AppState(df=_sample_df(), plot_profiles=[{"name": "P1"}], current_x_axis="Time")
        controller = AppStateController(state)
        snapshot = controller.capture_dataset_snapshot("edit")

        state.df = pd.DataFrame({"Other": [99.0]})
        state.plot_profiles = [{"name": "Changed"}]
        state.current_x_axis = "Other"
        state.is_dirty = True

        controller.restore_dataset_snapshot(snapshot)

        self.assertEqual(state.column_names(), ["Time", "A", "B"])
        self.assertEqual(state.plot_profiles[0]["name"], "P1")
        self.assertEqual(state.current_x_axis, "Time")
        self.assertFalse(state.is_dirty)

    def test_state_controller_applies_dataframe_payload_and_dirty_flag(self) -> None:
        state = AppState(df=_sample_df())
        controller = AppStateController(state)
        replacement = pd.DataFrame({"X": [1.0]})

        self.assertTrue(controller.apply_dataframe_payload({"df": replacement}))
        controller.mark_dirty()

        self.assertEqual(state.column_names(), ["X"])
        self.assertTrue(state.is_dirty)

    def test_state_controller_applies_plot_profile_updates(self) -> None:
        state = AppState(
            plot_profiles=[{"name": "Old"}],
            active_plot_profile_index=0,
            current_x_axis="Time",
            limit_lines=[{"name": "L"}],
            engineering_notes={"objective": "Old"},
        )
        controller = AppStateController(state)

        controller.reset_plot_workspace([{"name": "Plot 1"}], 0)
        controller.set_active_plot_profile(0, {"name": "Updated"})

        self.assertEqual(state.plot_profiles[0]["name"], "Updated")
        self.assertEqual(state.active_plot_profile_index, 0)
        self.assertEqual(state.current_x_axis, "")
        self.assertEqual(state.limit_lines, [])
        self.assertEqual(state.engineering_notes, {})

    def test_numeric_column_caches_until_invalidated(self) -> None:
        import test_data_analyser.viewmodels.app_state as app_state_module

        calls = {"n": 0}
        real = app_state_module.numeric_series

        def counting(series):
            calls["n"] += 1
            return real(series)

        app_state_module.numeric_series = counting
        try:
            state = AppState(df=_sample_df())
            first = state.numeric_column("A")
            second = state.numeric_column("A")
            self.assertIs(first, second)
            self.assertEqual(calls["n"], 1)  # coerced once, then served from cache
            state.invalidate_numeric_cache("A")
            state.numeric_column("A")
            self.assertEqual(calls["n"], 2)  # recomputed only after invalidation
        finally:
            app_state_module.numeric_series = real

    def test_numeric_column_cache_resets_when_dataframe_replaced(self) -> None:
        state = AppState(df=_sample_df())
        cached = state.numeric_column("A")
        state.df = pd.DataFrame({"A": [100.0, 200.0]})
        refreshed = state.numeric_column("A")
        self.assertEqual(list(refreshed), [100.0, 200.0])
        self.assertIsNot(refreshed, cached)

    def test_numeric_column_missing_returns_empty(self) -> None:
        state = AppState(df=_sample_df())
        self.assertTrue(state.numeric_column("Nope").empty)

    def test_raw_data_edit_refreshes_numeric_cache(self) -> None:
        state = AppState(df=_sample_df())
        state.channel_registry = dataset_service.build_registry_for_dataframe(state.df)
        self.assertEqual(list(state.numeric_column("A")), [10.0, 20.0, 30.0, 40.0])
        raw_vm = RawDataViewModel(state)
        result = raw_vm.apply_edit(0, "A", 99.0)
        self.assertTrue(result.ok)
        self.assertEqual(state.numeric_column("A").iloc[0], 99.0)


class DataLoadingViewModelTests(unittest.TestCase):
    def test_load_csv_updates_state(self) -> None:
        state = AppState()
        vm = DataLoadingViewModel(state)
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "data.csv"
            csv_path.write_text("Time,Sig\n0,10\n1,20\n2,30\n", encoding="utf-8")
            result = vm.load_file(csv_path)
        self.assertTrue(result.ok)
        self.assertEqual(result.payload, ["Time", "Sig"])
        self.assertIsNotNone(state.df)
        self.assertEqual(state.root_file_directory, str(csv_path.resolve().parent))
        self.assertTrue(state.is_dirty)
        self.assertEqual(state.sheet_name, "")

    def test_missing_file_fails(self) -> None:
        vm = DataLoadingViewModel(AppState())
        result = vm.load_file("does-not-exist.csv")
        self.assertFalse(result.ok)

    def test_get_sheets_empty_for_csv(self) -> None:
        vm = DataLoadingViewModel(AppState())
        with tempfile.TemporaryDirectory() as tmp:
            csv_path = Path(tmp) / "data.csv"
            csv_path.write_text("a,b\n1,2\n", encoding="utf-8")
            self.assertEqual(vm.get_sheets(csv_path), [])

    def test_get_sheets_returns_xlsx_sheet_names(self) -> None:
        vm = DataLoadingViewModel(AppState())
        with tempfile.TemporaryDirectory() as tmp:
            xlsx_path = Path(tmp) / "data.xlsx"
            with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
                pd.DataFrame({"A": [1]}).to_excel(writer, sheet_name="First", index=False)
                pd.DataFrame({"B": [2]}).to_excel(writer, sheet_name="Second", index=False)

            self.assertEqual(vm.get_sheets(xlsx_path), ["First", "Second"])

    def test_suggested_x_column(self) -> None:
        vm = DataLoadingViewModel(AppState())
        self.assertEqual(vm.suggested_x_column(["Elapsed Time", "Pressure"]), "Elapsed Time")
        self.assertEqual(vm.suggested_x_column(["Pressure", "Flow"]), "Pressure")
        self.assertEqual(vm.suggested_x_column([]), "")


class SettingsViewModelTests(unittest.TestCase):
    def test_get_with_default(self) -> None:
        vm = SettingsViewModel(_FakeSettings({"general_ui": {"theme": "dark"}}))
        self.assertEqual(vm.get("general_ui", "theme", "light"), "dark")
        self.assertEqual(vm.get("missing", "key", "fallback"), "fallback")

    def test_theme_helpers(self) -> None:
        vm = SettingsViewModel(_FakeSettings({"general_ui": {"theme": "dark"}}))
        self.assertTrue(vm.is_dark_theme())
        self.assertEqual(vm.theme_name(), "dark")
        self.assertIn("bg", vm.palette())

    def test_set_and_save(self) -> None:
        manager = _FakeSettings()
        vm = SettingsViewModel(manager)
        self.assertTrue(vm.set("general_ui", "theme", "dark").ok)
        self.assertFalse(vm.set("general_ui", "available_themes", []).ok)
        self.assertTrue(vm.save().ok)
        self.assertTrue(manager.saved)

    def test_no_manager_fails_gracefully(self) -> None:
        vm = SettingsViewModel(None)
        self.assertEqual(vm.get("general_ui", "theme", "light"), "light")
        self.assertFalse(vm.set("general_ui", "theme", "dark").ok)
        self.assertFalse(vm.save().ok)


class SettingsManagerPathTests(unittest.TestCase):
    def test_default_settings_path_uses_config_folder(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = SettingsManager.default_settings_path(Path(directory))

        self.assertEqual(path, Path(directory) / "config" / "settings.json")

    def test_default_settings_path_migrates_legacy_root_settings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            legacy_path = root / "settings.json"
            legacy_path.write_text('{"general_ui": {"theme": "dark"}}', encoding="utf-8")

            path = SettingsManager.default_settings_path(root)
            manager = SettingsManager(path)

            self.assertEqual(path, root / "config" / "settings.json")
            self.assertFalse(legacy_path.exists())
            self.assertTrue(path.exists())
            self.assertEqual(manager.get("general_ui", "theme"), "dark")


class PlotWorkspaceViewModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = AppState(df=_sample_df())
        self.vm = PlotWorkspaceViewModel(self.state)

    def test_prepare_plot_data_and_ranges(self) -> None:
        data = self.vm.prepare_plot_data("Time", ["A", "B"])
        x_range, y_range = self.vm.selected_ranges(data, secondary_y={"B"})
        self.assertEqual(x_range, (0.0, 3.0))
        self.assertEqual(y_range, (10.0, 40.0))

    def test_prepare_plot_data_window(self) -> None:
        data = self.vm.prepare_plot_data("Time", ["A"], xmin=1.0, xmax=2.0)
        self.assertEqual(list(data.y_map["A"].dropna()), [20.0, 30.0])

    def test_prepare_requires_selection(self) -> None:
        with self.assertRaises(ValueError):
            self.vm.prepare_plot_data("Time", [])
        with self.assertRaises(ValueError):
            self.vm.prepare_plot_data("", ["A"])

    def test_statistics(self) -> None:
        stats = self.vm.statistics(["A"])
        self.assertEqual(stats.loc["A"]["Count"], 4)
        self.assertEqual(stats.loc["A"]["Mean"], 25.0)


class LimitsViewModelTests(unittest.TestCase):
    def test_margin_summary_pass(self) -> None:
        data = PlotData(x=pd.Series([0.0, 1.0, 2.0]), y_map={"A": pd.Series([1.0, 2.0, 3.0])}, x_map=None)
        lines = [{"name": "Max", "type": "Upper Limit", "points": [{"x": 0, "y": 10}, {"x": 2, "y": 10}]}]
        summary = LimitsViewModel().margin_summary(data, lines)
        self.assertTrue(summary.any_result)
        self.assertEqual(summary.rows[0].status, "PASS")

    def test_active_ranges(self) -> None:
        lines = [{"name": "L", "points": [{"x": 0, "y": 1}, {"x": 5, "y": 9}]}]
        x_range, y_range = LimitsViewModel().active_ranges(lines, selected_y=set())
        self.assertEqual(x_range, (0.0, 5.0))
        self.assertEqual(y_range, (1.0, 9.0))


class LimitsViewModelCrudTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = AppState(df=_sample_df())
        self.vm = LimitsViewModel(self.state)

    def test_add_and_active_line(self) -> None:
        result = self.vm.add_line()
        self.assertTrue(result.ok)
        self.assertEqual(len(self.state.limit_lines), 1)
        self.assertEqual(self.vm.active_line()["name"], "Limit 1")

    def test_duplicate_line(self) -> None:
        self.vm.add_line()
        self.vm.update_active_metadata(
            name="Max", limit_type="Upper Limit", applies_to="All selected Y channels", colour="#005A8C"
        )
        self.vm.duplicate_line()
        self.assertEqual(len(self.state.limit_lines), 2)
        self.assertEqual(self.vm.active_line()["name"], "Max Copy")

    def test_delete_line(self) -> None:
        self.vm.add_line()
        self.vm.add_line()
        self.vm.delete_line()
        self.assertEqual(len(self.state.limit_lines), 1)

    def test_add_point_sorts_and_counts(self) -> None:
        self.vm.add_line()
        self.assertTrue(self.vm.add_point("5", "10").ok)
        self.assertTrue(self.vm.add_point("1", "2").ok)
        points = self.vm.active_points()
        self.assertEqual([p["x"] for p in points], [1.0, 5.0])

    def test_add_point_rejects_non_numeric(self) -> None:
        self.vm.add_line()
        self.assertFalse(self.vm.add_point("abc", "2").ok)

    def test_update_and_delete_point(self) -> None:
        self.vm.add_line()
        self.vm.add_point("1", "2")
        self.assertTrue(self.vm.update_point(0, "1", "99").ok)
        self.assertEqual(self.vm.active_points()[0]["y"], 99.0)
        self.assertTrue(self.vm.delete_point(0).ok)
        self.assertEqual(self.vm.active_points(), [])

    def test_preset_for_colour(self) -> None:
        self.assertEqual(self.vm.preset_for_colour("#007AC2"), "Eaton Blue")
        self.assertEqual(self.vm.preset_for_colour("#123456"), "Custom")

    def test_applies_options(self) -> None:
        self.assertEqual(
            self.vm.applies_options(["B", "A10", "A2"]),
            ["All selected Y channels", "A2", "A10", "B"],
        )


class RawDataViewModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = AppState(df=_sample_df())
        self.vm = RawDataViewModel(self.state)

    def test_parse_row_limit(self) -> None:
        self.assertIsNone(self.vm.parse_row_limit("All").payload)
        self.assertEqual(self.vm.parse_row_limit("10").payload, 10)
        self.assertFalse(self.vm.parse_row_limit("bad").ok)

    def test_apply_edit_marks_dirty(self) -> None:
        self.assertFalse(self.state.is_dirty)
        result = self.vm.apply_edit(0, "A", 99.0)
        self.assertTrue(result.ok)
        self.assertTrue(self.state.is_dirty)

    def test_select_frame(self) -> None:
        frame, removed = self.vm.select_frame(
            "Time", ["A"], apply_window=True, xmin=1.0, xmax=2.0, drop_blank=False
        )
        self.assertEqual(list(frame["Time"]), [1.0, 2.0])
        self.assertEqual(removed, 0)

    def test_select_frame_sorts_selected_y_columns_naturally(self) -> None:
        self.state.df["TC10"] = [10.0, 20.0, 30.0, 40.0]
        self.state.df["TC2"] = [2.0, 3.0, 4.0, 5.0]

        frame, _removed = self.vm.select_frame(
            "Time", ["TC10", "B", "TC2"], apply_window=False, xmin=None, xmax=None, drop_blank=False
        )

        self.assertEqual(list(frame.columns), ["Time", "B", "TC2", "TC10"])

    def test_display_frame_applies_sort(self) -> None:
        result = self.vm.display_frame(
            "Time", ["A"], row_limit_text="All", apply_window=False,
            xmin=None, xmax=None, drop_blank=False,
            sort_column="A", sort_ascending=False,
        )
        self.assertTrue(result.ok)
        self.assertEqual(list(result.payload["frame"]["A"]), [40.0, 30.0, 20.0, 10.0])

    def test_display_frame_applies_column_filter(self) -> None:
        result = self.vm.display_frame(
            "Time", ["A"], row_limit_text="All", apply_window=False,
            xmin=None, xmax=None, drop_blank=False,
            column_filters={"A": ">20"},
        )
        self.assertTrue(result.ok)
        self.assertEqual(list(result.payload["frame"]["A"]), [30.0, 40.0])

    def test_display_frame_sorted_edit_maps_to_source_row(self) -> None:
        result = self.vm.display_frame(
            "Time", ["A"], row_limit_text="All", apply_window=False,
            xmin=None, xmax=None, drop_blank=False,
            sort_column="A", sort_ascending=False,
        )
        frame = result.payload["frame"]
        top_index = frame.index[0]
        self.assertEqual(top_index, 3)
        self.vm.apply_edit(top_index, "A", 999.0)
        self.assertEqual(self.state.df.at[3, "A"], 999.0)

    def test_coerce_edit_value(self) -> None:
        self.assertEqual(self.vm.coerce_edit_value("A", "99").payload, 99.0)
        self.assertFalse(self.vm.coerce_edit_value("A", "abc").ok)

    def test_apply_edit_and_undo(self) -> None:
        self.assertFalse(self.vm.can_undo)
        result = self.vm.apply_edit(1, "A", 999.0)
        self.assertTrue(result.ok)
        self.assertEqual(result.payload, 20.0)
        self.assertEqual(self.state.df.at[1, "A"], 999.0)
        self.assertTrue(self.vm.can_undo)

        undo = self.vm.undo_last_edit()
        self.assertTrue(undo.ok)
        self.assertEqual(self.state.df.at[1, "A"], 20.0)
        self.assertFalse(self.vm.can_undo)

    def test_apply_edit_rejects_unchanged_value(self) -> None:
        self.assertFalse(self.vm.apply_edit(0, "A", 10.0).ok)
        self.assertFalse(self.vm.can_undo)

    def test_undo_without_edits(self) -> None:
        result = self.vm.undo_last_edit()
        self.assertFalse(result.ok)
        self.assertEqual(result.message, "Nothing to undo")

    def test_export_selected_frame_csv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "selected.csv"
            result = self.vm.export_selected_frame(
                target, "Time", ["A"], apply_window=False, xmin=None, xmax=None, drop_blank=False
            )
            self.assertTrue(result.ok)
            self.assertTrue(target.exists())
            exported = pd.read_csv(target)
            self.assertEqual(list(exported.columns), ["Time", "A"])
            self.assertEqual(len(exported), 4)

    def test_export_selected_frame_xlsx(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "selected.xlsx"
            result = self.vm.export_selected_frame(
                target, "Time", ["A"], apply_window=False, xmin=None, xmax=None, drop_blank=False
            )
            self.assertTrue(result.ok)
            self.assertTrue(target.exists())
            exported = pd.read_excel(target, engine="openpyxl")
            self.assertEqual(list(exported.columns), ["Time", "A"])
            self.assertEqual(len(exported), 4)

    def test_export_without_selection_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "selected.csv"
            result = self.vm.export_selected_frame(
                target, "", [], apply_window=False, xmin=None, xmax=None, drop_blank=False
            )
            self.assertFalse(result.ok)
            self.assertFalse(target.exists())



class MathsChannelsViewModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = AppState(df=_sample_df())
        self.vm = MathsChannelsViewModel(self.state)

    def test_validate_formula(self) -> None:
        result = self.vm.validate_formula("A + B")
        self.assertTrue(result.ok)
        self.assertEqual(result.payload["numeric"], 4)

    def test_validate_invalid(self) -> None:
        self.assertFalse(self.vm.validate_formula("Missing + 1").ok)

    def test_apply_channel_creates_column(self) -> None:
        result = self.vm.apply_channel("Sum", "A + B")
        self.assertTrue(result.ok)
        self.assertIn("Sum", self.state.df.columns)
        self.assertIn("Sum", self.state.calculated_channels)
        self.assertCountEqual(result.payload["created_from_columns"], ["A", "B"])

    def test_apply_and_delete_channel_mark_dirty(self) -> None:
        self.assertFalse(self.state.is_dirty)
        self.assertTrue(self.vm.apply_channel("Sum", "A + B").ok)
        self.assertTrue(self.state.is_dirty)
        self.state.is_dirty = False
        self.assertTrue(self.vm.delete_channel("Sum").ok)
        self.assertTrue(self.state.is_dirty)

    def test_channel_names_are_naturally_sorted(self) -> None:
        self.vm.apply_channel("TC10", "A + B")
        self.vm.apply_channel("TC2", "A + B")
        self.vm.apply_channel("Calc", "A + B")

        self.assertEqual(self.vm.channel_names(), ["Calc", "TC2", "TC10"])

    def test_apply_channel_rename_removes_old(self) -> None:
        self.vm.apply_channel("Old", "A + B")
        result = self.vm.apply_channel("New", "A - B", selected_name="Old")
        self.assertTrue(result.ok)
        self.assertNotIn("Old", self.state.df.columns)
        self.assertNotIn("Old", self.state.calculated_channels)
        self.assertIn("New", self.state.df.columns)

    def test_apply_channel_blocks_source_column_name(self) -> None:
        self.assertFalse(self.vm.apply_channel("A", "B + 1").ok)

    def test_recalculate_reports_errors(self) -> None:
        self.vm.apply_channel("Good", "A + B")
        self.state.calculated_channels["Bad"] = {
            "name": "Bad",
            "formula": "Missing + 1",
            "description": "",
            "enabled": True,
            "created_from_columns": [],
        }
        result = self.vm.recalculate()
        self.assertFalse(result.ok)
        self.assertEqual(len(result.payload["errors"]), 1)
        self.assertNotIn("Bad", self.state.df.columns)
        self.assertIn("Good", self.state.df.columns)

    def test_disabled_channel_column_removed(self) -> None:
        self.vm.apply_channel("Calc", "A + B")
        self.state.calculated_channels["Calc"]["enabled"] = False
        result = self.vm.recalculate()
        self.assertTrue(result.ok)
        self.assertNotIn("Calc", self.state.df.columns)
        self.assertIn("Calc", self.state.calculated_channels)

    def test_delete_channel(self) -> None:
        self.vm.apply_channel("Calc", "A + B")
        result = self.vm.delete_channel("Calc")
        self.assertTrue(result.ok)
        self.assertNotIn("Calc", self.state.df.columns)
        self.assertFalse(self.vm.delete_channel("Nonexistent").ok)


class RunsComparisonViewModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = AppState()
        self.vm = RunsComparisonViewModel(self.state)
        self.state.runs = [
            self.vm.make_run_entry("Run 1", "r1.csv", "", pd.DataFrame({"Time": [0.0, 10.0], "A": [1.0, 2.0]}), enabled=True),
            self.vm.make_run_entry("Run 2", "r2.csv", "", pd.DataFrame({"Time": [5.0, 20.0], "A": [3.0, 4.0]}), enabled=False),
        ]

    def test_enabled_runs(self) -> None:
        self.assertEqual([run["name"] for run in self.vm.enabled_runs()], ["Run 1"])

    def test_make_run_entry_assigns_colour(self) -> None:
        entry = self.vm.make_run_entry("Run 3", "r3.csv", "Sheet1", pd.DataFrame({"A": [1.0]}))
        self.assertTrue(entry["colour"].startswith("#"))
        self.assertEqual(entry["sheet_name"], "Sheet1")

    def test_common_x_range(self) -> None:
        for run in self.state.runs:
            run["enabled"] = True
        self.assertEqual(self.vm.common_x_range("Time"), (5.0, 10.0))

    def test_comparison_statistics(self) -> None:
        rows = self.vm.comparison_statistics(["A"])
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["run"], "Run 1")
        self.assertEqual(rows[0]["Count"], 2)

    def test_comparison_statistics_sort_channels_naturally(self) -> None:
        run = self.state.runs[0]
        run["df"] = pd.DataFrame({"Time": [0.0, 1.0], "TC10": [10.0, 11.0], "TC2": [2.0, 3.0]})

        rows = self.vm.comparison_statistics(["TC10", "TC2"])

        self.assertEqual([row["channel"] for row in rows], ["TC2", "TC10"])

    def test_serialise_runs_drops_dataframe(self) -> None:
        serialised = self.vm.serialise_runs()
        self.assertEqual(serialised[0]["name"], "Run 1")
        self.assertNotIn("df", serialised[0])


class RunsComparisonViewModelCrudTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = AppState()
        self.vm = RunsComparisonViewModel(self.state)
        self.state.runs = [
            self.vm.make_run_entry("Run 1", "r1.csv", "", pd.DataFrame({"Time": [0.0, 10.0], "A": [1.0, 2.0]}), enabled=True),
            self.vm.make_run_entry("Run 2", "r2.csv", "", pd.DataFrame({"Time": [5.0, 20.0], "A": [3.0, 4.0]}), enabled=True),
        ]
        self.state.active_run_index = 0

    def test_remove_run_adjusts_active(self) -> None:
        self.vm.set_active(1)
        result = self.vm.remove_run(1)
        self.assertTrue(result.ok)
        self.assertEqual(len(self.state.runs), 1)
        self.assertEqual(self.state.active_run_index, 0)

    def test_duplicate_run(self) -> None:
        result = self.vm.duplicate_run(0)
        self.assertTrue(result.ok)
        self.assertEqual(len(self.state.runs), 3)
        self.assertEqual(self.state.runs[-1]["name"], "Run 1 Copy")

    def test_rename_run(self) -> None:
        self.assertTrue(self.vm.rename_run(0, "Baseline").ok)
        self.assertEqual(self.state.runs[0]["name"], "Baseline")
        self.assertFalse(self.vm.rename_run(0, "   ").ok)

    def test_toggle_enabled(self) -> None:
        self.vm.toggle_enabled(1)
        self.assertFalse(self.state.runs[1]["enabled"])

    def test_run_rows(self) -> None:
        rows = self.vm.run_rows()
        self.assertEqual(rows[0]["Name"], "Run 1")
        self.assertEqual(rows[0]["Active"], "Yes")
        self.assertEqual(rows[0]["Rows"], "2")

    def test_comparison_plot_items(self) -> None:
        items, skipped = self.vm.comparison_plot_items("Time", ["A"], use_common_x=False, prefix_legend=True)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["label"], "Run 1 | A")
        self.assertEqual(list(items[0]["y"]), [1.0, 2.0])

    def test_comparison_settings_roundtrip(self) -> None:
        self.vm.set_setting("comparison_common_x_range", True)
        self.assertTrue(self.vm.get_setting("comparison_common_x_range"))

    def test_run_mutations_mark_dirty(self) -> None:
        self.state.is_dirty = False
        self.assertTrue(self.vm.rename_run(0, "Baseline").ok)
        self.assertTrue(self.state.is_dirty)
        self.state.is_dirty = False
        self.assertTrue(self.vm.toggle_enabled(1).ok)
        self.assertTrue(self.state.is_dirty)
        self.state.is_dirty = False
        self.vm.set_setting("comparison_common_x_range", True)
        self.assertTrue(self.state.is_dirty)
        self.state.is_dirty = False
        self.assertTrue(self.vm.remove_run(1).ok)
        self.assertTrue(self.state.is_dirty)


class CursorCompareViewModelTests(unittest.TestCase):
    def _data(self) -> PlotData:
        return PlotData(
            x=pd.Series([0.0, 1.0, 2.0, 3.0]),
            y_map={"A": pd.Series([10.0, 20.0, 30.0, 40.0])},
            x_map=None,
        )

    def test_lock_and_frame(self) -> None:
        vm = CursorCompareViewModel()
        vm.set_data(self._data())
        self.assertTrue(vm.has_data)
        self.assertTrue(vm.lock_at(0.1))
        self.assertTrue(vm.lock_at(2.1))
        frame = vm.comparison_frame(decimals=1)
        self.assertEqual(len(frame), 3)  # 2 points + delta
        self.assertEqual(list(vm.points[0]["values"].keys()), ["A"])

    def test_lock_without_data(self) -> None:
        vm = CursorCompareViewModel()
        self.assertFalse(vm.lock_at(1.0))

    def test_analysis_window_from_points(self) -> None:
        vm = CursorCompareViewModel()
        vm.set_data(self._data())
        vm.lock_at(3.0)
        vm.lock_at(1.0)
        self.assertEqual(vm.analysis_window_from_points(), (1.0, 3.0))

    def test_set_data_none_clears(self) -> None:
        vm = CursorCompareViewModel()
        vm.set_data(self._data())
        vm.lock_at(1.0)
        vm.set_data(None)
        self.assertFalse(vm.has_data)
        self.assertEqual(vm.points, [])


class EngineeringNotesViewModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = AppState()
        self.vm = EngineeringNotesViewModel(self.state)

    def test_field_definitions_keys(self) -> None:
        keys = self.vm.field_keys()
        self.assertIn("objective", keys)
        self.assertIn("report_summary", keys)
        self.assertEqual(len(self.vm.field_definitions()), 9)

    def test_update_and_get_field(self) -> None:
        self.vm.update_field("observations", "Peak at 2 s.")
        self.assertEqual(self.vm.get_notes()["observations"], "Peak at 2 s.")

    def test_report_text_includes_filled_fields(self) -> None:
        self.vm.update_field("objective", "Verify response.")
        report = self.vm.report_text(file_name="data.csv", x_axis="Time", y_axis="A")
        self.assertIn("TEST OBJECTIVE / PURPOSE", report)
        self.assertIn("Verify response.", report)
        self.assertIn("data.csv", report)

    def test_report_text_empty(self) -> None:
        self.assertIn("No engineering notes", self.vm.report_text())

    def test_clear_resets_fields(self) -> None:
        self.vm.update_field("actions", "Retest.")
        self.vm.clear()
        self.assertEqual(self.vm.get_notes()["actions"], "")

    def test_set_notes_from_legacy_string(self) -> None:
        self.vm.set_notes("freeform text")
        self.assertEqual(self.vm.get_notes()["observations"], "freeform text")


class RecentItemsTests(unittest.TestCase):
    def _vm(self) -> MainWindowViewModel:
        return MainWindowViewModel(_FakeSettings())

    def _paths(self, count: int) -> list[str]:
        directory = Path(tempfile.mkdtemp())
        return [str(directory / f"file{index}.csv") for index in range(count)]

    def test_recent_files_cap_and_order(self) -> None:
        vm = self._vm()
        paths = self._paths(12)
        for path in paths:
            vm.register_recent_file(path)

        recent = vm.recent_files()
        self.assertEqual(len(recent), 10)
        self.assertEqual(recent[0], str(Path(paths[11]).resolve()))
        self.assertEqual(recent[-1], str(Path(paths[2]).resolve()))
        self.assertNotIn(str(Path(paths[0]).resolve()), recent)
        self.assertNotIn(str(Path(paths[1]).resolve()), recent)

    def test_registering_existing_entry_moves_to_front(self) -> None:
        vm = self._vm()
        first, second, third = self._paths(3)
        for path in (first, second, third):
            vm.register_recent_file(path)

        vm.register_recent_file(first)

        recent = vm.recent_files()
        self.assertEqual(len(recent), 3)
        self.assertEqual(recent[0], str(Path(first).resolve()))
        self.assertEqual(recent.count(str(Path(first).resolve())), 1)

    def test_register_recent_persists_via_settings_save(self) -> None:
        manager = _FakeSettings()
        vm = MainWindowViewModel(manager)
        vm.register_recent_file(self._paths(1)[0])
        self.assertTrue(manager.saved)

    def test_files_and_sessions_tracked_separately(self) -> None:
        vm = self._vm()
        directory = Path(tempfile.mkdtemp())
        vm.register_recent_session(str(directory / "session.json"))
        self.assertEqual(len(vm.recent_sessions()), 1)
        self.assertEqual(vm.recent_files(), [])

    def test_recent_lists_empty_without_settings_manager(self) -> None:
        vm = MainWindowViewModel()
        self.assertEqual(vm.recent_files(), [])
        self.assertEqual(vm.register_recent_file("anything.csv"), [])


class AutoSaveSchedulingTests(unittest.TestCase):
    def test_auto_save_due_respects_interval(self) -> None:
        vm = MainWindowViewModel()
        self.assertTrue(vm.auto_save_due(None, 1000.0, 10))
        self.assertFalse(vm.auto_save_due(1000.0, 1000.0 + 5 * 60, 10))
        self.assertTrue(vm.auto_save_due(1000.0, 1000.0 + 10 * 60, 10))

    def test_auto_save_due_disabled_for_non_positive_interval(self) -> None:
        vm = MainWindowViewModel()
        self.assertFalse(vm.auto_save_due(None, 1000.0, 0))
        self.assertFalse(vm.auto_save_due(1000.0, 1_000_000.0, -5))

    def test_auto_save_target_prefers_session_path(self) -> None:
        vm = MainWindowViewModel()
        self.assertEqual(vm.auto_save_target_path("session.json"), "session.json")

    def test_auto_save_target_falls_back_to_autosave_json(self) -> None:
        vm = MainWindowViewModel()
        vm.state.root_file_directory = str(Path(tempfile.mkdtemp()))
        target = vm.auto_save_target_path(None)
        self.assertTrue(target.endswith("autosave.json"))
        self.assertTrue(target.startswith(vm.state.root_file_directory))


class MainWindowViewModelTests(unittest.TestCase):
    def _populated_vm(self) -> MainWindowViewModel:
        vm = MainWindowViewModel()
        vm.state.df = _sample_df()
        vm.state.filepath = Path("source.csv")
        vm.state.sheet_name = "Sheet1"
        vm.state.plot_profiles = [{"name": "Plot 1", "x_column": "Time", "y_columns": ["A"]}]
        vm.state.calculated_channels = {
            "Sum": {"name": "Sum", "formula": "A + B", "description": "", "enabled": True, "created_from_columns": ["A", "B"]}
        }
        return vm

    def test_build_session_keys(self) -> None:
        session = self._populated_vm().build_session()
        self.assertIn("root_file_directory", session)
        self.assertEqual(session["file_path"], "source.csv")
        self.assertEqual(session["sheet_name"], "Sheet1")
        self.assertIn("Sum", session["calculated_channels"])
        self.assertEqual(session["plot_profiles"][0]["x_column"], "Time")

    def test_capture_working_state_updates_active_profile_only(self) -> None:
        vm = MainWindowViewModel()
        vm.state.plot_profiles = [
            {"name": "Plot 1", "x_column": "Time", "y_columns": ["A"]},
            {"name": "Plot 2", "x_column": "Time", "y_columns": ["B"]},
        ]
        vm.state.active_plot_profile_index = 1
        vm.capture_working_state(
            x_column="Time",
            y_columns=["B"],
            secondary_y_columns=[],
            title="Second Plot",
            x_label="Seconds",
            y_label="Current",
        )

        self.assertEqual(len(vm.state.plot_profiles), 2)
        self.assertEqual(vm.state.active_plot_profile_index, 1)
        self.assertEqual(vm.state.plot_profiles[0]["y_columns"], ["A"])
        self.assertEqual(vm.state.plot_profiles[1]["title"], "Second Plot")
        self.assertEqual(vm.state.plot_profiles[1]["y_label"], "Current")

    def test_capture_working_state_persists_active_profile_annotations(self) -> None:
        vm = MainWindowViewModel()
        annotation = {"id": "ann_001", "type": "text", "text": "Pressure dip", "x": 1.0, "y": 2.0}

        vm.capture_working_state(x_column="Time", y_columns=["A"], annotations=[annotation])

        self.assertEqual(vm.state.plot_profiles[0]["annotations"][0]["text"], "Pressure dip")

        vm.capture_working_state(x_column="Time", y_columns=["A"], annotations=[])

        self.assertEqual(vm.state.plot_profiles[0]["annotations"], [])

    def test_new_plot_profile_uses_current_x_axis_or_default(self) -> None:
        vm = MainWindowViewModel()
        vm.state.df = pd.DataFrame({"Time": [0.0, 1.0], "Flow": [5.0, 6.0], "A": [1.0, 2.0]})

        vm.capture_working_state(x_column="Flow", y_columns=["A"])
        result = vm.add_plot_profile()

        self.assertTrue(result.ok, result.message)
        self.assertEqual(vm.state.plot_profiles[1]["x_column"], "Flow")

        vm.state.current_x_axis = "Removed Channel"
        result = vm.add_plot_profile()

        self.assertTrue(result.ok, result.message)
        self.assertEqual(vm.state.plot_profiles[2]["x_column"], "Time")

    def test_persistent_plot_channel_colours_use_active_selection_for_repeats(self) -> None:
        vm = MainWindowViewModel()
        vm.state.plot_profiles = [
            {
                "name": "Plot 1",
                "x_column": "Time",
                "y_columns": ["Motor Voltage", "Motor Current"],
                "generated": True,
            },
            {
                "name": "Plot 2",
                "x_column": "Time",
                "y_columns": ["Stale Channel"],
                "generated": True,
            },
        ]
        vm.state.active_plot_profile_index = 1

        mapping = vm.persistent_plot_channel_colours([" motor voltage "], ["Flow Rate"])

        self.assertIn(plot_render_service.normalise_channel_name("Motor Voltage"), mapping)
        self.assertNotIn(plot_render_service.normalise_channel_name("Motor Current"), mapping)
        self.assertNotIn(plot_render_service.normalise_channel_name("Stale Channel"), mapping)
        self.assertNotIn(plot_render_service.normalise_channel_name("Flow Rate"), mapping)

    def test_legend_colour_override_carries_across_matching_plot_profiles(self) -> None:
        vm = MainWindowViewModel()
        vm.state.plot_profiles = [
            {"name": "Plot 1", "x_column": "Time", "y_columns": ["Motor Voltage"], "generated": True},
            {"name": "Plot 2", "x_column": "Time", "y_columns": [" motor voltage "], "generated": True},
        ]
        vm.state.active_plot_profile_index = 0

        result = vm.update_active_legend_channel_override(
            "Motor Voltage",
            {"label": "Voltage", "colour": "#123456", "plot_kind": "Scatter"},
        )

        self.assertTrue(result.ok, result.message)
        key = plot_render_service.normalise_channel_name("Motor Voltage")
        self.assertEqual(vm.state.plot_profiles[0]["legend"]["channel_overrides"][key]["label"], "Voltage")
        self.assertEqual(vm.state.plot_profiles[0]["legend"]["channel_overrides"][key]["plot_kind"], "Scatter")
        self.assertEqual(vm.state.plot_profiles[1]["legend"]["channel_overrides"][key]["colour"], "#123456")

        vm.state.active_plot_profile_index = 1
        mapping = vm.persistent_plot_channel_colours(["Motor Voltage"], [])
        self.assertEqual(mapping[key], "#123456")

    def test_capture_working_state_preserves_legend_channel_overrides(self) -> None:
        vm = MainWindowViewModel()
        key = plot_render_service.normalise_channel_name("A")
        vm.state.plot_profiles = [
            {
                "name": "Plot 1",
                "legend": {"display_mode": "panel", "channel_overrides": {key: {"channel": "A", "colour": "#123456"}}},
            }
        ]

        vm.capture_working_state(x_column="Time", y_columns=["A"], legend_settings={"display_mode": "graph"})

        self.assertEqual(vm.state.plot_profiles[0]["legend"]["display_mode"], "graph")
        self.assertEqual(vm.state.plot_profiles[0]["legend"]["channel_overrides"][key]["colour"], "#123456")

    def test_legend_hidden_override_preserves_existing_style(self) -> None:
        vm = MainWindowViewModel()
        key = plot_render_service.normalise_channel_name("Motor Voltage")
        vm.state.plot_profiles = [
            {
                "name": "Plot 1",
                "x_column": "Time",
                "y_columns": ["Motor Voltage"],
                "legend": {
                    "channel_overrides": {
                        key: {"channel": "Motor Voltage", "colour": "#123456", "line_style": "--"}
                    }
                },
            }
        ]

        result = vm.update_active_legend_channel_override("Motor Voltage", {"hidden": True})

        self.assertTrue(result.ok, result.message)
        style = vm.state.plot_profiles[0]["legend"]["channel_overrides"][key]
        self.assertEqual(style["colour"], "#123456")
        self.assertEqual(style["line_style"], "--")
        self.assertEqual(style["hidden"], "true")

    def test_plot_selection_preserves_appearance_for_similar_channels_only(self) -> None:
        vm = MainWindowViewModel()
        vm.state.df = pd.DataFrame(
            {
                "Time": [0.0, 1.0, 2.0, 3.0],
                "Motor Pressure 1": [10.0, 20.0, 30.0, 40.0],
                "Motor Pressure 2": [11.0, 21.0, 31.0, 41.0],
                "High Pressure": [1000.0, 1200.0, 1400.0, 1600.0],
            }
        )
        previous = {
            "x_column": "Time",
            "primary_y": ["Motor Pressure 1"],
            "secondary_y": [],
            "xmin": None,
            "xmax": None,
            "use_filter": False,
            "cutoff": None,
            "order": 4,
        }
        similar = {**previous, "primary_y": ["Motor Pressure 1", "Motor Pressure 2"]}
        different = {**previous, "primary_y": ["High Pressure"]}

        self.assertTrue(vm.plot_selection_preserves_appearance(previous, similar))
        self.assertFalse(vm.plot_selection_preserves_appearance(previous, different))

    def test_plot_profile_crud_keeps_valid_active_profile(self) -> None:
        vm = MainWindowViewModel()
        vm.ensure_plot_profiles()
        add = vm.add_plot_profile()
        self.assertTrue(add.ok)
        self.assertEqual(len(vm.state.plot_profiles), 2)
        self.assertEqual(vm.state.active_plot_profile_index, 1)

        duplicate = vm.duplicate_plot_profile(0)
        self.assertTrue(duplicate.ok)
        self.assertEqual(vm.state.active_plot_profile_index, 1)
        self.assertEqual(vm.state.plot_profiles[1]["name"], "Plot 1 Copy")

        rename = vm.rename_plot_profile(1, "Renamed Plot")
        self.assertTrue(rename.ok)
        self.assertEqual(vm.state.plot_profiles[1]["name"], "Renamed Plot")
        self.assertFalse(vm.rename_plot_profile(1, "Plot 1").ok)

        delete = vm.delete_plot_profile(1)
        self.assertTrue(delete.ok)
        self.assertEqual(len(vm.state.plot_profiles), 2)
        self.assertEqual(vm.state.active_plot_profile_index, 1)

        self.assertTrue(vm.delete_plot_profile(1).ok)
        self.assertFalse(vm.delete_plot_profile(0).ok)
        self.assertEqual(len(vm.state.plot_profiles), 1)

    def test_save_and_load_round_trip(self) -> None:
        source = self._populated_vm()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.json"
            save_result = source.save_session(path)
            self.assertTrue(save_result.ok)

            target = MainWindowViewModel()
            load_result = target.load_session(path)
            self.assertTrue(load_result.ok)
            self.assertEqual(target.state.plot_profiles[0]["x_column"], "Time")
            self.assertIn("Sum", target.state.calculated_channels)

    def test_save_and_load_preserves_multiple_plot_profiles(self) -> None:
        source = self._populated_vm()
        source.state.plot_profiles = [
            {"name": "Voltage", "x_column": "Time", "y_columns": ["A"], "title": "Voltage Plot"},
            {"name": "Current", "x_column": "Time", "y_columns": ["B"], "title": "Current Plot"},
        ]
        source.state.active_plot_profile_index = 1
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.json"
            self.assertTrue(source.save_session(path).ok)

            target = MainWindowViewModel()
            self.assertTrue(target.load_session(path).ok)
            self.assertEqual(len(target.state.plot_profiles), 2)
            self.assertEqual(target.state.active_plot_profile_index, 1)
            self.assertEqual(target.state.plot_profiles[0]["title"], "Voltage Plot")
            self.assertEqual(target.state.plot_profiles[1]["y_columns"], ["B"])

    def test_load_missing_file_fails(self) -> None:
        self.assertFalse(MainWindowViewModel().load_session("missing.json").ok)

    def test_save_extensionless_path_adds_json(self) -> None:
        source = self._populated_vm()
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session"
            result = source.save_session(path)
            self.assertTrue(result.ok)
            self.assertTrue((Path(tmp) / "session.json").exists())

    def test_save_session_mark_clean_false_keeps_dirty(self) -> None:
        vm = self._populated_vm()
        vm.state.is_dirty = True
        with tempfile.TemporaryDirectory() as tmp:
            recovery = vm.save_session(Path(tmp) / "recovery.json", mark_clean=False)
            self.assertTrue(recovery.ok)
            self.assertTrue(vm.state.is_dirty)
            explicit = vm.save_session(Path(tmp) / "explicit.json")
            self.assertTrue(explicit.ok)
            self.assertFalse(vm.state.is_dirty)

    def test_capture_working_state_marks_dirty_on_real_change_only(self) -> None:
        vm = MainWindowViewModel()
        vm.capture_working_state(x_column="Time", y_columns=["A"])
        vm.state.is_dirty = False
        vm.capture_working_state(x_column="Time", y_columns=["A"])
        self.assertFalse(vm.state.is_dirty)
        vm.capture_working_state(x_column="Time", y_columns=["A", "B"])
        self.assertTrue(vm.state.is_dirty)

    def test_profile_crud_marks_dirty_but_select_does_not(self) -> None:
        vm = MainWindowViewModel()
        vm.ensure_plot_profiles()
        vm.state.is_dirty = False
        self.assertTrue(vm.add_plot_profile("Plot 2").ok)
        self.assertTrue(vm.state.is_dirty)
        vm.state.is_dirty = False
        self.assertTrue(vm.select_plot_profile(0).ok)
        self.assertFalse(vm.state.is_dirty)
        vm.state.is_dirty = False
        self.assertTrue(vm.rename_plot_profile(0, "Renamed").ok)
        self.assertTrue(vm.state.is_dirty)

    def test_capture_working_state_builds_profile(self) -> None:
        vm = MainWindowViewModel()
        vm.state.limit_lines = [{"name": "L", "type": "Upper Limit", "points": []}]
        vm.state.engineering_notes = {"objective": "Verify response"}
        vm.capture_working_state(
            x_column="Time",
            y_columns=["A"],
            secondary_y_columns=["B"],
            title="Pump Run",
            x_label="Seconds",
            y_label="Pressure",
            secondary_y_label="Current",
            plot_kind="Scatter",
            auto_fit_axes=False,
            axis_limits={"xmin": "0", "xmax": "10", "ymin": "", "ymax": "100"},
            axis_ticks={
                "x_major_tick": "0.5",
                "y_major_tick": "25",
                "y2_major_tick": "2.5",
                "align_secondary_y_axis_grid": True,
            },
            legend_settings={"display_mode": "graph"},
            best_fit_lines=[{"channel": "A", "fit_type": "Linear", "order": 1}],
            analysis_window={"start_x": "1", "end_x": "9"},
            filter_settings={"enabled": True, "cutoff_hz": "50", "order": "4"},
        )
        profile = vm.state.plot_profiles[0]
        self.assertEqual(profile["x_column"], "Time")
        self.assertEqual(profile["secondary_y_columns"], ["B"])
        self.assertEqual(profile["title"], "Pump Run")
        self.assertEqual(profile["x_label"], "Seconds")
        self.assertEqual(profile["y_label"], "Pressure")
        self.assertEqual(profile["secondary_y_label"], "Current")
        self.assertEqual(profile["plot_kind"], "Scatter")
        self.assertFalse(profile["auto_fit_axes"])
        self.assertEqual(profile["axis_limits"]["xmax"], "10")
        self.assertEqual(profile["axis_ticks"]["x_major_tick"], "0.5")
        self.assertTrue(profile["axis_ticks"]["align_secondary_y_axis_grid"])
        self.assertEqual(profile["legend"]["display_mode"], "graph")
        self.assertEqual(profile["best_fit_lines"][0]["channel"], "A")
        self.assertEqual(profile["best_fit_lines"][0]["order"], 1)
        self.assertEqual(profile["analysis_window"]["start_x"], "1")
        self.assertTrue(profile["filter"]["enabled"])
        self.assertEqual(profile["engineering_notes"]["objective"], "Verify response")
        self.assertEqual(len(profile["limit_lines"]), 1)

    def test_generated_flag_round_trips_through_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "data.csv"
            pd.DataFrame({"Time": [0.0, 1.0, 2.0], "A": [1.0, 2.0, 3.0]}).to_csv(data_path, index=False)

            source = MainWindowViewModel()
            source.data_loading.load_file(data_path, None)
            source.capture_working_state(x_column="Time", y_columns=["A"], secondary_y_columns=[], generated=True)
            self.assertTrue(source.state.plot_profiles[0]["generated"])

            session_path = Path(tmp) / "s.json"
            self.assertTrue(source.save_session(session_path).ok)

            target = MainWindowViewModel()
            self.assertTrue(target.restore_session(session_path).ok)
            self.assertTrue(target.state.active_plot_profile()["generated"])

    def test_restore_session_round_trip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "data.csv"
            pd.DataFrame({"Time": [0.0, 1.0, 2.0], "A": [1.0, 2.0, 3.0]}).to_csv(data_path, index=False)
            run_path = Path(tmp) / "run2.csv"
            pd.DataFrame({"Time": [0.0, 1.0, 2.0], "A": [3.0, 4.0, 5.0]}).to_csv(run_path, index=False)

            source = MainWindowViewModel()
            source.data_loading.load_file(data_path, None)
            source.state.limit_lines = [
                {"name": "Max", "type": "Upper Limit", "applies_to": "All selected Y channels",
                 "color": "#005A8C", "points": [{"x": 0, "y": 10}, {"x": 2, "y": 10}]}
            ]
            source.state.engineering_notes = {"objective": "Verify"}
            source.runs_comparison.add_run(run_path, None)
            source.maths_channels.apply_channel("Sum", "A + A")
            source.capture_working_state(x_column="Time", y_columns=["A"], secondary_y_columns=[])

            session_path = Path(tmp) / "s.json"
            self.assertTrue(source.save_session(session_path).ok)

            target = MainWindowViewModel()
            result = target.restore_session(session_path)
            self.assertTrue(result.ok, result.message)
            self.assertEqual(result.warnings, [])
            self.assertIsNotNone(target.state.df)
            self.assertEqual(result.payload["x_column"], "Time")
            self.assertEqual(result.payload["y_columns"], ["A"])
            self.assertEqual(len(target.state.limit_lines), 1)
            self.assertEqual(target.state.engineering_notes["objective"], "Verify")
            self.assertEqual(len(target.state.runs), 1)
            self.assertIn("Sum", target.state.df.columns)

    def test_restore_session_reloads_modified_excel_from_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "data.xlsx"
            with pd.ExcelWriter(data_path, engine="openpyxl") as writer:
                pd.DataFrame({"Time": [0.0, 1.0], "A": [1.0, 2.0]}).to_excel(
                    writer,
                    sheet_name="Data",
                    index=False,
                )

            source = MainWindowViewModel()
            self.assertTrue(source.data_loading.load_file(data_path, "Data").ok)
            source.capture_working_state(x_column="Time", y_columns=["A"], secondary_y_columns=[])
            session_path = Path(tmp) / "s.json"
            self.assertTrue(source.save_session(session_path).ok)

            with pd.ExcelWriter(data_path, engine="openpyxl") as writer:
                pd.DataFrame({"Time": [0.0, 1.0], "A": [10.0, 20.0], "B": [5.0, 6.0]}).to_excel(
                    writer,
                    sheet_name="Data",
                    index=False,
                )

            target = MainWindowViewModel()
            result = target.restore_session(session_path)

            self.assertTrue(result.ok, result.message)
            self.assertEqual(result.warnings, [])
            self.assertEqual(list(target.state.df["A"]), [10.0, 20.0])
            self.assertIn("B", target.state.column_names())

    def test_restore_session_warns_for_plot_channels_missing_after_excel_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "data.xlsx"
            with pd.ExcelWriter(data_path, engine="openpyxl") as writer:
                pd.DataFrame({"Time": [0.0, 1.0], "Outlet Pressure": [1.0, 2.0]}).to_excel(
                    writer,
                    sheet_name="Data",
                    index=False,
                )

            source = MainWindowViewModel()
            self.assertTrue(source.data_loading.load_file(data_path, "Data").ok)
            source.capture_working_state(x_column="Time", y_columns=["Outlet Pressure"], secondary_y_columns=[])
            session_path = Path(tmp) / "s.json"
            self.assertTrue(source.save_session(session_path).ok)

            with pd.ExcelWriter(data_path, engine="openpyxl") as writer:
                pd.DataFrame({"Time": [0.0, 1.0], "Inlet Pressure": [3.0, 4.0]}).to_excel(
                    writer,
                    sheet_name="Data",
                    index=False,
                )

            target = MainWindowViewModel()
            result = target.restore_session(session_path)

            self.assertTrue(result.ok, result.message)
            self.assertIn("Inlet Pressure", target.state.column_names())
            self.assertNotIn("Outlet Pressure", target.state.column_names())
            self.assertTrue(
                any("Outlet Pressure" in warning and "not found" in warning for warning in result.warnings),
                result.warnings,
            )
            self.assertEqual(result.payload["y_columns"], ["Outlet Pressure"])

    def test_restore_session_reuses_main_dataframe_for_matching_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "data.xlsx"
            data_path.write_text("placeholder", encoding="utf-8")
            session_path = Path(tmp) / "s.json"
            session_service.save_session_dict(
                session_path,
                {
                    "version": "test",
                    "file_path": str(data_path),
                    "sheet_name": "Temperature",
                    "runs": [
                        {
                            "name": "Main workbook run",
                            "filepath": str(data_path),
                            "sheet_name": "Temperature",
                            "enabled": True,
                            "colour": "#123456",
                        }
                    ],
                    "active_plot_profile_index": 0,
                    "plot_profiles": [{"name": "Plot 1", "x_column": "Time", "y_columns": ["Temp"]}],
                    "calculated_channels": {},
                },
            )

            loaded_frame = pd.DataFrame({"Time": [0.0, 1.0], "Temp": [20.0, 21.0]})
            load_calls: list[tuple[str, str | None]] = []

            def fake_main_load(path, sheet_name=None, settings_manager=None):
                load_calls.append((str(path), sheet_name))
                return loaded_frame

            def fail_run_load(path, sheet_name=None, settings_manager=None):
                raise AssertionError("matching run should reuse the main dataframe")

            original_main_load = data_loading_module.load_data
            original_run_load = runs_comparison_module.load_data
            data_loading_module.load_data = fake_main_load
            runs_comparison_module.load_data = fail_run_load
            try:
                target = MainWindowViewModel()
                result = target.restore_session(session_path)
            finally:
                data_loading_module.load_data = original_main_load
                runs_comparison_module.load_data = original_run_load

            self.assertTrue(result.ok, result.message)
            self.assertEqual(result.warnings, [])
            self.assertEqual(load_calls, [(str(data_path), "Temperature")])
            self.assertEqual(len(target.state.runs), 1)
            self.assertEqual(target.state.runs[0]["name"], "Main workbook run")
            self.assertEqual(target.state.runs[0]["colour"], "#123456")
            self.assertEqual(list(target.state.runs[0]["df"]["Temp"]), [20.0, 21.0])

    def test_restore_missing_session_fails(self) -> None:
        self.assertFalse(MainWindowViewModel().restore_session("missing.json").ok)

    def test_restore_session_warns_on_missing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            source = MainWindowViewModel()
            source.state.filepath = Path(tmp) / "gone.csv"
            source.state.sheet_name = ""
            source.capture_working_state(x_column="", y_columns=[], secondary_y_columns=[])
            # Force a file_path that no longer exists into the session.
            session_path = Path(tmp) / "s.json"
            session = source.build_session()
            session["file_path"] = str(Path(tmp) / "gone.csv")
            from test_data_analyser.services import session_service

            session_service.save_session_dict(session_path, session)

            target = MainWindowViewModel()
            result = target.restore_session(session_path)
            self.assertTrue(result.ok)
            self.assertTrue(result.warnings)
            self.assertFalse(result.payload["main_data_loaded"])
            self.assertIsNone(target.state.df)

    def test_needs_main_data_relink_detects_missing_main_data(self) -> None:
        missing = OperationResult.success("x", payload={"main_data_warning": "gone", "main_data_loaded": False})
        self.assertTrue(MainWindowViewModel.needs_main_data_relink(missing))
        loaded = OperationResult.success("x", payload={"main_data_warning": "", "main_data_loaded": True})
        self.assertFalse(MainWindowViewModel.needs_main_data_relink(loaded))
        relinked = OperationResult.success("x", payload={"main_data_warning": "gone", "main_data_loaded": True})
        self.assertFalse(MainWindowViewModel.needs_main_data_relink(relinked))
        self.assertFalse(MainWindowViewModel.needs_main_data_relink(OperationResult.failure("bad")))

    def test_restore_session_uses_data_file_override(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_dir = Path(tmp) / "old"
            new_dir = Path(tmp) / "new"
            old_dir.mkdir()
            new_dir.mkdir()
            original_path = old_dir / "data.csv"
            moved_path = new_dir / "data.csv"
            pd.DataFrame({"Time": [0.0, 1.0], "A": [2.0, 3.0]}).to_csv(original_path, index=False)

            source = MainWindowViewModel()
            self.assertTrue(source.data_loading.load_file(original_path, None).ok)
            source.capture_working_state(x_column="Time", y_columns=["A"], secondary_y_columns=[])
            session_path = Path(tmp) / "s.json"
            self.assertTrue(source.save_session(session_path).ok)

            original_path.replace(moved_path)

            target = MainWindowViewModel()
            result = target.restore_session(session_path, data_file_override=moved_path)
            self.assertTrue(result.ok, result.message)
            self.assertEqual(result.warnings, [])
            self.assertTrue(result.payload["main_data_loaded"])
            self.assertEqual(target.state.root_file_directory, str(moved_path.resolve().parent))
            self.assertTrue(target.state.is_dirty)
            self.assertEqual(target.state.filepath, moved_path)
            self.assertEqual(target.state.column_names(), ["Time", "A"])

    def test_restore_session_uses_saved_root_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_dir = Path(tmp) / "old"
            new_dir = Path(tmp) / "new"
            old_dir.mkdir()
            new_dir.mkdir()
            stale_path = old_dir / "data.csv"
            current_path = new_dir / "data.csv"
            pd.DataFrame({"Time": [0.0, 1.0], "A": [2.0, 3.0]}).to_csv(current_path, index=False)
            session_path = Path(tmp) / "s.json"
            from test_data_analyser.services import session_service

            session_service.save_session_dict(
                session_path,
                {
                    "version": "test",
                    "root_file_directory": str(new_dir),
                    "file_path": str(stale_path),
                    "sheet_name": "",
                    "runs": [],
                    "active_plot_profile_index": 0,
                    "plot_profiles": [{"name": "Plot 1", "x_column": "Time", "y_columns": ["A"]}],
                    "calculated_channels": {},
                },
            )

            target = MainWindowViewModel()
            result = target.restore_session(session_path)

            self.assertTrue(result.ok, result.message)
            self.assertEqual(result.warnings, [])
            self.assertEqual(result.payload["source_file_path"], str(current_path))
            self.assertEqual(target.state.root_file_directory, str(new_dir))
            self.assertEqual(target.state.filepath, current_path)
            self.assertEqual(target.state.column_names(), ["Time", "A"])

    def test_save_session_writes_updated_root_directory_after_relink(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old_dir = Path(tmp) / "old"
            new_dir = Path(tmp) / "new"
            old_dir.mkdir()
            new_dir.mkdir()
            original_path = old_dir / "data.csv"
            moved_path = new_dir / "data.csv"
            pd.DataFrame({"Time": [0.0, 1.0], "A": [2.0, 3.0]}).to_csv(original_path, index=False)

            source = MainWindowViewModel()
            self.assertTrue(source.data_loading.load_file(original_path, None).ok)
            source.capture_working_state(x_column="Time", y_columns=["A"], secondary_y_columns=[])
            session_path = Path(tmp) / "s.json"
            self.assertTrue(source.save_session(session_path).ok)
            original_path.replace(moved_path)

            target = MainWindowViewModel()
            self.assertTrue(target.restore_session(session_path, data_file_override=moved_path).ok)
            self.assertTrue(target.state.is_dirty)
            relinked_session_path = Path(tmp) / "relinked.json"
            self.assertTrue(target.save_session(relinked_session_path).ok)
            self.assertFalse(target.state.is_dirty)

            reloaded = session_service.load_session_dict(relinked_session_path)
            self.assertEqual(reloaded["root_file_directory"], str(new_dir))
            self.assertEqual(reloaded["file_path"], str(moved_path))

    def test_restore_missing_main_file_clears_previous_dataframe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            session_path = Path(tmp) / "s.json"
            session = {
                "version": "test",
                "file_path": str(Path(tmp) / "gone.csv"),
                "sheet_name": "",
                "runs": [],
                "active_plot_profile_index": 0,
                "plot_profiles": [{"name": "Plot 1", "x_column": "Time", "y_columns": ["A"]}],
                "calculated_channels": {},
            }
            from test_data_analyser.services import session_service

            session_service.save_session_dict(session_path, session)

            target = MainWindowViewModel()
            target.state.df = pd.DataFrame({"Old": [1.0]})
            result = target.restore_session(session_path)
            self.assertTrue(result.ok)
            self.assertIsNone(target.state.df)
            self.assertIsNone(target.state.filepath)

    def test_create_manual_session_sets_manual_source(self) -> None:
        vm = MainWindowViewModel()
        result = vm.create_manual_session(columns=["A", "B"], rows=3)
        self.assertTrue(result.ok, result.message)
        self.assertTrue(vm.state.is_manual_source)
        self.assertEqual(vm.state.column_names(), ["A", "B"])
        self.assertEqual(len(vm.state.df), 3)
        self.assertEqual(vm.state.channel_registry.ids(), ["ch_001", "ch_002"])
        self.assertIsNone(vm.state.filepath)
        self.assertTrue(vm.state.is_dirty)

    def test_manual_session_save_and_restore_round_trip(self) -> None:
        source = MainWindowViewModel()
        self.assertTrue(source.create_manual_session(columns=["Time", "Pressure"], rows=2).ok)
        time_id = source.state.channel_registry.id_for_name("Time")
        pressure_id = source.state.channel_registry.id_for_name("Pressure")
        source.state.df.at[0, "Time"] = 0.0
        source.state.df.at[1, "Time"] = 1.0
        source.state.df.at[0, "Pressure"] = 10.0
        source.state.df.at[1, "Pressure"] = 11.0
        source.capture_working_state(x_column="Time", y_columns=["Pressure"], secondary_y_columns=[])

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "manual.json"
            self.assertTrue(source.save_session(path).ok)

            target = MainWindowViewModel()
            result = target.restore_session(path)
            self.assertTrue(result.ok, result.message)
            self.assertEqual(result.warnings, [])
            self.assertTrue(target.state.is_manual_source)
            self.assertIsNone(target.state.filepath)
            self.assertEqual(target.state.column_names(), ["Time", "Pressure"])
            self.assertEqual(list(target.state.df["Pressure"]), [10.0, 11.0])
            self.assertEqual(target.state.channel_registry.id_for_name("Time"), time_id)
            self.assertEqual(target.state.channel_registry.id_for_name("Pressure"), pressure_id)

    def test_excel_restore_preserves_channel_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "data.csv"
            pd.DataFrame({"Time": [0.0, 1.0], "A": [1.0, 2.0]}).to_csv(data_path, index=False)

            source = MainWindowViewModel()
            self.assertTrue(source.data_loading.load_file(data_path, None).ok)
            original_ids = dict(
                zip(source.state.channel_registry.display_names(), source.state.channel_registry.ids())
            )
            source.capture_working_state(x_column="Time", y_columns=["A"], secondary_y_columns=[])
            session_path = Path(tmp) / "s.json"
            self.assertTrue(source.save_session(session_path).ok)

            target = MainWindowViewModel()
            self.assertTrue(target.restore_session(session_path).ok)
            restored_ids = dict(
                zip(target.state.channel_registry.display_names(), target.state.channel_registry.ids())
            )
            self.assertEqual(restored_ids, original_ids)
            self.assertEqual(target.state.data_source_type, "excel")

    def test_legacy_session_without_registry_restores_and_builds_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_path = Path(tmp) / "data.csv"
            pd.DataFrame({"Time": [0.0, 1.0], "A": [1.0, 2.0]}).to_csv(data_path, index=False)
            session_path = Path(tmp) / "s.json"
            session_service.save_session_dict(
                session_path,
                {
                    "version": "old",
                    "file_path": str(data_path),
                    "sheet_name": "",
                    "runs": [],
                    "active_plot_profile_index": 0,
                    "plot_profiles": [{"name": "Plot 1", "x_column": "Time", "y_columns": ["A"]}],
                    "calculated_channels": {},
                },
            )

            target = MainWindowViewModel()
            result = target.restore_session(session_path)
            self.assertTrue(result.ok, result.message)
            self.assertEqual(target.state.data_source_type, "excel")
            self.assertEqual(target.state.channel_registry.display_names(), ["Time", "A"])
            self.assertTrue(target.state.channel_registry.ids())


class DatasetClipboardTests(unittest.TestCase):
    def _vm(self) -> MainWindowViewModel:
        vm = MainWindowViewModel()
        vm.state.df = pd.DataFrame({"A": [1.0, 2.0, 3.0], "B": [4.0, 5.0, 6.0]})
        vm.state.channel_registry = dataset_service.build_registry_for_dataframe(vm.state.df)
        return vm

    def test_copy_block_returns_tsv(self) -> None:
        vm = self._vm()
        ids = vm.state.channel_registry.ids()
        self.assertEqual(vm.dataset.copy_block([0, 1], ids), "1.0\t4.0\n2.0\t5.0")

    def test_cut_block_clears_cells_and_returns_tsv(self) -> None:
        vm = self._vm()
        ids = vm.state.channel_registry.ids()
        result = vm.dataset.cut_block([0], ids)
        self.assertTrue(result.ok)
        self.assertEqual(result.payload, "1.0\t4.0")
        self.assertTrue(pd.isna(vm.state.df.at[0, "A"]))
        self.assertTrue(pd.isna(vm.state.df.at[0, "B"]))

    def test_paste_block_writes_values(self) -> None:
        vm = self._vm()
        anchor = vm.state.channel_registry.ids()[0]
        result = vm.dataset.paste_block(0, anchor, "7\t8\n9\t10")
        self.assertTrue(result.ok)
        self.assertEqual(vm.state.df.at[0, "A"], 7.0)
        self.assertEqual(vm.state.df.at[0, "B"], 8.0)
        self.assertEqual(vm.state.df.at[1, "A"], 9.0)
        self.assertEqual(vm.state.df.at[1, "B"], 10.0)

    def test_paste_block_expands_df_when_needed(self) -> None:
        vm = self._vm()
        rightmost = vm.state.channel_registry.ids()[1]
        result = vm.dataset.paste_block(0, rightmost, "1\t2\n3\t4\n5\t6\n7\t8")
        self.assertTrue(result.ok)
        self.assertEqual(len(vm.state.df), 4)
        self.assertEqual(len(vm.state.channel_registry.ids()), 3)
        new_name = vm.state.channel_registry.display_names()[2]
        self.assertEqual(new_name, "Column 3")
        self.assertEqual(vm.state.df.at[0, new_name], 2.0)
        self.assertEqual(vm.state.df.at[3, new_name], 8.0)

    def test_paste_block_single_undo_step(self) -> None:
        vm = self._vm()
        anchor = vm.state.channel_registry.ids()[0]
        vm.dataset.paste_block(0, anchor, "100\t200\n300\t400")
        self.assertTrue(vm.dataset.can_undo)
        vm.dataset.undo_last_edit()
        self.assertEqual(vm.state.df.at[0, "A"], 1.0)
        self.assertEqual(vm.state.df.at[0, "B"], 4.0)
        self.assertFalse(vm.dataset.can_undo)

    def test_paste_block_warns_on_invalid_numeric_text(self) -> None:
        vm = self._vm()
        anchor = vm.state.channel_registry.ids()[0]
        result = vm.dataset.paste_block(0, anchor, "abc")
        self.assertTrue(result.ok)
        self.assertTrue(result.warnings)
        self.assertEqual(vm.state.df.at[0, "A"], "abc")


class FindReplaceVMTests(unittest.TestCase):
    def _vm(self) -> MainWindowViewModel:
        vm = MainWindowViewModel()
        vm.state.df = pd.DataFrame({"A": [1.0, 2.0, 3.0], "Name": ["x1", "x2", "y1"]})
        vm.state.channel_registry = dataset_service.build_registry_for_dataframe(vm.state.df)
        return vm
    def test_find_full_dataset(self) -> None:
        vm = self._vm()
        result = vm.raw_data.find("x")
        self.assertTrue(result.ok)
        self.assertEqual(len(result.payload), 2)

    def test_find_displayed_frame_scope(self) -> None:
        vm = self._vm()
        display = vm.state.df.iloc[:1]
        result = vm.raw_data.find("x", search_full_dataset=False, display_frame=display)
        self.assertEqual(len(result.payload), 1)

    def test_replace_all_single_undo_step(self) -> None:
        vm = self._vm()
        result = vm.raw_data.replace_all("x", "z")
        self.assertTrue(result.ok)
        self.assertEqual(result.payload["replaced"], 2)
        self.assertEqual(vm.state.df.at[0, "Name"], "z1")
        self.assertTrue(vm.raw_data.can_undo)

        vm.raw_data.undo_last_edit()
        self.assertEqual(vm.state.df.at[0, "Name"], "x1")
        self.assertFalse(vm.raw_data.can_undo)

    def test_replace_all_regex_round_trip(self) -> None:
        vm = self._vm()
        result = vm.raw_data.replace_all(r"x(\d)", r"a\1", regex=True, columns=["Name"])
        self.assertTrue(result.ok)
        self.assertEqual(vm.state.df.at[0, "Name"], "a1")
        self.assertEqual(vm.state.df.at[1, "Name"], "a2")

    def test_replace_all_invalid_regex_fails(self) -> None:
        vm = self._vm()
        self.assertFalse(vm.raw_data.replace_all("(", "x", regex=True).ok)

    def test_replace_all_numeric_column_keeps_text_with_warning(self) -> None:
        vm = self._vm()
        result = vm.raw_data.replace_all("1.0", "abc", columns=["A"])
        self.assertTrue(result.ok)
        self.assertEqual(vm.state.df.at[0, "A"], "abc")
        self.assertTrue(result.warnings)


class FillVMTests(unittest.TestCase):
    def _vm(self) -> MainWindowViewModel:
        vm = MainWindowViewModel()
        vm.state.df = pd.DataFrame({"A": [1.0, 2.0, 0.0, 0.0, 0.0], "B": [9.0, 0.0, 0.0, 0.0, 0.0]})
        vm.state.channel_registry = dataset_service.build_registry_for_dataframe(vm.state.df)
        return vm
    def test_fill_down_copies_top_value(self) -> None:
        vm = self._vm()
        ids = vm.state.channel_registry.ids()
        result = vm.dataset.fill_down([0, 1, 2, 3, 4], [ids[1]])
        self.assertTrue(result.ok)
        self.assertEqual(list(vm.state.df["B"]), [9.0, 9.0, 9.0, 9.0, 9.0])

    def test_fill_drag_linear(self) -> None:
        vm = self._vm()
        ids = vm.state.channel_registry.ids()
        result = vm.dataset.fill_drag([0, 1], [2, 3, 4], [ids[0]])
        self.assertTrue(result.ok)
        self.assertEqual(list(vm.state.df["A"]), [1.0, 2.0, 3.0, 4.0, 5.0])

    def test_fill_drag_undo_restores_values(self) -> None:
        vm = self._vm()
        ids = vm.state.channel_registry.ids()
        vm.dataset.fill_drag([0, 1], [2, 3, 4], [ids[0]])
        self.assertTrue(vm.dataset.can_undo)
        vm.dataset.undo_last_edit()
        self.assertEqual(list(vm.state.df["A"]), [1.0, 2.0, 0.0, 0.0, 0.0])
        self.assertFalse(vm.dataset.can_undo)


class RunsComparisonBatchTests(unittest.TestCase):
    def test_imports_multiple_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for index in range(3):
                frame = pd.DataFrame({"Time": [0.0, 1.0], "A": [float(index), float(index + 1)]})
                frame.to_csv(Path(directory, f"Run{index}.csv"), index=False)
            vm = MainWindowViewModel()

            result = vm.runs_comparison.add_runs_from_folder(directory, glob="*.csv")

            self.assertTrue(result.ok)
            self.assertEqual(result.payload["added"], 3)
            self.assertEqual(len(vm.state.runs), 3)

    def test_applies_name_regex(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pd.DataFrame({"Time": [0.0], "A": [1.0]}).to_csv(Path(directory, "Run_SN42.csv"), index=False)
            vm = MainWindowViewModel()

            vm.runs_comparison.add_runs_from_folder(directory, glob="*.csv", name_regex=r"SN(\d+)")

            self.assertEqual(vm.state.runs[0]["name"], "42")

    def test_skips_corrupt_file_with_warning(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            pd.DataFrame({"Time": [0.0], "A": [1.0]}).to_csv(Path(directory, "good.csv"), index=False)
            Path(directory, "bad.xlsx").write_text("not an excel file", encoding="utf-8")
            vm = MainWindowViewModel()

            result = vm.runs_comparison.add_runs_from_folder(directory, glob="*.csv;*.xlsx")

            self.assertTrue(result.ok)
            self.assertEqual(result.payload["added"], 1)
            self.assertTrue(result.warnings)
            self.assertIn("bad.xlsx", result.warnings[0])


class LimitTemplateImportTests(unittest.TestCase):
    def _template_path(self, directory: str) -> str:
        source = LimitsViewModel(AppState())
        source.state.limit_lines = [source._blank_line("L1")]
        path = str(Path(directory, "template.json"))
        self.assertTrue(source.export_template(path).ok)
        return path

    def test_replace_clears_then_imports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._template_path(directory)
            vm = LimitsViewModel(AppState())
            vm.state.limit_lines = [vm._blank_line("Existing")]

            result = vm.import_template(path, replace=True)

            self.assertTrue(result.ok)
            self.assertEqual([line["name"] for line in vm.state.limit_lines], ["L1"])

    def test_merge_appends(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = self._template_path(directory)
            vm = LimitsViewModel(AppState())
            vm.state.limit_lines = [vm._blank_line("Existing")]

            result = vm.import_template(path, replace=False)

            self.assertTrue(result.ok)
            self.assertEqual([line["name"] for line in vm.state.limit_lines], ["Existing", "L1"])


class PeakDetectionVMTests(unittest.TestCase):
    def _vm(self) -> MainWindowViewModel:
        vm = MainWindowViewModel()
        x = np.linspace(0, 4 * np.pi, 400)
        vm.state.df = pd.DataFrame({"Time": x, "A": np.sin(x)})
        vm.state.current_x_axis = "Time"
        vm.state.channel_registry = dataset_service.build_registry_for_dataframe(vm.state.df)
        return vm

    def test_returns_peak_points_and_annotations(self) -> None:
        vm = self._vm()
        result = vm.plot_workspace.detect_peaks("A")
        self.assertTrue(result.ok)
        self.assertEqual(len(result.payload["points"]), 2)
        annotations = result.payload["annotations"]
        self.assertEqual(len(annotations), 2)
        self.assertEqual(annotations[0]["type"], "text")
        self.assertIn("text", annotations[0])

    def test_unknown_channel_fails(self) -> None:
        vm = self._vm()
        self.assertFalse(vm.plot_workspace.detect_peaks("Missing").ok)


class PlotProfileReorderTests(unittest.TestCase):
    def test_reorder_moves_active_index(self) -> None:
        vm = MainWindowViewModel()
        vm.state.plot_profiles = [{"name": "P1"}, {"name": "P2"}, {"name": "P3"}]
        vm.state.active_plot_profile_index = 0

        result = vm.reorder_plot_profile(0, 2)

        self.assertTrue(result.ok)
        self.assertEqual([profile["name"] for profile in vm.state.plot_profiles], ["P2", "P3", "P1"])
        self.assertEqual(vm.state.active_plot_profile_index, 2)

    def test_reorder_shifts_active_when_other_tab_moves(self) -> None:
        vm = MainWindowViewModel()
        vm.state.plot_profiles = [{"name": "P1"}, {"name": "P2"}, {"name": "P3"}]
        vm.state.active_plot_profile_index = 1

        vm.reorder_plot_profile(0, 2)

        self.assertEqual(vm.state.active_plot_profile_index, 0)

    def test_reorder_invalid_index_fails(self) -> None:
        vm = MainWindowViewModel()
        vm.state.plot_profiles = [{"name": "P1"}]
        self.assertFalse(vm.reorder_plot_profile(0, 5).ok)


class ResetAxisAppearanceTests(unittest.TestCase):
    def test_reset_active_axis_appearance_clears_manual_state(self) -> None:
        vm = MainWindowViewModel()
        vm.state.plot_profiles = [
            {
                "name": "P1",
                "x_column": "Time",
                "y_columns": ["A"],
                "title": "Custom Title",
                "axis_limits": {"xmin": 0.0, "xmax": 10.0, "ymin": -1.0, "ymax": 1.0},
                "manual_labels": {"title": True, "x_label": True},
            }
        ]
        vm.state.active_plot_profile_index = 0

        result = vm.reset_active_axis_appearance()

        self.assertTrue(result.ok)
        profile = vm.state.plot_profiles[0]
        self.assertEqual(profile["x_column"], "Time")
        self.assertEqual(profile["y_columns"], ["A"])
        self.assertNotEqual(profile.get("title"), "Custom Title")
        self.assertFalse(any(bool(value) for value in (profile.get("manual_labels") or {}).values()))

    def test_reset_active_axis_appearance_without_profiles_fails(self) -> None:
        vm = MainWindowViewModel()
        vm.state.plot_profiles = []
        self.assertFalse(vm.reset_active_axis_appearance().ok)


class DatasetViewModelTests(unittest.TestCase):
    def _manual_vm(self) -> MainWindowViewModel:
        vm = MainWindowViewModel()
        vm.create_manual_session(columns=["Time", "Pressure"], rows=2)
        return vm
    def test_add_column_and_duplicate_block(self) -> None:
        vm = self._manual_vm()
        self.assertTrue(vm.dataset.add_column("Flow").ok)
        self.assertIn("Flow", vm.state.column_names())
        self.assertEqual(vm.state.channel_registry.id_for_name("Flow"), "ch_003")
        self.assertFalse(vm.dataset.add_column("Flow").ok)

    def test_rename_column_propagates_to_profile(self) -> None:
        vm = self._manual_vm()
        key = plot_render_service.normalise_channel_name("Pressure")
        vm.state.plot_profiles = [
            {
                "name": "Plot 1",
                "x_column": "Time",
                "y_columns": ["Pressure"],
                "secondary_y_columns": [],
                "best_fit_lines": [{"channel": "Pressure", "fit_type": "Linear", "order": 1}],
                "legend": {"channel_overrides": {key: {"channel": "Pressure", "colour": "#111111"}}},
                "limit_lines": [{"name": "L", "applies_to": "Pressure", "points": []}],
            }
        ]
        channel_id = vm.state.channel_registry.id_for_name("Pressure")
        result = vm.dataset.rename_column(channel_id, "Outlet Pressure")
        self.assertTrue(result.ok, result.message)
        profile = vm.state.plot_profiles[0]
        self.assertEqual(profile["y_columns"], ["Outlet Pressure"])
        self.assertEqual(profile["best_fit_lines"][0]["channel"], "Outlet Pressure")
        self.assertEqual(profile["limit_lines"][0]["applies_to"], "Outlet Pressure")
        new_key = plot_render_service.normalise_channel_name("Outlet Pressure")
        self.assertEqual(profile["legend"]["channel_overrides"][new_key]["channel"], "Outlet Pressure")
        self.assertIn("Outlet Pressure", vm.state.column_names())

    def test_rename_column_updates_current_x_axis(self) -> None:
        vm = self._manual_vm()
        vm.state.current_x_axis = "Time"
        channel_id = vm.state.channel_registry.id_for_name("Time")
        self.assertTrue(vm.dataset.rename_column(channel_id, "Seconds").ok)
        self.assertEqual(vm.state.current_x_axis, "Seconds")

    def test_rename_column_rewrites_maths_formula(self) -> None:
        vm = self._manual_vm()
        vm.state.calculated_channels = {
            "Doubled": {
                "name": "Doubled",
                "formula": "`Pressure` * 2",
                "description": "",
                "enabled": True,
                "created_from_columns": ["Pressure"],
            }
        }
        channel_id = vm.state.channel_registry.id_for_name("Pressure")
        self.assertTrue(vm.dataset.rename_column(channel_id, "Outlet Pressure").ok)
        definition = vm.state.calculated_channels["Doubled"]
        self.assertEqual(definition["formula"], "`Outlet Pressure` * 2")
        self.assertEqual(definition["created_from_columns"], ["Outlet Pressure"])

    def test_rename_column_blocks_duplicate(self) -> None:
        vm = self._manual_vm()
        channel_id = vm.state.channel_registry.id_for_name("Pressure")
        result = vm.dataset.rename_column(channel_id, "Time")
        self.assertFalse(result.ok)
        self.assertIn("already exists", result.message)

    def test_delete_column_warns_dependents(self) -> None:
        vm = self._manual_vm()
        vm.state.plot_profiles = [
            {"name": "Plot 1", "x_column": "Time", "y_columns": ["Pressure"], "secondary_y_columns": []}
        ]
        vm.state.calculated_channels = {
            "Doubled": {
                "name": "Doubled",
                "formula": "`Pressure` * 2",
                "description": "",
                "enabled": True,
                "created_from_columns": ["Pressure"],
            }
        }
        channel_id = vm.state.channel_registry.id_for_name("Pressure")
        result = vm.dataset.delete_column(channel_id)
        self.assertTrue(result.ok, result.message)
        self.assertNotIn("Pressure", vm.state.column_names())
        self.assertEqual(vm.state.plot_profiles[0]["y_columns"], [])
        self.assertTrue(any("Plot 1" in warning for warning in result.warnings))
        self.assertTrue(any("Doubled" in warning for warning in result.warnings))

    def test_row_and_cell_operations(self) -> None:
        vm = self._manual_vm()
        self.assertTrue(vm.dataset.add_row().ok)
        self.assertEqual(len(vm.state.df), 3)
        channel_id = vm.state.channel_registry.id_for_name("Pressure")
        self.assertTrue(vm.dataset.set_cell(channel_id, 0, "42").ok)
        self.assertEqual(vm.state.df.at[0, "Pressure"], 42.0)
        self.assertTrue(vm.dataset.delete_rows([0]).ok)
        self.assertEqual(len(vm.state.df), 2)

    def test_move_column_reorders_and_can_undo(self) -> None:
        vm = self._manual_vm()
        channel_id = vm.state.channel_registry.id_for_name("Time")
        self.assertTrue(vm.dataset.move_column(channel_id, 1).ok)
        self.assertEqual(vm.state.column_names(), ["Pressure", "Time"])
        self.assertTrue(vm.dataset.can_undo)
        self.assertTrue(vm.dataset.undo_last_edit().ok)
        self.assertEqual(vm.state.column_names(), ["Time", "Pressure"])

    def test_undo_dataset_cell_edit(self) -> None:
        vm = self._manual_vm()
        channel_id = vm.state.channel_registry.id_for_name("Pressure")

        self.assertFalse(vm.dataset.can_undo)
        self.assertTrue(vm.dataset.set_cell(channel_id, 0, "42").ok)
        self.assertEqual(vm.state.df.at[0, "Pressure"], 42.0)
        self.assertTrue(vm.dataset.can_undo)

        undo = vm.dataset.undo_last_edit()
        self.assertTrue(undo.ok, undo.message)
        self.assertTrue(pd.isna(vm.state.df.at[0, "Pressure"]))
        self.assertFalse(vm.dataset.can_undo)

    def test_undo_dataset_structural_edits(self) -> None:
        vm = self._manual_vm()
        original_columns = list(vm.state.df.columns)
        original_rows = len(vm.state.df)

        self.assertTrue(vm.dataset.add_column("Flow").ok)
        self.assertIn("Flow", vm.state.column_names())
        self.assertTrue(vm.dataset.undo_last_edit().ok)
        self.assertEqual(list(vm.state.df.columns), original_columns)

        self.assertTrue(vm.dataset.add_row().ok)
        self.assertEqual(len(vm.state.df), original_rows + 1)
        self.assertTrue(vm.dataset.undo_last_edit().ok)
        self.assertEqual(len(vm.state.df), original_rows)

        self.assertTrue(vm.dataset.delete_rows([0]).ok)
        self.assertEqual(len(vm.state.df), original_rows - 1)
        self.assertTrue(vm.dataset.undo_last_edit().ok)
        self.assertEqual(len(vm.state.df), original_rows)

        pressure_id = vm.state.channel_registry.id_for_name("Pressure")
        self.assertTrue(vm.dataset.rename_column(pressure_id, "Outlet Pressure").ok)
        self.assertIn("Outlet Pressure", vm.state.column_names())
        self.assertTrue(vm.dataset.undo_last_edit().ok)
        self.assertEqual(list(vm.state.df.columns), original_columns)

        pressure_id = vm.state.channel_registry.id_for_name("Pressure")
        self.assertTrue(vm.dataset.delete_column(pressure_id).ok)
        self.assertNotIn("Pressure", vm.state.column_names())
        self.assertTrue(vm.dataset.undo_last_edit().ok)
        self.assertEqual(list(vm.state.df.columns), original_columns)

    def test_delete_multiple_columns_and_undo(self) -> None:
        vm = MainWindowViewModel()
        vm.create_manual_session(columns=["Time", "Pressure", "Flow"], rows=2)
        original_columns = list(vm.state.df.columns)
        pressure_id = vm.state.channel_registry.id_for_name("Pressure")
        flow_id = vm.state.channel_registry.id_for_name("Flow")

        result = vm.dataset.delete_columns([pressure_id, flow_id])

        self.assertTrue(result.ok, result.message)
        self.assertEqual(vm.state.column_names(), ["Time"])
        self.assertTrue(vm.dataset.can_undo)

        undo = vm.dataset.undo_last_edit()
        self.assertTrue(undo.ok, undo.message)
        self.assertEqual(list(vm.state.df.columns), original_columns)


if __name__ == "__main__":
    unittest.main()
