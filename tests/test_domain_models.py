"""Framework-independent tests for the domain models.

These tests exercise the ``from_dict``/``to_dict`` round-trips and session
normalisation that underpin JSON session compatibility. They deliberately avoid
importing any UI framework (Tkinter or PySide6) so they can run headless.

Run with:

    python -m unittest discover -s tests
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from test_data_analyser.core.channel_classification import classify_channel_name
from test_data_analyser.core.indexing import clamp_index
from test_data_analyser.core.utils import classify_channel_name as legacy_classify_channel_name
from test_data_analyser.core.utils import clamp_index as legacy_clamp_index
from test_data_analyser.domain import (
    AxisLimits,
    AxisTickSettings,
    CalculatedChannelDefinition,
    ChannelRegistry,
    ComparisonSettings,
    EngineeringNotes,
    LegendSettings,
    LimitLine,
    PlotProfile,
    RunMetadata,
    SessionState,
    normalise_annotations,
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


class ClampIndexTests(unittest.TestCase):
    def test_clamps_into_valid_range(self) -> None:
        self.assertEqual(clamp_index(3, 5), 3)
        self.assertEqual(clamp_index(9, 5), 4)  # past the end -> last index
        self.assertEqual(clamp_index(-2, 5), 0)  # negative -> first index

    def test_empty_collection_returns_zero(self) -> None:
        # Matches the long-standing active-profile / active-limit selection idiom.
        self.assertEqual(clamp_index(0, 0), 0)
        self.assertEqual(clamp_index(7, 0), 0)

    def test_utils_facade_preserves_legacy_imports(self) -> None:
        self.assertIs(legacy_clamp_index, clamp_index)
        self.assertIs(legacy_classify_channel_name, classify_channel_name)


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
                    "hidden": "true",
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
                "best_fit_lines": [
                    {"channel": "A", "fit_type": "Polynomial", "order": 4}
                ],
            }
        )
        # Normalisation is idempotent.
        self.assertEqual(PlotProfile.from_dict(data).to_dict(), data)
        self.assertEqual(data["best_fit_lines"][0]["channel"], "A")
        self.assertEqual(data["best_fit_lines"][0]["order"], 4)

    def test_best_fit_lines_are_limited_and_normalised(self) -> None:
        profile = PlotProfile.from_dict(
            {
                "best_fit_lines": [
                    {"channel": "A", "fit_type": "Polynomial", "order": 99},
                    {"channel": " a ", "fit_type": "Squared", "order": 2},
                    *[{"channel": f"C{index}", "fit_type": "Linear", "order": 1} for index in range(6)],
                ]
            }
        )

        self.assertEqual(len(profile.best_fit_lines), 5)
        self.assertEqual(profile.best_fit_lines[0]["order"], 6)
        self.assertEqual(profile.best_fit_lines[1]["channel"], "C0")

    def test_defaults_for_empty_input(self) -> None:
        profile = PlotProfile.from_dict({})
        self.assertEqual(profile.name, "Plot 1")
        self.assertEqual(profile.y_label, "Selected Signals")
        self.assertEqual(profile.plot_kind, "Line")
        self.assertTrue(profile.grid)

    def test_annotations_are_preserved_and_malformed_entries_are_skipped(self) -> None:
        annotations = normalise_annotations(
            [
                {"id": "txt", "type": "text", "text": "Pressure dip", "x": "1.5", "y": "2.5"},
                {"id": "arr", "type": "arrow", "axis": "secondary", "start_x": 1, "start_y": 2, "end_x": 3, "end_y": 4},
                {"id": "box", "type": "box", "x_min": 3, "x_max": 1, "y_min": 4, "y_max": 2},
                {"id": "bad", "type": "text", "x": 1, "y": 2},
                {"id": "unknown", "type": "circle", "x": 1, "y": 2},
            ]
        )

        self.assertEqual([annotation["type"] for annotation in annotations], ["text", "arrow", "box"])
        self.assertEqual(annotations[0]["axis"], "primary")
        self.assertEqual(annotations[1]["axis"], "secondary")
        self.assertEqual(annotations[2]["x_min"], 1.0)
        profile = PlotProfile.from_dict({"annotations": annotations})
        self.assertEqual(profile.to_dict()["annotations"], annotations)


class SessionStateTests(unittest.TestCase):
    FIXTURE_ROOT = PROJECT_ROOT / "tests" / "fixtures" / "v103_migration"

    def _sample_session(self) -> dict:
        return {
            "version": "1.00.00",
            "root_file_directory": r"C:\\data",
            "file_path": r"C:\\data\\run1.xlsx",
            "sheet_name": "Sheet1",
            "data_source_type": "excel",
            "channel_registry": {
                "columns": [{"id": "ch_001", "display_name": "Time", "data_type": "numeric"}],
                "next_id": 2,
            },
            "dataset_rows": [],
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
        self.assertEqual(restored["root_file_directory"], "")

    def test_missing_root_directory_is_derived_from_file_path(self) -> None:
        restored = SessionState.from_dict({"file_path": r"C:\data\run1.xlsx"}).to_dict()
        self.assertEqual(restored["root_file_directory"], r"C:\data")

    def test_invalid_calculated_channels_are_dropped(self) -> None:
        session = self._sample_session()
        session["calculated_channels"]["Broken"] = {"name": "Broken"}  # no formula
        restored = SessionState.from_dict(session).to_dict()
        self.assertIn("Power", restored["calculated_channels"])
        self.assertNotIn("Broken", restored["calculated_channels"])

    def test_current_fixture_keeps_workspace_state_out_of_analysis_models(self) -> None:
        fixture = json.loads(
            (self.FIXTURE_ROOT / "current_session.json").read_text(encoding="utf-8")
        )

        restored = SessionState.from_dict(fixture).to_dict()

        self.assertNotIn("workspace", restored)
        self.assertNotIn("workspace_layout_version", restored)
        self.assertNotIn("workspace", restored["plot_profiles"][0])
        self.assertEqual(restored["plot_profiles"][0]["secondary_y_columns"], ["Power"])
        self.assertTrue(restored["plot_profiles"][0]["generated"])
        self.assertIn("Power", restored["calculated_channels"])
        self.assertNotIn("Broken", restored["calculated_channels"])

    def test_legacy_fixture_normalises_without_new_workspace_or_registry_state(self) -> None:
        fixture = json.loads(
            (self.FIXTURE_ROOT / "legacy_session.json").read_text(encoding="utf-8")
        )

        restored = SessionState.from_dict(fixture).to_dict()

        self.assertEqual(restored["root_file_directory"], r"C:\Engineering\TDA Fixtures")
        self.assertEqual(restored["channel_registry"], {"columns": [], "next_id": 1})
        self.assertEqual(restored["plot_profiles"][0]["secondary_y_columns"], ["Temperature"])
        self.assertEqual(restored["plot_profiles"][0]["legend"]["display_mode"], "graph")
        self.assertIn("Pressure Delta", restored["calculated_channels"])
        self.assertNotIn("engineering_notes", restored)
        self.assertNotIn("limit_lines", restored)
        self.assertNotIn("workspace", restored)

    def test_non_dict_input_is_handled(self) -> None:
        restored = SessionState.from_dict(None).to_dict()
        self.assertEqual(restored["plot_profiles"], [])


class ChannelRegistryTests(unittest.TestCase):
    def _registry(self) -> ChannelRegistry:
        registry = ChannelRegistry()
        registry.add_column("Time", "numeric")
        registry.add_column("Pressure", "numeric")
        registry.add_column("Serial", "text")
        return registry

    def test_allocate_ids_are_sequential_and_unique(self) -> None:
        registry = self._registry()
        self.assertEqual(registry.ids(), ["ch_001", "ch_002", "ch_003"])

    def test_lookups_resolve_both_directions(self) -> None:
        registry = self._registry()
        channel_id = registry.id_for_name("Pressure")
        self.assertEqual(channel_id, "ch_002")
        self.assertEqual(registry.name_for_id(channel_id), "Pressure")
        self.assertEqual(registry.numeric_names(), ["Time", "Pressure"])

    def test_has_display_name_respects_exclusion(self) -> None:
        registry = self._registry()
        self.assertTrue(registry.has_display_name("Time"))
        self.assertFalse(
            registry.has_display_name("Time", exclude_id=registry.id_for_name("Time"))
        )

    def test_round_trip_preserves_ids_and_counter(self) -> None:
        registry = self._registry()
        restored = ChannelRegistry.from_dict(registry.to_dict())
        self.assertEqual(restored.ids(), ["ch_001", "ch_002", "ch_003"])
        self.assertEqual(restored.next_id, 4)
        self.assertEqual(restored.spec_for_name("Serial").data_type, "text")

    def test_sync_next_id_recovers_from_stale_counter(self) -> None:
        registry = ChannelRegistry.from_dict(
            {"columns": [{"id": "ch_010", "display_name": "A", "data_type": "numeric"}], "next_id": 1}
        )
        self.assertEqual(registry.allocate_id(), "ch_011")

    def test_names_and_ids_resolution_skips_unknown(self) -> None:
        registry = self._registry()
        ids = registry.names_to_ids(["Pressure", "Missing", "Time"])
        self.assertEqual(ids, ["ch_002", "ch_001"])
        names = registry.ids_to_names(["ch_001", "ch_999", "ch_003"])
        self.assertEqual(names, ["Time", "Serial"])


if __name__ == "__main__":
    unittest.main()
