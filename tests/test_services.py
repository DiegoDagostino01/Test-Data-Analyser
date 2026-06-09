"""Framework-independent tests for the service layer.

These tests exercise the pure engineering/data logic extracted into
``test_data_analyser.services``. They must not require a GUI.

Run with:

    python -m unittest discover -s tests
"""
from __future__ import annotations

import unittest

import numpy as np
import pandas as pd

from test_data_analyser.domain import PlotData
from test_data_analyser.services import (
    cursor_service,
    fft_service,
    limits_service,
    maths_channel_service,
    plotting_data_service,
    raw_data_service,
    run_comparison_service,
    statistics_service,
)
from test_data_analyser.services.maths_channel_service import MathsChannelEvaluator
from test_data_analyser.services.results import OperationResult


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


class FftServiceTests(unittest.TestCase):
    def test_detects_known_frequency(self) -> None:
        fs = 1000.0
        t = np.arange(0, 1.0, 1.0 / fs)
        signal = np.sin(2 * np.pi * 50 * t)
        freqs, amp = fft_service.fft_spectrum(signal, fs, window_name="hanning", overlap_percent=0)
        peak_freq = freqs[int(np.argmax(amp))]
        self.assertAlmostEqual(peak_freq, 50.0, delta=2.0)

    def test_window_sizes(self) -> None:
        self.assertEqual(len(fft_service.fft_window("hamming", 16)), 16)
        self.assertEqual(len(fft_service.fft_window("rectangular", 8)), 8)
        self.assertTrue(np.allclose(fft_service.fft_window("rectangular", 4), np.ones(4)))


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


if __name__ == "__main__":
    unittest.main()
