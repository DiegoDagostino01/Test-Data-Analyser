"""Framework-independent tests for the viewmodel layer.

These tests exercise the UI-independent viewmodels in
``test_data_analyser.viewmodels`` (and the supporting settings/session services).
They must not require a GUI.

Run with:

    python -m unittest discover -s tests
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

from test_data_analyser.domain import PlotData
from test_data_analyser.viewmodels import (
    AppState,
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
            self.vm.applies_options(["A", "B"]),
            ["All selected Y channels", "A", "B"],
        )


class RawDataViewModelTests(unittest.TestCase):
    def setUp(self) -> None:
        self.state = AppState(df=_sample_df())
        self.vm = RawDataViewModel(self.state)

    def test_parse_row_limit(self) -> None:
        self.assertIsNone(self.vm.parse_row_limit("All").payload)
        self.assertEqual(self.vm.parse_row_limit("10").payload, 10)
        self.assertFalse(self.vm.parse_row_limit("bad").ok)

    def test_select_frame(self) -> None:
        frame, removed = self.vm.select_frame(
            "Time", ["A"], apply_window=True, xmin=1.0, xmax=2.0, drop_blank=False
        )
        self.assertEqual(list(frame["Time"]), [1.0, 2.0])
        self.assertEqual(removed, 0)

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
        self.assertFalse(self.vm.undo_last_edit().ok)

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
            legend_settings={"display_mode": "graph"},
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
        self.assertEqual(profile["legend"]["display_mode"], "graph")
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


if __name__ == "__main__":
    unittest.main()
