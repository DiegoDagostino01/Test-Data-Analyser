"""Framework-independent tests for the domain models.

These tests exercise the ``from_dict``/``to_dict`` round-trips and session
normalisation that underpin JSON session compatibility. They deliberately avoid
importing any UI framework (Tkinter or PySide6) so they can run headless.

Run with:

    python -m unittest discover -s tests
"""
from __future__ import annotations

import unittest

from test_data_analyser.core.utils import classify_channel_name
from test_data_analyser.domain import (
    AxisLimits,
    AxisTickSettings,
    CalculatedChannelDefinition,
    ComparisonSettings,
    EngineeringNotes,
    LegendSettings,
    LimitLine,
    PlotProfile,
    RunMetadata,
    SessionState,
    normalise_plot_profile,
)


class ChannelClassificationTests(unittest.TestCase):
    def test_engineering_channel_names_are_classified(self) -> None:
        self.assertEqual(classify_channel_name("Outlet Pressure"), "Pressure")
        self.assertEqual(classify_channel_name("Current on Phase A"), "Current")
        self.assertEqual(classify_channel_name("TC25 Structural Interface Temperature 240 Deg (C)"), "Temperature")
        self.assertEqual(classify_channel_name("Voltage"), "Voltage")
        self.assertEqual(classify_channel_name("Main Pump RPM"), "Speed")
        self.assertEqual(classify_channel_name("Mystery Signal"), "Other Numeric")


class AxisLimitsTests(unittest.TestCase):
    def test_round_trip_preserves_values(self) -> None:
        data = {"xmin": "0", "xmax": "10", "ymin": "-1", "ymax": "1", "y2min": "", "y2max": "5"}
        self.assertEqual(AxisLimits.from_dict(data).to_dict(), data)

    def test_missing_keys_default_to_empty_strings(self) -> None:
        self.assertEqual(
            AxisLimits.from_dict({}).to_dict(),
            {"xmin": "", "xmax": "", "ymin": "", "ymax": "", "y2min": "", "y2max": ""},
        )


class AxisTickSettingsTests(unittest.TestCase):
    def test_round_trip_preserves_values(self) -> None:
        data = {
            "x_major_tick": "0.5",
            "y_major_tick": "100",
            "y2_major_tick": "2.5",
            "align_secondary_y_axis_grid": True,
        }
        self.assertEqual(AxisTickSettings.from_dict(data).to_dict(), data)

    def test_missing_keys_default_to_auto_ticks(self) -> None:
        self.assertEqual(
            AxisTickSettings.from_dict({}).to_dict(),
            {
                "x_major_tick": "",
                "y_major_tick": "",
                "y2_major_tick": "",
                "align_secondary_y_axis_grid": False,
            },
        )


class LegendSettingsTests(unittest.TestCase):
    def test_display_mode_round_trip(self) -> None:
        data = {"max_inline_entries": 8, "location": "upper right", "display_mode": "graph"}
        expected = {**data, "channel_overrides": {}}
        self.assertEqual(LegendSettings.from_dict(data).to_dict(), expected)

    def test_channel_overrides_round_trip(self) -> None:
        data = {
            "display_mode": "panel",
            "channel_overrides": {
                "motor voltage": {
                    "channel": "Motor Voltage",
                    "label": "Voltage",
                    "colour": "#123456",
                    "plot_kind": "Scatter",
                    "line_style": "--",
                    "draw_style": "steps-post",
                    "line_width": "2.5",
                    "marker_style": "s",
                    "marker_size": "7",
                    "marker_face_colour": "#ABCDEF",
                    "marker_edge_colour": "#654321",
                }
            },
        }
        result = LegendSettings.from_dict(data).to_dict()
        self.assertEqual(result["channel_overrides"], data["channel_overrides"])

    def test_missing_display_mode_defaults_to_panel(self) -> None:
        self.assertEqual(LegendSettings.from_dict({}).display_mode, "panel")


class EngineeringNotesTests(unittest.TestCase):
    def test_legacy_free_text_maps_to_observations(self) -> None:
        notes = EngineeringNotes.from_dict("free text note")
        self.assertEqual(notes.observations, "free text note")
        self.assertEqual(notes.schema, "structured_engineering_notes_v1")

    def test_structured_round_trip(self) -> None:
        data = EngineeringNotes(objective="why", observations="what").to_dict()
        self.assertEqual(EngineeringNotes.from_dict(data).to_dict(), data)


class LimitLineTests(unittest.TestCase):
    def test_round_trip_with_points(self) -> None:
        data = {
            "name": "Upper",
            "type": "Upper Limit",
            "applies_to": "All selected Y channels",
            "color": "#007AC2",
            "points": [{"x": 0.0, "y": 1.0}, {"x": 5.0, "y": 2.5}],
        }
        self.assertEqual(LimitLine.from_dict(data).to_dict(), data)

    def test_invalid_points_are_ignored(self) -> None:
        line = LimitLine.from_dict({"name": "L", "points": "not-a-list"})
        self.assertEqual(line.points, [])


class RunMetadataTests(unittest.TestCase):
    def test_round_trip_preserves_keys(self) -> None:
        data = {
            "name": "Run 1",
            "filepath": r"C:\\data\\run1.xlsx",
            "sheet_name": "Sheet1",
            "enabled": True,
            "colour": "#007AC2",
        }
        self.assertEqual(RunMetadata.from_dict(data).to_dict(), data)


class ComparisonSettingsTests(unittest.TestCase):
    def test_defaults(self) -> None:
        self.assertEqual(
            ComparisonSettings.from_dict({}).to_dict(),
            {
                "comparison_mode_enabled": False,
                "comparison_common_x_range": False,
                "comparison_prefix_legend": True,
                "active_run_index": -1,
            },
        )

    def test_invalid_active_run_index_falls_back(self) -> None:
        self.assertEqual(ComparisonSettings.from_dict({"active_run_index": "abc"}).active_run_index, -1)


class CalculatedChannelTests(unittest.TestCase):
    def test_valid_definition(self) -> None:
        definition = CalculatedChannelDefinition.from_dict({"name": "Power", "formula": "V * I"})
        self.assertTrue(definition.is_valid)

    def test_missing_formula_is_invalid(self) -> None:
        self.assertFalse(CalculatedChannelDefinition.from_dict({"name": "Power"}).is_valid)

    def test_fallback_name_from_session_key(self) -> None:
        definition = CalculatedChannelDefinition.from_dict({"formula": "A + B"}, fallback_name="Sum")
        self.assertEqual(definition.name, "Sum")


class PlotProfileTests(unittest.TestCase):
    def test_round_trip_preserves_values(self) -> None:
        data = normalise_plot_profile(
            {
                "name": "Plot 1",
                "x_column": "Time",
                "y_columns": ["A", "B"],
                "title": "Test",
                "limit_lines": [{"name": "Upper", "points": [{"x": 0.0, "y": 1.0}]}],
            }
        )
        # Normalisation is idempotent.
        self.assertEqual(PlotProfile.from_dict(data).to_dict(), data)

    def test_defaults_for_empty_input(self) -> None:
        profile = PlotProfile.from_dict({})
        self.assertEqual(profile.name, "Plot 1")
        self.assertEqual(profile.y_label, "Selected Signals")
        self.assertEqual(profile.plot_kind, "Line")
        self.assertTrue(profile.grid)


class SessionStateTests(unittest.TestCase):
    def _sample_session(self) -> dict:
        return {
            "version": "1.00.00",
            "file_path": r"C:\\data\\run1.xlsx",
            "sheet_name": "Sheet1",
            "runs": [
                {
                    "name": "Run 1",
                    "filepath": r"C:\\data\\run1.xlsx",
                    "sheet_name": "Sheet1",
                    "enabled": True,
                    "colour": "#007AC2",
                }
            ],
            "active_run_index": 0,
            "comparison_mode_enabled": True,
            "comparison_common_x_range": False,
            "comparison_prefix_legend": True,
            "active_plot_profile_index": 0,
            "plot_profiles": [PlotProfile(name="Plot 1", x_column="Time", y_columns=["A"]).to_dict()],
            "calculated_channels": {
                "Power": {
                    "name": "Power",
                    "formula": "V * I",
                    "description": "",
                    "enabled": True,
                    "created_from_columns": ["V", "I"],
                }
            },
        }

    def test_round_trip_preserves_all_keys(self) -> None:
        session = self._sample_session()
        restored = SessionState.from_dict(session).to_dict()
        self.assertEqual(set(restored.keys()), set(session.keys()))
        self.assertEqual(restored["runs"], session["runs"])
        self.assertEqual(restored["calculated_channels"], session["calculated_channels"])
        self.assertEqual(restored["comparison_mode_enabled"], True)
        self.assertEqual(restored["active_run_index"], 0)
        self.assertEqual(restored["plot_profiles"], session["plot_profiles"])

    def test_missing_keys_produce_safe_defaults(self) -> None:
        restored = SessionState.from_dict({}).to_dict()
        self.assertEqual(restored["runs"], [])
        self.assertEqual(restored["plot_profiles"], [])
        self.assertEqual(restored["calculated_channels"], {})
        self.assertEqual(restored["active_plot_profile_index"], 0)
        self.assertEqual(restored["active_run_index"], -1)

    def test_invalid_calculated_channels_are_dropped(self) -> None:
        session = self._sample_session()
        session["calculated_channels"]["Broken"] = {"name": "Broken"}  # no formula
        restored = SessionState.from_dict(session).to_dict()
        self.assertIn("Power", restored["calculated_channels"])
        self.assertNotIn("Broken", restored["calculated_channels"])

    def test_non_dict_input_is_handled(self) -> None:
        restored = SessionState.from_dict(None).to_dict()
        self.assertEqual(restored["plot_profiles"], [])


if __name__ == "__main__":
    unittest.main()
