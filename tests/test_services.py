"""Framework-independent tests for the service layer.

These tests exercise the pure engineering/data logic extracted into
``test_data_analyser.services``. They must not require a GUI.

Run with:

    python -m unittest discover -s tests
"""
from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import numpy as np
import pandas as pd

from test_data_analyser.core import data_io
from test_data_analyser.core.config import EATON_PLOT_COLORS
from test_data_analyser.domain import SOURCE_MANUAL, PlotData, SessionState
from test_data_analyser.services import (
    annotation_geometry_service,
    axis_limits_computer,
    legend_metadata_service,
    column_reference_service,
    batch_import_service,
    clipboard_service,
    cursor_service,
    dataset_service,
    fill_series_service,
    find_replace_service,
    limit_templates_service,
    limits_service,
    maths_channel_service,
    peak_detection_service,
    plot_profile_service,
    plot_render_service,
    plotting_data_service,
    raw_data_service,
    run_comparison_service,
    session_service,
    statistics_service,
)
from test_data_analyser.services.maths_channel_service import MathsChannelEvaluator
from test_data_analyser.services.results import OperationResult, payload_dict


class AnnotationGeometryServiceTests(unittest.TestCase):
    def test_point_distance(self) -> None:
        self.assertAlmostEqual(annotation_geometry_service.point_distance((0.0, 0.0), (3.0, 4.0)), 5.0)

    def test_distance_to_segment_projects_within(self) -> None:
        distance = annotation_geometry_service.distance_to_segment((5.0, 5.0), (0.0, 0.0), (10.0, 0.0))
        self.assertAlmostEqual(distance, 5.0)

    def test_distance_to_segment_clamps_beyond_endpoint(self) -> None:
        distance = annotation_geometry_service.distance_to_segment((-3.0, 4.0), (0.0, 0.0), (10.0, 0.0))
        self.assertAlmostEqual(distance, 5.0)

    def test_distance_to_segment_degenerate_segment(self) -> None:
        distance = annotation_geometry_service.distance_to_segment((3.0, 4.0), (2.0, 2.0), (2.0, 2.0))
        self.assertAlmostEqual(distance, 5.0 ** 0.5)

    def test_annotation_handle_points_arrow(self) -> None:
        points = annotation_geometry_service.annotation_handle_points(
            {"type": "arrow", "start_x": 1, "start_y": 2, "end_x": 3, "end_y": 4}
        )
        self.assertEqual(points, {"start": (1.0, 2.0), "end": (3.0, 4.0)})

    def test_annotation_handle_points_box_corners(self) -> None:
        points = annotation_geometry_service.annotation_handle_points(
            {"type": "box", "x_min": 0, "x_max": 2, "y_min": 0, "y_max": 4}
        )
        self.assertEqual(points["bottom_left"], (0.0, 0.0))
        self.assertEqual(points["bottom_right"], (2.0, 0.0))
        self.assertEqual(points["top_left"], (0.0, 4.0))
        self.assertEqual(points["top_right"], (2.0, 4.0))

    def test_annotation_handle_points_text_has_none(self) -> None:
        self.assertEqual(annotation_geometry_service.annotation_handle_points({"type": "text"}), {})

    def test_annotation_float_invalid_returns_default(self) -> None:
        self.assertEqual(annotation_geometry_service.annotation_float({"x": "bad"}, "x", 1.5), 1.5)


class AnnotationDragTests(unittest.TestCase):
    def test_move_text(self) -> None:
        ann = {"type": "text", "x": 1.0, "y": 2.0}
        annotation_geometry_service.move_annotation(ann, dict(ann), 0.5, -0.5)
        self.assertEqual((ann["x"], ann["y"]), (1.5, 1.5))

    def test_move_box_shifts_all_bounds(self) -> None:
        ann = {"type": "box", "x_min": 0.0, "x_max": 2.0, "y_min": 0.0, "y_max": 2.0}
        annotation_geometry_service.move_annotation(ann, dict(ann), 1.0, 1.0)
        self.assertEqual((ann["x_min"], ann["x_max"], ann["y_min"], ann["y_max"]), (1.0, 3.0, 1.0, 3.0))

    def test_resize_box_top_right(self) -> None:
        ann = {"type": "box", "x_min": 0.0, "x_max": 2.0, "y_min": 0.0, "y_max": 2.0}
        annotation_geometry_service.resize_box_annotation(ann, dict(ann), "top_right", (3.0, 4.0))
        self.assertEqual((ann["x_max"], ann["y_max"]), (3.0, 4.0))

    def test_resize_box_normalises_when_edge_crosses(self) -> None:
        ann = {"type": "box", "x_min": 0.0, "x_max": 2.0, "y_min": 0.0, "y_max": 2.0}
        annotation_geometry_service.resize_box_annotation(ann, dict(ann), "left", (5.0, 0.0))
        self.assertEqual((ann["x_min"], ann["x_max"]), (2.0, 5.0))

    def test_apply_drag_arrow_endpoint(self) -> None:
        ann = {"type": "arrow", "start_x": 0.0, "start_y": 0.0, "end_x": 1.0, "end_y": 1.0}
        annotation_geometry_service.apply_annotation_drag(ann, dict(ann), "end", 0.0, 0.0, (0.8, 0.9))
        self.assertEqual((ann["end_x"], ann["end_y"]), (0.8, 0.9))

    def test_apply_drag_move_dispatches(self) -> None:
        ann = {"type": "text", "x": 0.0, "y": 0.0}
        annotation_geometry_service.apply_annotation_drag(ann, dict(ann), "move", 1.0, 2.0, (0.0, 0.0))
        self.assertEqual((ann["x"], ann["y"]), (1.0, 2.0))


class SeriesColourAssignmentTests(unittest.TestCase):
    def test_no_manual_or_repeated_returns_all_none(self) -> None:
        items = [{"channel": "A"}, {"channel": "B"}]
        result = plot_render_service.series_colour_assignment(items, {}, ["#111111", "#222222"], ["#333333"])
        self.assertEqual(result, [None, None])

    def test_manual_colour_preserved_and_others_distinct(self) -> None:
        items = [{"channel": "A", "colour": "#ff0000"}, {"channel": "B"}]
        result = plot_render_service.series_colour_assignment(items, {}, ["#ff0000", "#00ff00"], ["#0000ff"])
        self.assertEqual(result[0], "#ff0000")
        self.assertEqual(result[1], "#00ff00")

    def test_persistent_channel_colour_applied(self) -> None:
        items = [{"channel": "A"}, {"channel": "B"}]
        result = plot_render_service.series_colour_assignment(items, {"A": "#123456"}, ["#111111", "#222222"], ["#333333"])
        self.assertEqual(result[0], "#123456")

    def test_secondary_uses_secondary_cycle(self) -> None:
        items = [{"channel": "A", "colour": "#ff0000"}, {"channel": "B", "secondary": True}]
        result = plot_render_service.series_colour_assignment(items, {}, ["#ff0000"], ["#abcdef"])
        self.assertEqual(result[0], "#ff0000")
        self.assertEqual(result[1], "#abcdef")


class AxisLimitsComputerTests(unittest.TestCase):
    def test_positive_float_valid(self) -> None:
        self.assertEqual(axis_limits_computer.positive_float("2.5"), 2.5)

    def test_positive_float_rejects_non_positive_and_blank(self) -> None:
        self.assertIsNone(axis_limits_computer.positive_float("0"))
        self.assertIsNone(axis_limits_computer.positive_float("-3"))
        self.assertIsNone(axis_limits_computer.positive_float(""))
        self.assertIsNone(axis_limits_computer.positive_float("abc"))

    def test_safe_major_tick_keeps_reasonable_step(self) -> None:
        self.assertEqual(axis_limits_computer.safe_major_tick(10.0, (0.0, 100.0)), 10.0)

    def test_safe_major_tick_drops_step_that_exceeds_max_ticks(self) -> None:
        self.assertIsNone(axis_limits_computer.safe_major_tick(2.0, (0.0, 90000.0)))

    def test_safe_major_tick_none_step(self) -> None:
        self.assertIsNone(axis_limits_computer.safe_major_tick(None, (0.0, 100.0)))

    def test_mapped_secondary_ticks_linear(self) -> None:
        ticks = axis_limits_computer.mapped_secondary_ticks([0.0, 5.0, 10.0], 0.0, 10.0, 0.0, 100.0)
        self.assertEqual(ticks, [0.0, 50.0, 100.0])

    def test_mapped_secondary_ticks_degenerate_primary(self) -> None:
        self.assertEqual(axis_limits_computer.mapped_secondary_ticks([1.0], 5.0, 5.0, 0.0, 100.0), [])


class LegendMetadataServiceTests(unittest.TestCase):
    class _FakeLine:
        _tda_channel = "TC1"

        @staticmethod
        def get_visible() -> bool:
            return True

        @staticmethod
        def get_linestyle() -> str:
            return "--"

        @staticmethod
        def get_drawstyle() -> str:
            return "steps"

        @staticmethod
        def get_linewidth() -> float:
            return 2.0

        @staticmethod
        def get_marker() -> str:
            return "o"

        @staticmethod
        def get_markersize() -> float:
            return 4.0

        @staticmethod
        def get_markerfacecolor() -> str:
            return "#abcdef"

        @staticmethod
        def get_markeredgecolor() -> str:
            return "#654321"

        @staticmethod
        def get_color() -> str:
            return "#123456"

    def test_channel_metadata_reads_handle(self) -> None:
        meta = legend_metadata_service.channel_metadata(self._FakeLine(), "Flow [Right Y]")
        self.assertEqual(meta["channel"], "TC1")
        self.assertEqual(meta["label"], "Flow")
        self.assertEqual(str(meta["colour"]).lower(), "#123456")
        self.assertEqual(meta["line_style"], "--")
        self.assertEqual(meta["marker_style"], "o")

    def test_channel_metadata_empty_without_channel(self) -> None:
        class _NoChannel(self._FakeLine):
            _tda_channel = ""

        self.assertEqual(legend_metadata_service.channel_metadata(_NoChannel(), "x"), {})

    def test_normalise_marker_style(self) -> None:
        self.assertEqual(legend_metadata_service.normalise_marker_style("None"), "none")
        self.assertEqual(legend_metadata_service.normalise_marker_style("s"), "s")

    def test_colour_to_hex_invalid_returns_blank(self) -> None:
        self.assertEqual(legend_metadata_service.colour_to_hex(object()), "")

    def test_first_colour_to_hex_empty(self) -> None:
        self.assertEqual(legend_metadata_service.first_colour_to_hex([]), "")


class StatisticsServiceTests(unittest.TestCase):
    def test_compute_statistics_values(self) -> None:
        columns = {"A": pd.Series([1.0, 2.0, 3.0, 4.0])}
        stats = statistics_service.compute_statistics(columns, decimal_places=4)
        row = stats.loc["A"]
        self.assertEqual(row["Count"], 4)
        self.assertEqual(row["Min"], 1.0)
        self.assertEqual(row["Max"], 4.0)
        self.assertEqual(row["Mean"], 2.5)
        self.assertEqual(row["Peak-to-Peak"], 3.0)

    def test_compute_statistics_rows_are_naturally_sorted(self) -> None:
        columns = {
            "TC10": pd.Series([1.0]),
            "B": pd.Series([1.0]),
            "TC2": pd.Series([1.0]),
        }

        stats = statistics_service.compute_statistics(columns)

        self.assertEqual(list(stats.index), ["B", "TC2", "TC10"])


class CursorServiceTests(unittest.TestCase):
    def _xy(self):
        x = pd.Series([0.0, 1.0, 2.0, 3.0])
        y_map = {"A": pd.Series([10.0, 20.0, 30.0, 40.0])}
        return x, y_map

    def test_nearest_point_snaps_to_sample(self) -> None:
        x, y_map = self._xy()
        point = cursor_service.nearest_point(x, y_map, 1.4)
        assert point is not None
        self.assertEqual(point["x"], 1.0)
        self.assertEqual(point["values"]["A"], 20.0)

    def test_nearest_point_empty(self) -> None:
        self.assertIsNone(cursor_service.nearest_point(pd.Series(dtype=float), {}, 0.0))


class PlotProfileServiceTests(unittest.TestCase):
    def test_add_profile_uses_unique_name_and_supplied_x_column(self) -> None:
        update = plot_profile_service.add_profile(
            [{"name": "Plot 1"}],
            0,
            name="",
            x_column="Time",
        )

        self.assertTrue(update.result.ok)
        self.assertEqual(update.active_index, 1)
        self.assertEqual(update.result.payload, 1)
        self.assertEqual([profile["name"] for profile in update.profiles], ["Plot 1", "Plot 2"])
        self.assertEqual(update.profiles[1]["x_column"], "Time")

    def test_duplicate_rename_delete_preserve_active_index_rules(self) -> None:
        profiles = [{"name": "Plot 1"}, {"name": "Plot 2"}]

        duplicate = plot_profile_service.duplicate_profile(profiles, 0, index=0)
        self.assertTrue(duplicate.result.ok)
        self.assertEqual(duplicate.active_index, 1)
        self.assertEqual(duplicate.profiles[1]["name"], "Plot 1 Copy")

        rename = plot_profile_service.rename_profile(duplicate.profiles, duplicate.active_index, 1, "Renamed")
        self.assertTrue(rename.result.ok)
        self.assertEqual(rename.profiles[1]["name"], "Renamed")
        self.assertFalse(plot_profile_service.rename_profile(rename.profiles, 1, 1, "Plot 1").result.ok)

        delete = plot_profile_service.delete_profile(rename.profiles, rename.active_index, index=1)
        self.assertTrue(delete.result.ok)
        self.assertEqual(delete.active_index, 1)
        self.assertEqual([profile["name"] for profile in delete.profiles], ["Plot 1", "Plot 2"])

    def test_select_rejects_out_of_range_without_losing_profiles(self) -> None:
        profiles = [{"name": "Plot 1"}]

        update = plot_profile_service.select_profile(profiles, 0, 99)

        self.assertFalse(update.result.ok)
        self.assertEqual(update.active_index, 0)
        self.assertEqual(update.profiles[0]["name"], "Plot 1")

    def test_legend_override_normalises_aliases_and_preserves_existing_style(self) -> None:
        key = plot_render_service.normalise_channel_name("Motor Voltage")
        profiles = [
            {
                "name": "Plot 1",
                "y_columns": ["Motor Voltage"],
                "legend": {
                    "channel_overrides": {
                        key: {"channel": "Motor Voltage", "colour": "#123456", "line_style": "--"}
                    }
                },
            }
        ]

        result = plot_profile_service.update_legend_channel_override(
            profiles,
            0,
            "Motor Voltage",
            {"hidden": True, "plot_kind": "Line + Marker", "marker_face_color": "#ABCDEF"},
        )

        self.assertTrue(result.ok, result.message)
        style = profiles[0]["legend"]["channel_overrides"][key]
        self.assertEqual(style["colour"], "#123456")
        self.assertEqual(style["line_style"], "--")
        self.assertEqual(style["hidden"], "true")
        self.assertEqual(style["plot_kind"], "Line + Markers")
        self.assertEqual(style["marker_face_colour"], "#ABCDEF")

    def test_legend_colour_override_propagates_to_matching_profiles(self) -> None:
        profiles = [
            {"name": "Plot 1", "y_columns": ["Motor Voltage"]},
            {"name": "Plot 2", "secondary_y_columns": [" motor voltage "]},
            {"name": "Plot 3", "y_columns": ["Motor Current"]},
        ]

        result = plot_profile_service.update_legend_channel_override(
            profiles,
            0,
            "Motor Voltage",
            {"label": "Voltage", "colour": "#123456"},
        )

        self.assertTrue(result.ok, result.message)
        key = plot_render_service.normalise_channel_name("Motor Voltage")
        self.assertEqual(profiles[0]["legend"]["channel_overrides"][key]["label"], "Voltage")
        self.assertEqual(profiles[1]["legend"]["channel_overrides"][key]["colour"], "#123456")
        self.assertNotIn("legend", profiles[2])
        self.assertEqual(plot_profile_service.legend_channel_colour_overrides(profiles)[key], "#123456")

    def test_capture_working_profile_merges_legend_and_preserves_existing_annotations_when_none(self) -> None:
        key = plot_render_service.normalise_channel_name("A")
        existing = {
            "name": "Plot 1",
            "legend": {"display_mode": "panel", "channel_overrides": {key: {"channel": "A", "colour": "#123456"}}},
            "annotations": [{"id": "ann_001", "type": "text", "text": "Note", "x": 1.0, "y": 2.0}],
        }

        profile = plot_profile_service.capture_working_profile(
            existing,
            0,
            x_column="Time",
            y_columns=["A"],
            legend_settings={"display_mode": "graph"},
            limit_lines=[{"name": "Limit", "points": []}],
            engineering_notes={"objective": "Verify"},
        )

        self.assertEqual(profile["x_column"], "Time")
        self.assertEqual(profile["legend"]["display_mode"], "graph")
        self.assertEqual(profile["legend"]["channel_overrides"][key]["colour"], "#123456")
        self.assertEqual(profile["annotations"][0]["text"], "Note")
        self.assertEqual(profile["limit_lines"][0]["name"], "Limit")
        self.assertEqual(profile["engineering_notes"]["objective"], "Verify")

    def test_comparison_frame_empty(self) -> None:
        frame = cursor_service.cursor_comparison_frame([])
        self.assertTrue(frame.empty)
        self.assertIn("Type", frame.columns)

    def test_comparison_frame_with_delta(self) -> None:
        points = [
            {"point_no": 1, "index": 0, "x": 0.0, "values": {"A": 10.0}},
            {"point_no": 2, "index": 2, "x": 2.0, "values": {"A": 30.0}},
        ]
        frame = cursor_service.cursor_comparison_frame(points, decimals=2)
        self.assertEqual(len(frame), 3)  # 2 points + 1 delta row
        delta_row = frame.iloc[2]
        self.assertEqual(delta_row["Type"], "\u0394 vs P1")
        self.assertEqual(delta_row["A"], "20.00")
        self.assertEqual(delta_row["X / \u0394X"], "2.00")

    def test_comparison_frame_channel_columns_are_naturally_sorted(self) -> None:
        points = [
            {"point_no": 1, "index": 0, "x": 0.0, "values": {"TC10": 10.0, "TC2": 2.0, "A": 1.0}},
        ]

        frame = cursor_service.cursor_comparison_frame(points)

        self.assertEqual(list(frame.columns[4:]), ["A", "TC2", "TC10"])

    def test_empty_series_skipped(self) -> None:
        columns = {"A": pd.Series([np.nan, np.nan])}
        stats = statistics_service.compute_statistics(columns)
        self.assertNotIn("A", stats.index)

    def test_individual_helpers(self) -> None:
        series = pd.Series([1.0, 2.0, 3.0])
        self.assertEqual(statistics_service.count(series), 3)
        self.assertEqual(statistics_service.mean(series), 2.0)
        self.assertEqual(statistics_service.peak_to_peak(series), 2.0)
        self.assertAlmostEqual(statistics_service.rms(series), float(np.sqrt((1 + 4 + 9) / 3)))

    def test_selected_xy_ranges_excludes_secondary(self) -> None:
        data = PlotData(
            x=pd.Series([0.0, 1.0, 2.0]),
            y_map={"A": pd.Series([10.0, 20.0, 30.0]), "B": pd.Series([100.0, 200.0, 300.0])},
            x_map=None,
        )
        x_range, y_range = statistics_service.selected_xy_ranges(data, secondary_y={"B"})
        self.assertEqual(x_range, (0.0, 2.0))
        self.assertEqual(y_range, (10.0, 30.0))


class LimitsServiceTests(unittest.TestCase):
    def test_normalise_sorts_points(self) -> None:
        lines = [{"name": "L", "points": [{"x": 5, "y": 1}, {"x": 1, "y": 2}]}]
        normalised = limits_service.normalise_limit_lines(lines)
        self.assertEqual([p["x"] for p in normalised[0]["points"]], [1.0, 5.0])

    def test_active_limit_ranges(self) -> None:
        lines = limits_service.normalise_limit_lines(
            [{"name": "L", "applies_to": "All selected Y channels", "points": [{"x": 0, "y": 1}, {"x": 10, "y": 5}]}]
        )
        x_range, y_range = limits_service.active_limit_ranges(lines, selected_y=set())
        self.assertEqual(x_range, (0.0, 10.0))
        self.assertEqual(y_range, (1.0, 5.0))

    def test_upper_limit_pass_and_fail(self) -> None:
        data = PlotData(x=pd.Series([0.0, 1.0, 2.0]), y_map={"Sig": pd.Series([1.0, 2.0, 3.0])}, x_map=None)
        passing = limits_service.normalise_limit_lines(
            [{"name": "Max", "type": "Upper Limit", "points": [{"x": 0, "y": 10}, {"x": 2, "y": 10}]}]
        )
        summary = limits_service.compute_limit_margins(data, passing)
        self.assertTrue(summary.any_result)
        self.assertEqual(summary.rows[0].status, "PASS")

        failing = limits_service.normalise_limit_lines(
            [{"name": "Max", "type": "Upper Limit", "points": [{"x": 0, "y": 1.5}, {"x": 2, "y": 1.5}]}]
        )
        self.assertEqual(limits_service.compute_limit_margins(data, failing).rows[0].status, "FAIL")

    def test_limit_margin_reports_first_interpolated_failure(self) -> None:
        data = PlotData(
            x=pd.Series([0.0, 20.0, 26.0, 30.0]),
            y_map={"Sig": pd.Series([5.0, 18.0, 27.0, 35.0])},
            x_map=None,
        )
        lines = limits_service.normalise_limit_lines(
            [
                {
                    "name": "Max",
                    "type": "Upper Limit",
                    "points": [{"x": 0, "y": 10}, {"x": 20, "y": 20}, {"x": 30, "y": 30}],
                }
            ]
        )

        row = limits_service.compute_limit_margins(data, lines).rows[0]

        self.assertEqual(row.status, "FAIL")
        self.assertIn("minimum margin below upper limit = -5 at X = 30", row.message)
        self.assertIn("first failure at X = 26", row.message)
        self.assertIn("data = 27, limit = 26", row.message)

    def test_limit_margin_uses_channel_specific_x_map(self) -> None:
        data = PlotData(
            x=pd.Series([100.0, 101.0, 102.0]),
            y_map={"Sig": pd.Series([5.0, 12.0, 9.0])},
            x_map={"Sig": pd.Series([0.0, 1.0, 2.0])},
        )
        lines = limits_service.normalise_limit_lines(
            [{"name": "Max", "type": "Upper Limit", "points": [{"x": 0, "y": 10}, {"x": 2, "y": 10}]}]
        )

        row = limits_service.compute_limit_margins(data, lines).rows[0]

        self.assertEqual(row.status, "FAIL")
        self.assertIn("first failure at X = 1", row.message)

    def test_limit_margin_warns_when_pass_margin_is_within_five_percent(self) -> None:
        data = PlotData(x=pd.Series([0.0, 1.0]), y_map={"Sig": pd.Series([96.0, 96.0])}, x_map=None)
        lines = limits_service.normalise_limit_lines(
            [{"name": "Max", "type": "Upper Limit", "points": [{"x": 0, "y": 100}, {"x": 1, "y": 100}]}]
        )

        summary = limits_service.compute_limit_margins(data, lines)
        row = summary.rows[0]
        table_row = summary.to_table_rows()[0]

        self.assertEqual(row.status, "PASS")
        self.assertEqual(row.severity, "WARN")
        self.assertEqual(table_row["Status"], "PASS")
        self.assertEqual(table_row["Severity"], "WARN")
        self.assertAlmostEqual(table_row["Margin %"], 4.166666666666666)

    def test_margin_table_rows_are_naturally_sorted_by_limit_and_channel(self) -> None:
        summary = limits_service.LimitMarginSummary(
            rows=[
                limits_service.LimitMarginRow("Limit B", "TC10", "PASS", "ok"),
                limits_service.LimitMarginRow("Limit A", "TC10", "PASS", "ok"),
                limits_service.LimitMarginRow("Limit A", "TC2", "PASS", "ok"),
            ]
        )

        labels = [(row["Limit"], row["Channel"]) for row in summary.to_table_rows()]

        self.assertEqual(labels, [("Limit A", "TC2"), ("Limit A", "TC10"), ("Limit B", "TC10")])

    def test_summary_text_header_and_skip(self) -> None:
        data = PlotData(x=pd.Series([0.0, 1.0]), y_map={"Sig": pd.Series([1.0, 2.0])}, x_map=None)
        lines = limits_service.normalise_limit_lines([{"name": "OnePoint", "points": [{"x": 0, "y": 1}]}])
        text = limits_service.calculate_limit_margins_text(data, lines)
        self.assertIn("MARGIN-TO-LIMIT SUMMARY", text)
        self.assertIn("OnePoint: not evaluated", text)
        self.assertIn("No limit margins were calculated", text)


class MathsChannelServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.df = pd.DataFrame({"A": [1.0, 2.0, 3.0], "B": [4.0, 5.0, 6.0]})

    def test_basic_formula(self) -> None:
        evaluator = MathsChannelEvaluator(self.df)
        series, referenced = evaluator.evaluate("A + B")
        self.assertEqual(list(series), [5.0, 7.0, 9.0])
        self.assertCountEqual(referenced, ["A", "B"])

    def test_backtick_columns(self) -> None:
        df = pd.DataFrame({"Inlet Pressure": [10.0, 20.0], "Outlet Pressure": [5.0, 5.0]})
        series, _ = MathsChannelEvaluator(df).evaluate("`Inlet Pressure` - `Outlet Pressure`")
        self.assertEqual(list(series), [5.0, 15.0])

    def test_rolling_mean_function(self) -> None:
        series, _ = MathsChannelEvaluator(self.df).evaluate("rolling_mean(A, 2)")
        self.assertAlmostEqual(series.iloc[1], 1.5)

    def test_self_reference_blocked(self) -> None:
        with self.assertRaises(ValueError):
            MathsChannelEvaluator(self.df).evaluate("A + 1", blocked_names={"A"})

    def test_unknown_column_raises(self) -> None:
        with self.assertRaises(ValueError):
            MathsChannelEvaluator(self.df).evaluate("Nonexistent + 1")

    def test_disallowed_call_raises(self) -> None:
        with self.assertRaises(ValueError):
            MathsChannelEvaluator(self.df).evaluate("eval(A)")

    def test_normalise_definitions_drops_invalid(self) -> None:
        raw = {
            "Power": {"name": "Power", "formula": "A * B"},
            "Broken": {"name": "Broken"},
        }
        normalised = maths_channel_service.normalise_calculated_channel_definitions(raw)
        self.assertIn("Power", normalised)
        self.assertNotIn("Broken", normalised)
        self.assertEqual(normalised["Power"]["enabled"], True)


class PlottingDataServiceTests(unittest.TestCase):
    def test_prepare_plot_series_without_filter_does_not_import_scipy_signal(self) -> None:
        script = """
import sys

import pandas as pd

from test_data_analyser.domain import PlotData
from test_data_analyser.services.plotting_data_service import prepare_plot_series

data = PlotData(
    x=pd.Series([0.0, 1.0, 2.0]),
    y_map={"A": pd.Series([10.0, 11.0, 12.0])},
    x_map={"A": pd.Series([0.0, 1.0, 2.0])},
)
result = prepare_plot_series(data, use_filter=False)
if not result.ok:
    raise SystemExit(result.message)
raise SystemExit(1 if "scipy.signal" in sys.modules else 0)
"""
        completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_analysis_window_masks_values(self) -> None:
        x = pd.Series([0.0, 1.0, 2.0, 3.0])
        y_map = {"A": pd.Series([10.0, 11.0, 12.0, 13.0])}
        x_map = {"A": x.copy()}
        result = plotting_data_service.apply_analysis_window(x, y_map, x_map, xmin=1.0, xmax=2.0)
        kept = result.y_map["A"].dropna()
        self.assertEqual(list(kept), [11.0, 12.0])

    def test_invalid_window_raises(self) -> None:
        x = pd.Series([0.0, 1.0])
        with self.assertRaises(ValueError):
            plotting_data_service.apply_analysis_window(x, {"A": x}, {"A": x}, xmin=5.0, xmax=1.0)

    def test_no_window_returns_all(self) -> None:
        x = pd.Series([0.0, 1.0, 2.0])
        result = plotting_data_service.apply_analysis_window(x, {"A": x}, {"A": x}, xmin=None, xmax=None)
        self.assertEqual(len(result.y_map["A"].dropna()), 3)


class PlotRenderServiceTests(unittest.TestCase):
    def test_polynomial_best_fit_returns_formula(self) -> None:
        fit = plot_render_service.polynomial_best_fit([0.0, 1.0, 2.0], [1.0, 3.0, 5.0], 1, sample_count=3)

        self.assertIsNotNone(fit)
        assert fit is not None
        self.assertEqual(len(fit["x"]), 3)
        self.assertEqual(len(fit["y"]), 3)
        self.assertIn("y =", fit["formula"])
        self.assertIn("2x", fit["formula"])

    def test_best_fit_settings_are_limited_and_deduplicated(self) -> None:
        raw_settings = [
            {"channel": "A", "fit_type": "Polynomial", "order": 99},
            {"channel": " a ", "fit_type": "Linear", "order": 1},
        ]
        raw_settings.extend({"channel": f"C{index}", "fit_type": "Squared", "order": 2} for index in range(6))

        settings = plot_render_service.normalise_best_fit_settings(
            raw_settings
        )

        self.assertEqual(len(settings), 5)
        self.assertEqual(settings[0]["channel"], "A")
        self.assertEqual(settings[0]["order"], plot_render_service.MAX_BEST_FIT_ORDER)

    def test_resolve_axis_range_applies_full_and_partial_manual_limits(self) -> None:
        self.assertEqual(plot_render_service.resolve_axis_range((0.0, 10.0), 1.0, 9.0), (1.0, 9.0))
        self.assertEqual(plot_render_service.resolve_axis_range((0.0, 10.0), None, 8.0), (0.0, 8.0))
        self.assertEqual(plot_render_service.resolve_axis_range((0.0, 10.0), 2.0, None), (2.0, 10.0))

    def test_resolve_axis_range_ignores_empty_or_inverted_limits(self) -> None:
        self.assertIsNone(plot_render_service.resolve_axis_range((0.0, 10.0), None, None))
        self.assertIsNone(plot_render_service.resolve_axis_range((0.0, 10.0), 10.0, 1.0))
        self.assertIsNone(plot_render_service.resolve_axis_range((0.0, 10.0), 5.0, 5.0))

    def test_apply_channel_style_overrides_updates_label_plot_kind_colour_and_hidden_state(self) -> None:
        items = [
            {"channel": "A", "label": "A", "secondary": False},
            {"channel": "B", "label": "B [Right Y]", "secondary": True},
        ]
        styles = {
            "a": {"channel": "A", "name": "Pump Pressure", "color": "#123456", "plot_kind": "Scatter"},
            "b": {"channel": "B", "label": "Flow", "hidden": "true", "plot_kind": "Line + Marker"},
        }

        styled = plot_render_service.apply_channel_style_overrides(items, styles, "Line")

        self.assertEqual(styled[0]["label"], "Pump Pressure")
        self.assertEqual(styled[0]["colour"], "#123456")
        self.assertEqual(styled[0]["plot_kind"], "Scatter")
        self.assertTrue(styled[0]["label_overridden"])
        self.assertEqual(styled[1]["label"], "Flow [Right Y]")
        self.assertTrue(styled[1]["hidden"])
        self.assertEqual(styled[1]["plot_kind"], "Line + Markers")

    def test_apply_channel_style_overrides_uses_default_plot_kind_for_invalid_styles(self) -> None:
        styled = plot_render_service.apply_channel_style_overrides(
            [{"channel": "A", "label": "A", "secondary": False}],
            {"a": {"channel": "A", "plot_kind": "Bars"}},
            "Line + Markers",
        )

        self.assertEqual(styled[0]["plot_kind"], "Line + Markers")
        self.assertFalse(styled[0]["plot_kind_overridden"])

    def test_eaton_colours_do_not_import_matplotlib_pyplot(self) -> None:
        script = """
import sys

from test_data_analyser.services.plot_render_service import resolve_plot_colours

colours = resolve_plot_colours("eaton")
if not colours:
    raise SystemExit("Expected Eaton colours")
raise SystemExit(1 if "matplotlib.pyplot" in sys.modules else 0)
"""
        completed = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def test_colour_cycle_registry_lists_defaults_and_allows_internal_extensions(self) -> None:
        self.assertEqual(
            plot_render_service.available_colour_cycles()[:3],
            ["eaton", "matplotlib", "colourblind_safe"],
        )
        plot_render_service.register_colour_cycle("phase9_test", lambda: ["#111111", "#222222"], replace=True)

        self.assertEqual(plot_render_service.resolve_plot_colours("phase9_test"), ["#111111", "#222222"])

    def test_colour_cycle_registry_rejects_duplicate_names_by_default(self) -> None:
        with self.assertRaises(ValueError):
            plot_render_service.register_colour_cycle("eaton", lambda: ["#000000"])

    def test_unknown_or_empty_colour_cycle_falls_back_to_eaton(self) -> None:
        plot_render_service.register_colour_cycle("phase9_empty", lambda: [], replace=True)

        self.assertEqual(plot_render_service.resolve_plot_colours("missing"), list(EATON_PLOT_COLORS))
        self.assertEqual(plot_render_service.resolve_plot_colours("phase9_empty"), list(EATON_PLOT_COLORS))

    def test_persistent_channel_colours_empty_for_single_plot(self) -> None:
        mapping = plot_render_service.persistent_channel_colour_map(
            [["Voltage A", "Current A", "Pressure A"]],
            ["red", "blue", "green"],
        )
        self.assertEqual(mapping, {})

    def test_persistent_channel_colours_normalise_partial_repeats(self) -> None:
        mapping = plot_render_service.persistent_channel_colour_map(
            [
                ["Motor Voltage", "Motor Current", "Outlet Pressure"],
                [" motor voltage ", "MOTOR CURRENT", "Flow Rate"],
            ],
            ["red", "blue", "green"],
        )
        self.assertEqual(mapping[plot_render_service.normalise_channel_name("Motor Voltage")], "red")
        self.assertEqual(mapping[plot_render_service.normalise_channel_name("Motor Current")], "blue")
        self.assertNotIn(plot_render_service.normalise_channel_name("Outlet Pressure"), mapping)
        self.assertNotIn(plot_render_service.normalise_channel_name("Flow Rate"), mapping)

    def test_persistent_channel_colours_keep_same_engineering_type_distinct(self) -> None:
        mapping = plot_render_service.persistent_channel_colour_map(
            [
                ["Supply Voltage", "Motor Voltage", "Control Voltage"],
                ["Supply Voltage", "Motor Voltage", "Control Voltage"],
            ],
            ["red", "blue", "green"],
        )
        colours = [
            mapping[plot_render_service.normalise_channel_name("Supply Voltage")],
            mapping[plot_render_service.normalise_channel_name("Motor Voltage")],
            mapping[plot_render_service.normalise_channel_name("Control Voltage")],
        ]
        self.assertEqual(colours, ["red", "blue", "green"])
        self.assertEqual(len(set(colours)), 3)


class RawDataServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.df = pd.DataFrame({"Time": [0.0, 1.0, 2.0], "Sig": [10.0, 20.0, 30.0]})

    def test_parse_row_limit(self) -> None:
        self.assertIsNone(raw_data_service.parse_row_limit("All"))
        self.assertIsNone(raw_data_service.parse_row_limit(""))
        self.assertEqual(raw_data_service.parse_row_limit("1,000"), 1000)
        with self.assertRaises(ValueError):
            raw_data_service.parse_row_limit("abc")

    def test_select_frame_columns(self) -> None:
        frame, removed = raw_data_service.select_raw_data_frame(
            self.df,
            "Time",
            ["Sig"],
            apply_window=False,
            xmin=None,
            xmax=None,
            drop_blank=False,
            get_numeric=lambda col: pd.to_numeric(self.df[col]),
        )
        self.assertEqual(list(frame.columns), ["Time", "Sig"])
        self.assertEqual(removed, 0)

    def test_select_frame_applies_window(self) -> None:
        frame, _ = raw_data_service.select_raw_data_frame(
            self.df,
            "Time",
            ["Sig"],
            apply_window=True,
            xmin=1.0,
            xmax=2.0,
            drop_blank=False,
            get_numeric=lambda col: pd.to_numeric(self.df[col]),
        )
        self.assertEqual(list(frame["Time"]), [1.0, 2.0])

    def test_coerce_edit_value(self) -> None:
        self.assertTrue(np.isnan(raw_data_service.coerce_raw_edit_value(self.df, "Sig", "")))
        self.assertEqual(raw_data_service.coerce_raw_edit_value(self.df, "Sig", "42"), 42.0)
        with self.assertRaises(ValueError):
            raw_data_service.coerce_raw_edit_value(self.df, "Sig", "not-a-number")


class RawDataSortTests(unittest.TestCase):
    def test_numeric_sort_preserves_original_index(self) -> None:
        frame = pd.DataFrame({"V": [30.0, 10.0, 20.0]}, index=[2, 5, 8])
        ascending = raw_data_service.sort_display_frame(frame, "V", True)
        self.assertEqual(list(ascending["V"]), [10.0, 20.0, 30.0])
        self.assertEqual(list(ascending.index), [5, 8, 2])
        descending = raw_data_service.sort_display_frame(frame, "V", False)
        self.assertEqual(list(descending["V"]), [30.0, 20.0, 10.0])

    def test_text_sort_is_natural(self) -> None:
        frame = pd.DataFrame({"Ch": ["TC10", "TC2", "TC1"]})
        result = raw_data_service.sort_display_frame(frame, "Ch", True)
        self.assertEqual(list(result["Ch"]), ["TC1", "TC2", "TC10"])

    def test_nan_sinks_to_bottom_in_both_directions(self) -> None:
        frame = pd.DataFrame({"V": [2.0, np.nan, 1.0]})
        ascending = raw_data_service.sort_display_frame(frame, "V", True)
        self.assertEqual(list(ascending["V"])[:2], [1.0, 2.0])
        self.assertTrue(np.isnan(list(ascending["V"])[2]))
        descending = raw_data_service.sort_display_frame(frame, "V", False)
        self.assertEqual(list(descending["V"])[:2], [2.0, 1.0])
        self.assertTrue(np.isnan(list(descending["V"])[2]))

    def test_blank_text_sinks_and_index_preserved(self) -> None:
        frame = pd.DataFrame({"Ch": ["B", "", "A"]}, index=[10, 11, 12])
        result = raw_data_service.sort_display_frame(frame, "Ch", True)
        self.assertEqual(list(result["Ch"]), ["A", "B", ""])
        self.assertEqual(list(result.index), [12, 10, 11])

    def test_unknown_column_returns_frame_unchanged(self) -> None:
        frame = pd.DataFrame({"V": [1.0, 2.0]})
        result = raw_data_service.sort_display_frame(frame, "Missing", True)
        self.assertTrue(result.equals(frame))


class RawDataFilterTests(unittest.TestCase):
    def setUp(self) -> None:
        self.frame = pd.DataFrame(
            {"V": [1.0, 5.0, 10.0, 50.0], "Name": ["alpha", "Beta", "gamma", "delta"]},
            index=[100, 101, 102, 103],
        )

    def test_substring_is_case_insensitive(self) -> None:
        result = raw_data_service.filter_display_frame(self.frame, {"Name": "ET"})
        self.assertEqual(list(result["Name"]), ["Beta"])

    def test_greater_than(self) -> None:
        result = raw_data_service.filter_display_frame(self.frame, {"V": ">5"})
        self.assertEqual(list(result["V"]), [10.0, 50.0])
        self.assertEqual(list(result.index), [102, 103])

    def test_less_than_or_equal(self) -> None:
        result = raw_data_service.filter_display_frame(self.frame, {"V": "<=10"})
        self.assertEqual(list(result["V"]), [1.0, 5.0, 10.0])

    def test_range_inclusive(self) -> None:
        result = raw_data_service.filter_display_frame(self.frame, {"V": "5..10"})
        self.assertEqual(list(result["V"]), [5.0, 10.0])

    def test_equality(self) -> None:
        result = raw_data_service.filter_display_frame(self.frame, {"V": "=10"})
        self.assertEqual(list(result["V"]), [10.0])

    def test_blank_filter_is_noop(self) -> None:
        result = raw_data_service.filter_display_frame(self.frame, {"V": "  "})
        self.assertEqual(len(result), 4)


class ClipboardServiceTests(unittest.TestCase):
    def test_selection_to_tsv_round_trip(self) -> None:
        values = [["1", "2"], ["3", "4"]]
        tsv = clipboard_service.selection_to_tsv(values)
        self.assertEqual(tsv, "1\t2\n3\t4")
        self.assertEqual(clipboard_service.tsv_to_values(tsv), values)

    def test_selection_to_tsv_blanks_none_and_nan(self) -> None:
        tsv = clipboard_service.selection_to_tsv([[1.0, None], [float("nan"), "x"]])
        self.assertEqual(tsv, "1.0\t\n\tx")

    def test_tsv_to_values_drops_trailing_newline_row(self) -> None:
        self.assertEqual(clipboard_service.tsv_to_values("a\tb\n"), [["a", "b"]])
        self.assertEqual(clipboard_service.tsv_to_values("a\tb\r\nc\td"), [["a", "b"], ["c", "d"]])
        self.assertEqual(clipboard_service.tsv_to_values(""), [])

    def test_infer_column_type(self) -> None:
        self.assertEqual(clipboard_service.infer_column_type(["1", "2", ""]), "numeric")
        self.assertEqual(clipboard_service.infer_column_type(["1", "abc"]), "text")
        self.assertEqual(clipboard_service.infer_column_type(["", ""]), "numeric")

    def test_coerce_pasted_block_numeric_and_text(self) -> None:
        from test_data_analyser.domain import ColumnSpec

        numeric = ColumnSpec(id="c1", display_name="N", data_type="numeric")
        text = ColumnSpec(id="c2", display_name="T", data_type="text")
        values = [["10", "hello"], ["bad", "world"]]

        coerced, warnings = clipboard_service.coerce_pasted_block(values, [numeric, text])

        self.assertEqual(coerced[0][0], 10.0)
        self.assertEqual(coerced[0][1], "hello")
        self.assertEqual(coerced[1][0], "bad")
        self.assertEqual(len(warnings), 1)
        self.assertIn("numeric column 'N'", warnings[0])

    def test_coerce_pasted_block_keeps_overflow_columns_as_text(self) -> None:
        from test_data_analyser.domain import ColumnSpec

        numeric = ColumnSpec(id="c1", display_name="N", data_type="numeric")
        coerced, warnings = clipboard_service.coerce_pasted_block([["1", "extra"]], [numeric])

        self.assertEqual(coerced[0][0], 1.0)
        self.assertEqual(coerced[0][1], "extra")
        self.assertEqual(warnings, [])


class FindReplaceServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.df = pd.DataFrame({"A": [1.5, 2.0, 15.0], "Name": ["alpha", "Alpha", "beta"]})

    def test_find_substring_default_case_insensitive(self) -> None:
        matches = find_replace_service.find_matches(self.df, "alpha")
        self.assertEqual(len(matches), 2)
        self.assertEqual({m.column for m in matches}, {"Name"})

    def test_find_case_sensitive(self) -> None:
        matches = find_replace_service.find_matches(self.df, "alpha", case_sensitive=True)
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].value, "alpha")

    def test_find_numeric_by_string_representation(self) -> None:
        matches = find_replace_service.find_matches(self.df, "1.5", columns=["A"])
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].row, 0)

    def test_find_regex(self) -> None:
        matches = find_replace_service.find_matches(self.df, r"^1", regex=True, columns=["A"])
        self.assertEqual({m.row for m in matches}, {0, 2})

    def test_find_column_scoping(self) -> None:
        matches = find_replace_service.find_matches(self.df, "a", columns=["Name"])
        self.assertTrue(all(m.column == "Name" for m in matches))

    def test_apply_replacements_uses_write_and_collects_warnings(self) -> None:
        df = self.df.copy()
        writes: list[tuple] = []

        def write(row, column, new_text):
            writes.append((row, column, new_text))
            return OperationResult.success(warnings=["w"] if new_text == "BETA" else None)

        matches = find_replace_service.find_matches(df, "beta")
        summary = find_replace_service.apply_replacements(df, matches, "BETA", query="beta", write=write)

        self.assertEqual(summary.replaced, 1)
        self.assertEqual(writes[0][2], "BETA")
        self.assertEqual(summary.warnings, ["w"])

    def test_invalid_regex_raises(self) -> None:
        with self.assertRaises(re.error):
            find_replace_service.find_matches(self.df, "(", regex=True)


class FillSeriesServiceTests(unittest.TestCase):
    def test_constant_fill(self) -> None:
        pattern = fill_series_service.infer_fill_pattern([5.0, 5.0, 5.0])
        self.assertEqual(pattern.kind, "constant")
        self.assertEqual(fill_series_service.generate_fill(pattern, 3), [5.0, 5.0, 5.0])

    def test_linear_fill(self) -> None:
        pattern = fill_series_service.infer_fill_pattern([1.0, 2.0, 3.0])
        self.assertEqual(pattern.kind, "linear")
        self.assertEqual(fill_series_service.generate_fill(pattern, 4), [4.0, 5.0, 6.0, 7.0])

    def test_repeat_fill_for_non_linear(self) -> None:
        pattern = fill_series_service.infer_fill_pattern([1.0, 4.0, 9.0])
        self.assertEqual(pattern.kind, "repeat")
        self.assertEqual(fill_series_service.generate_fill(pattern, 4), [1.0, 4.0, 9.0, 1.0])

    def test_text_values_repeat_verbatim(self) -> None:
        pattern = fill_series_service.infer_fill_pattern(["a", "b"])
        self.assertEqual(pattern.kind, "repeat")
        self.assertEqual(fill_series_service.generate_fill(pattern, 3), ["a", "b", "a"])

    def test_single_value_is_constant(self) -> None:
        pattern = fill_series_service.infer_fill_pattern([7.0])
        self.assertEqual(fill_series_service.generate_fill(pattern, 2), [7.0, 7.0])


class BatchImportServiceTests(unittest.TestCase):
    def test_discover_with_glob_and_natural_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            for name in ["Run2.csv", "Run10.csv", "notes.txt", "data.xlsx"]:
                Path(directory, name).write_text("x", encoding="utf-8")
            found = batch_import_service.discover_data_files(directory, glob="*.csv;*.xlsx")
            names = [path.name for path in found]
            self.assertIn("Run2.csv", names)
            self.assertIn("data.xlsx", names)
            self.assertNotIn("notes.txt", names)
            self.assertLess(names.index("Run2.csv"), names.index("Run10.csv"))

    def test_discover_recursive(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sub = Path(directory, "sub")
            sub.mkdir()
            Path(sub, "a.csv").write_text("x", encoding="utf-8")
            self.assertEqual(batch_import_service.discover_data_files(directory, glob="*.csv"), [])
            recursive = batch_import_service.discover_data_files(directory, glob="*.csv", recursive=True)
            self.assertEqual([path.name for path in recursive], ["a.csv"])

    def test_extract_run_name_default_stem(self) -> None:
        self.assertEqual(batch_import_service.extract_run_name("x/Run_SN13260599.csv"), "Run_SN13260599")

    def test_extract_run_name_regex_group(self) -> None:
        self.assertEqual(
            batch_import_service.extract_run_name("Run_SN13260599.csv", regex=r"SN(\d+)"), "13260599"
        )

    def test_extract_run_name_invalid_regex_falls_back(self) -> None:
        self.assertEqual(batch_import_service.extract_run_name("Run1.csv", regex="("), "Run1")


class LimitTemplatesServiceTests(unittest.TestCase):
    def test_round_trip_preserves_fields(self) -> None:
        lines = [
            {
                "name": "Upper",
                "type": "Upper Limit",
                "applies_to": "Pressure",
                "color": "#FF0000",
                "points": [{"x": 0.0, "y": 10.0}, {"x": 5.0, "y": 12.0}],
            }
        ]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "template.json")
            limit_templates_service.save_limit_template(path, lines)
            loaded = limit_templates_service.load_limit_template(path)

        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0]["name"], "Upper")
        self.assertEqual(loaded[0]["type"], "Upper Limit")
        self.assertEqual(loaded[0]["applies_to"], "Pressure")
        self.assertEqual(loaded[0]["color"], "#FF0000")
        self.assertEqual(loaded[0]["points"], [{"x": 0.0, "y": 10.0}, {"x": 5.0, "y": 12.0}])

    def test_load_missing_key_returns_empty(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory, "empty.json")
            path.write_text("{}", encoding="utf-8")
            self.assertEqual(limit_templates_service.load_limit_template(path), [])


class PeakDetectionServiceTests(unittest.TestCase):
    def test_finds_sine_peaks(self) -> None:
        x = np.linspace(0, 4 * np.pi, 400)
        peaks = peak_detection_service.find_peaks(x, np.sin(x))
        self.assertEqual(len([peak for peak in peaks if not peak.is_trough]), 2)

    def test_prominence_filters_small_bumps(self) -> None:
        x = np.arange(7, dtype=float)
        y = np.array([0, 5, 0, 1, 0, 5, 0], dtype=float)
        self.assertEqual(len(peak_detection_service.find_peaks(x, y, prominence=0.5)), 3)
        self.assertEqual(len(peak_detection_service.find_peaks(x, y, prominence=2.0)), 2)

    def test_troughs_flag(self) -> None:
        x = np.linspace(0, 2 * np.pi, 200)
        peaks = peak_detection_service.find_peaks(x, np.sin(x), find_troughs=True)
        self.assertTrue(any(peak.is_trough for peak in peaks))




class RunComparisonServiceTests(unittest.TestCase):
    def _runs(self) -> list[dict]:
        return [
            {"name": "Run 1", "enabled": True, "df": pd.DataFrame({"Time": [0.0, 1.0, 2.0], "Sig": [1.0, 2.0, 3.0]}), "colour": "#007AC2"},
            {"name": "Run 2", "enabled": False, "df": pd.DataFrame({"Time": [0.0, 1.0], "Sig": [4.0, 5.0]})},
            {"name": "Run 3", "enabled": True, "df": None},
        ]

    def test_enabled_runs_filters(self) -> None:
        enabled = run_comparison_service.enabled_runs(self._runs())
        self.assertEqual([run["name"] for run in enabled], ["Run 1"])

    def test_common_x_range(self) -> None:
        runs = [
            {"df": pd.DataFrame({"Time": [0.0, 10.0]})},
            {"df": pd.DataFrame({"Time": [5.0, 20.0]})},
        ]
        self.assertEqual(run_comparison_service.comparison_common_x_range(runs, "Time"), (5.0, 10.0))

    def test_common_x_range_no_overlap(self) -> None:
        runs = [
            {"df": pd.DataFrame({"Time": [0.0, 1.0]})},
            {"df": pd.DataFrame({"Time": [5.0, 6.0]})},
        ]
        self.assertIsNone(run_comparison_service.comparison_common_x_range(runs, "Time"))

    def test_channel_frame_filters_window(self) -> None:
        df = pd.DataFrame({"Time": [0.0, 1.0, 2.0, 3.0], "Sig": [1.0, 2.0, 3.0, 4.0]})
        frame = run_comparison_service.comparison_channel_frame(df, "Time", "Sig", None, xmin=1.0, xmax=2.0)
        self.assertEqual(list(frame["x"]), [1.0, 2.0])

    def test_run_channel_statistics(self) -> None:
        df = pd.DataFrame({"Sig": [1.0, 2.0, 3.0]})
        stats = run_comparison_service.run_channel_statistics(df, "Sig")
        assert stats is not None
        self.assertEqual(stats["Count"], 3)
        self.assertEqual(stats["Mean"], 2.0)
        self.assertIsNone(run_comparison_service.run_channel_statistics(df, "Missing"))

    def test_serialise_runs_round_trip(self) -> None:
        serialised = run_comparison_service.serialise_runs(self._runs())
        self.assertEqual(serialised[0]["name"], "Run 1")
        self.assertEqual(serialised[0]["colour"], "#007AC2")
        self.assertNotIn("df", serialised[0])


class OperationResultTests(unittest.TestCase):
    def test_success_and_failure(self) -> None:
        ok = OperationResult.success("done", payload=42)
        self.assertTrue(ok.ok)
        self.assertEqual(ok.payload, 42)
        bad = OperationResult.failure("nope")
        self.assertFalse(bad.ok)
        self.assertEqual(bad.errors, ["nope"])

    def test_payload_dict_adapts_legacy_dict_payloads(self) -> None:
        self.assertEqual(payload_dict(OperationResult.success(payload={"df": "frame"})), {"df": "frame"})
        self.assertEqual(payload_dict(OperationResult.success(payload="not-a-dict")), {})


class SessionServiceTests(unittest.TestCase):
    def _base_parts(self) -> dict[str, object]:
        return {
            "version": "test",
            "root_file_directory": "",
            "file_path": "source.csv",
            "sheet_name": "",
            "runs": [],
            "comparison": {},
            "active_plot_profile_index": 0,
            "plot_profiles": [{"name": "Plot 1"}],
            "calculated_channels": {},
        }

    def test_validate_session_for_write_rejects_missing_required_new_write_fields(self) -> None:
        validation = session_service.validate_session_for_write(SessionState.from_dict({}))

        self.assertFalse(validation.ok)
        self.assertIn("Session version is required.", validation.errors)
        self.assertIn("At least one plot profile is required.", validation.errors)

    def test_build_session_dict_rejects_invalid_new_write_payload(self) -> None:
        parts = self._base_parts()
        parts["version"] = ""

        with self.assertRaises(ValueError):
            session_service.build_session_dict(**parts)

    def test_build_runtime_session_dict_embeds_manual_rows_and_normalises_channels(self) -> None:
        df = pd.DataFrame({"Time": [0.0, 1.0], "Pressure": [10.0, 11.0]})
        registry = dataset_service.build_registry_for_dataframe(df)

        session = session_service.build_runtime_session_dict(
            version="test",
            root_file_directory="",
            file_path="",
            sheet_name="",
            runs=[],
            comparison={},
            active_plot_profile_index=0,
            plot_profiles=[{"name": "Plot 1"}],
            calculated_channels={"Sum": {"formula": "Time + Pressure"}, "Broken": {"name": "Broken"}},
            data_source_type=SOURCE_MANUAL,
            channel_registry=registry,
            df=df,
        )

        self.assertEqual(session["data_source_type"], SOURCE_MANUAL)
        self.assertEqual(len(session["dataset_rows"]), 2)
        self.assertIn("Sum", session["calculated_channels"])
        self.assertNotIn("Broken", session["calculated_channels"])


class DataIoTests(unittest.TestCase):
    def test_xlsx_fast_path_preserves_single_row_headers_and_numeric_dtypes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "single-header.xlsx"
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                pd.DataFrame({"Time": [0.0, 1.0], "Pressure": [10.0, 11.0]}).to_excel(
                    writer, sheet_name="Data", index=False
                )

            loaded = data_io.load_data(path, "Data")

        self.assertEqual(list(loaded.columns), ["Time", "Pressure"])
        self.assertTrue(pd.api.types.is_numeric_dtype(loaded["Time"]))
        self.assertTrue(pd.api.types.is_numeric_dtype(loaded["Pressure"]))

    def test_xlsx_fast_path_preserves_grouped_headers(self) -> None:
        rows = [
            ["Run 1", "Run 1"],
            ["Time", "Pressure"],
            [0.0, 10.0],
            [1.0, 11.0],
        ]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "grouped-header.xlsx"
            with pd.ExcelWriter(path, engine="openpyxl") as writer:
                pd.DataFrame(rows).to_excel(writer, sheet_name="Data", index=False, header=False)

            loaded = data_io.load_data(path, "Data")

        self.assertEqual(list(loaded.columns), ["Run 1 - Time", "Run 1 - Pressure"])
        self.assertEqual(list(loaded["Run 1 - Pressure"]), [10.0, 11.0])


class CsvLoadingTests(unittest.TestCase):
    """Fast CSV loading: delimiter sniffing and numeric data-start detection."""

    def _write(self, tmp: str, name: str, text: str) -> Path:
        path = Path(tmp) / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_units_row_skipped_so_columns_load_numeric(self) -> None:
        # Header + a units row + a blank separator, like a PicoScope export. The
        # units row must not poison the numeric dtype or appear as data.
        text = "Time,Channel A,Channel B\n(ms),(A),(V)\n\n0.0,1.0,15.0\n1.0,2.0,16.0\n"
        with tempfile.TemporaryDirectory() as tmp:
            loaded = data_io.load_data(self._write(tmp, "scope.csv", text))
        self.assertEqual(list(loaded.columns), ["Time", "Channel A", "Channel B"])
        self.assertTrue(pd.api.types.is_numeric_dtype(loaded["Time"]))
        self.assertTrue(pd.api.types.is_numeric_dtype(loaded["Channel A"]))
        self.assertEqual(list(loaded["Channel A"]), [1.0, 2.0])
        self.assertEqual(len(loaded), 2)

    def test_plain_numeric_csv_is_unchanged(self) -> None:
        text = "Time,Sig\n0,10\n1,20\n2,30\n"
        with tempfile.TemporaryDirectory() as tmp:
            loaded = data_io.load_data(self._write(tmp, "plain.csv", text))
        self.assertEqual(list(loaded.columns), ["Time", "Sig"])
        self.assertEqual(list(loaded["Sig"]), [10, 20, 30])
        self.assertEqual(len(loaded), 3)

    def test_semicolon_delimiter_is_auto_sniffed(self) -> None:
        text = "Time;Sig\n0;10\n1;20\n2;30\n"
        with tempfile.TemporaryDirectory() as tmp:
            loaded = data_io.load_data(self._write(tmp, "euro.csv", text))
        self.assertEqual(list(loaded.columns), ["Time", "Sig"])
        self.assertTrue(pd.api.types.is_numeric_dtype(loaded["Sig"]))
        self.assertEqual(len(loaded), 3)

    def test_text_only_table_is_not_truncated(self) -> None:
        # No row has >=2 numeric cells, so nothing is treated as a units row.
        text = "Name,Status\nPump,OK\nValve,FAIL\n"
        with tempfile.TemporaryDirectory() as tmp:
            loaded = data_io.load_data(self._write(tmp, "text.csv", text))
        self.assertEqual(list(loaded.columns), ["Name", "Status"])
        self.assertEqual(list(loaded["Name"]), ["Pump", "Valve"])
        self.assertEqual(len(loaded), 2)


class DatasetServiceTests(unittest.TestCase):
    def _dataset(self):
        df = pd.DataFrame({"Time": [0.0, 1.0, 2.0], "Pressure": [10.0, 11.0, 12.0]})
        registry = dataset_service.build_registry_for_dataframe(df)
        return df, registry

    def test_build_registry_assigns_stable_ids_and_types(self) -> None:
        df = pd.DataFrame({"Time": [0.0, 1.0], "Label": ["a", "b"]})
        registry = dataset_service.build_registry_for_dataframe(df)
        self.assertEqual(registry.ids(), ["ch_001", "ch_002"])
        self.assertEqual(registry.spec_for_name("Time").data_type, "numeric")
        self.assertEqual(registry.spec_for_name("Label").data_type, "text")
        self.assertEqual(registry.numeric_names(), ["Time"])

    def test_build_registry_preserves_ids_on_reconcile(self) -> None:
        df, registry = self._dataset()
        original_id = registry.id_for_name("Pressure")
        reloaded = pd.DataFrame(
            {"Time": [0.0, 1.0], "Pressure": [9.0, 9.5], "Flow": [1.0, 2.0]}
        )
        reconciled = dataset_service.build_registry_for_dataframe(reloaded, existing=registry)
        self.assertEqual(reconciled.id_for_name("Pressure"), original_id)
        self.assertNotIn(reconciled.id_for_name("Flow"), {None, original_id})

    def test_add_column_blocks_duplicate(self) -> None:
        df, registry = self._dataset()
        ok = dataset_service.add_column(df, registry, "Flow")
        self.assertTrue(ok.ok)
        self.assertIn("Flow", ok.payload["df"].columns)
        dup = dataset_service.add_column(df, registry, "Flow")
        self.assertFalse(dup.ok)
        self.assertIn("already exists", dup.message)

    def test_rename_column_updates_df_and_registry(self) -> None:
        df, registry = self._dataset()
        channel_id = registry.id_for_name("Pressure")
        result = dataset_service.rename_column(df, registry, channel_id, "Outlet Pressure")
        self.assertTrue(result.ok)
        self.assertIn("Outlet Pressure", df.columns)
        self.assertNotIn("Pressure", df.columns)
        self.assertEqual(registry.name_for_id(channel_id), "Outlet Pressure")

    def test_rename_column_blocks_duplicate(self) -> None:
        df, registry = self._dataset()
        channel_id = registry.id_for_name("Pressure")
        result = dataset_service.rename_column(df, registry, channel_id, "Time")
        self.assertFalse(result.ok)
        self.assertIn("already exists", result.message)

    def test_delete_column_removes_from_df_and_registry(self) -> None:
        df, registry = self._dataset()
        channel_id = registry.id_for_name("Pressure")
        result = dataset_service.delete_column(df, registry, channel_id)
        self.assertTrue(result.ok)
        self.assertNotIn("Pressure", df.columns)
        self.assertIsNone(registry.spec_for_id(channel_id))

    def test_move_column_reorders_df_and_registry(self) -> None:
        df, registry = self._dataset()
        channel_id = registry.id_for_name("Pressure")
        result = dataset_service.move_column(df, registry, channel_id, 0)
        self.assertTrue(result.ok)
        self.assertEqual(list(result.payload["df"].columns), ["Pressure", "Time"])
        self.assertEqual(registry.display_names(), ["Pressure", "Time"])
        unchanged = dataset_service.move_column(df, registry, channel_id, 0)
        self.assertTrue(unchanged.ok)
        self.assertEqual(registry.display_names(), ["Pressure", "Time"])

    def test_add_and_delete_rows(self) -> None:
        df, _ = self._dataset()
        added = dataset_service.add_row(df)
        self.assertTrue(added.ok)
        self.assertEqual(len(added.payload["df"]), 4)
        deleted = dataset_service.delete_rows(added.payload["df"], [0, 1])
        self.assertTrue(deleted.ok)
        self.assertEqual(len(deleted.payload["df"]), 2)

    def test_set_cell_numeric_and_invalid(self) -> None:
        df, registry = self._dataset()
        channel_id = registry.id_for_name("Pressure")
        ok = dataset_service.set_cell(df, registry, channel_id, 0, "99.5")
        self.assertTrue(ok.ok)
        self.assertEqual(df.at[0, "Pressure"], 99.5)
        invalid = dataset_service.set_cell(df, registry, channel_id, 1, "bad")
        self.assertTrue(invalid.ok)
        self.assertTrue(invalid.warnings)
        self.assertEqual(df.at[1, "Pressure"], "bad")

    def test_session_rows_round_trip(self) -> None:
        df, registry = self._dataset()
        rows = dataset_service.rows_from_dataframe(registry, df)
        self.assertEqual(rows[0][registry.id_for_name("Time")], 0.0)
        rebuilt = dataset_service.dataframe_from_rows(registry, rows)
        self.assertEqual(list(rebuilt.columns), ["Time", "Pressure"])
        self.assertEqual(list(rebuilt["Pressure"]), [10.0, 11.0, 12.0])

    def test_session_rows_preserve_blanks_as_none(self) -> None:
        df = pd.DataFrame({"A": [1.0, np.nan]})
        registry = dataset_service.build_registry_for_dataframe(df)
        rows = dataset_service.rows_from_dataframe(registry, df)
        self.assertIsNone(rows[1][registry.id_for_name("A")])
        rebuilt = dataset_service.dataframe_from_rows(registry, rows)
        self.assertTrue(np.isnan(rebuilt.at[1, "A"]))


class ColumnReferenceServiceTests(unittest.TestCase):
    def test_rename_updates_profiles_limits_and_maths_references(self) -> None:
        key = plot_render_service.normalise_channel_name("Pressure")
        profiles = [
            {
                "name": "Plot 1",
                "x_column": "Pressure",
                "y_columns": ["Pressure"],
                "secondary_y_columns": ["Flow"],
                "best_fit_lines": [{"channel": "Pressure", "fit_type": "Linear", "order": 1}],
                "legend": {"channel_overrides": {key: {"channel": "Pressure", "colour": "#111111"}}},
                "limit_lines": [{"name": "L", "applies_to": "Pressure", "points": []}],
            }
        ]
        calculated_channels = {
            "Doubled": {
                "formula": "`Pressure` * 2",
                "created_from_columns": ["Pressure", "Flow"],
            }
        }
        limit_lines = [{"name": "Top", "applies_to": "Pressure", "points": []}]

        update = column_reference_service.propagate_column_rename(
            current_x_axis="Pressure",
            plot_profiles=profiles,
            calculated_channels=calculated_channels,
            limit_lines=limit_lines,
            old_name="Pressure",
            new_name="Outlet Pressure",
        )

        self.assertEqual(update.current_x_axis, "Outlet Pressure")
        self.assertEqual(profiles[0]["x_column"], "Outlet Pressure")
        self.assertEqual(profiles[0]["y_columns"], ["Outlet Pressure"])
        self.assertEqual(profiles[0]["best_fit_lines"][0]["channel"], "Outlet Pressure")
        self.assertEqual(profiles[0]["limit_lines"][0]["applies_to"], "Outlet Pressure")
        new_key = plot_render_service.normalise_channel_name("Outlet Pressure")
        self.assertEqual(profiles[0]["legend"]["channel_overrides"][new_key]["channel"], "Outlet Pressure")
        self.assertEqual(limit_lines[0]["applies_to"], "Outlet Pressure")
        self.assertEqual(calculated_channels["Doubled"]["formula"], "`Outlet Pressure` * 2")
        self.assertEqual(calculated_channels["Doubled"]["created_from_columns"], ["Outlet Pressure", "Flow"])

    def test_delete_removes_plot_references_and_returns_warnings(self) -> None:
        key = plot_render_service.normalise_channel_name("Pressure")
        profiles = [
            {
                "name": "Plot 1",
                "x_column": "Pressure",
                "y_columns": ["Pressure", "Flow"],
                "secondary_y_columns": ["Pressure"],
                "best_fit_lines": [{"channel": "Pressure", "fit_type": "Linear", "order": 1}],
                "legend": {"channel_overrides": {key: {"channel": "Pressure", "colour": "#111111"}}},
            }
        ]
        calculated_channels = {
            "Doubled": {"formula": "`Pressure` * 2", "created_from_columns": ["Pressure"]}
        }

        update = column_reference_service.propagate_column_delete(
            current_x_axis="Pressure",
            plot_profiles=profiles,
            calculated_channels=calculated_channels,
            name="Pressure",
        )

        self.assertEqual(update.current_x_axis, "")
        self.assertEqual(profiles[0]["x_column"], "")
        self.assertEqual(profiles[0]["y_columns"], ["Flow"])
        self.assertEqual(profiles[0]["secondary_y_columns"], [])
        self.assertEqual(profiles[0]["best_fit_lines"], [])
        self.assertEqual(profiles[0]["legend"]["channel_overrides"], {})
        self.assertTrue(any("Plot 1" in warning for warning in update.warnings))
        self.assertTrue(any("Doubled" in warning for warning in update.warnings))


class MathsChannelFormulaRenameTests(unittest.TestCase):
    def test_rename_backtick_reference(self) -> None:
        out = maths_channel_service.rename_column_in_formula(
            "`Inlet Pressure` / `Outlet Pressure`", "Inlet Pressure", "Supply Pressure"
        )
        self.assertEqual(out, "`Supply Pressure` / `Outlet Pressure`")

    def test_rename_bare_identifier(self) -> None:
        out = maths_channel_service.rename_column_in_formula("A + B", "A", "Alpha")
        self.assertEqual(out, "Alpha + B")

    def test_rename_bare_to_spaced_name_uses_backticks(self) -> None:
        out = maths_channel_service.rename_column_in_formula("A + B", "A", "Alpha One")
        self.assertEqual(out, "`Alpha One` + B")

    def test_rename_leaves_functions_and_substrings_untouched(self) -> None:
        out = maths_channel_service.rename_column_in_formula("abs(AB) + A", "A", "X")
        self.assertEqual(out, "abs(AB) + X")

    def test_rename_noop_when_absent(self) -> None:
        out = maths_channel_service.rename_column_in_formula("A + B", "C", "Z")
        self.assertEqual(out, "A + B")


if __name__ == "__main__":
    unittest.main()
