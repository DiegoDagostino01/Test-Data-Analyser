"""Tests for the Qt ``PandasTableModel`` adapter and the settings options helper.

These tests construct a Qt model and therefore need a ``QApplication``. They run
headless under the offscreen platform and are skipped entirely if PySide6 is not
installed, so the rest of the suite stays GUI-free.

Run with:

    python -m unittest discover -s tests
"""
from __future__ import annotations

import os
import unittest

import pandas as pd

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from test_data_analyser.qt_app.adapters.editable_raw_data_model import EditableRawDataTableModel
    from test_data_analyser.qt_app.adapters.pandas_table_model import PandasTableModel
    from test_data_analyser.viewmodels.app_state import AppState
    from test_data_analyser.viewmodels.cursor_compare_vm import CursorCompareViewModel
    from test_data_analyser.viewmodels.engineering_notes_vm import EngineeringNotesViewModel
    from test_data_analyser.viewmodels.limits_vm import LimitsViewModel
    from test_data_analyser.viewmodels.maths_channels_vm import MathsChannelsViewModel
    from test_data_analyser.viewmodels.plot_workspace_vm import PlotWorkspaceViewModel
    from test_data_analyser.viewmodels.raw_data_vm import RawDataViewModel
    from test_data_analyser.viewmodels.runs_comparison_vm import RunsComparisonViewModel
    from test_data_analyser.viewmodels.settings_vm import SettingsViewModel

    PYSIDE_AVAILABLE = True
except Exception:  # pragma: no cover - exercised only when PySide6 is absent
    PYSIDE_AVAILABLE = False


_app = None


def setUpModule() -> None:
    global _app
    if PYSIDE_AVAILABLE:
        _app = QApplication.instance() or QApplication([])


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class PandasTableModelTests(unittest.TestCase):
    def _df(self) -> pd.DataFrame:
        return pd.DataFrame({"A": [1.0, 2.5, 3.0], "B": ["x", "y", "z"]})

    def test_dimensions_without_index(self) -> None:
        model = PandasTableModel(self._df())
        self.assertEqual(model.rowCount(), 3)
        self.assertEqual(model.columnCount(), 2)

    def test_dimensions_with_index_column(self) -> None:
        model = PandasTableModel(self._df(), index_header="Signal")
        self.assertEqual(model.columnCount(), 3)
        self.assertEqual(model.headerData(0, Qt.Horizontal, Qt.DisplayRole), "Signal")
        self.assertEqual(model.headerData(1, Qt.Horizontal, Qt.DisplayRole), "A")

    def test_value_formatting(self) -> None:
        model = PandasTableModel(self._df())
        self.assertEqual(model.data(model.index(0, 0), Qt.DisplayRole), "1")
        self.assertEqual(model.data(model.index(1, 0), Qt.DisplayRole), "2.5")
        self.assertEqual(model.data(model.index(2, 1), Qt.DisplayRole), "z")

    def test_nan_renders_empty(self) -> None:
        model = PandasTableModel(pd.DataFrame({"A": [float("nan"), 1.0]}))
        self.assertEqual(model.data(model.index(0, 0), Qt.DisplayRole), "")

    def test_index_column_shows_index(self) -> None:
        df = pd.DataFrame({"Mean": [10.0]}, index=["ChannelA"])
        model = PandasTableModel(df, index_header="Signal")
        self.assertEqual(model.data(model.index(0, 0), Qt.DisplayRole), "ChannelA")
        self.assertEqual(model.data(model.index(0, 1), Qt.DisplayRole), "10")

    def test_set_dataframe_resets(self) -> None:
        model = PandasTableModel(self._df())
        model.set_dataframe(pd.DataFrame({"Z": [1, 2, 3, 4]}))
        self.assertEqual(model.rowCount(), 4)
        self.assertEqual(model.columnCount(), 1)

    def test_empty_dataframe(self) -> None:
        model = PandasTableModel()
        self.assertEqual(model.rowCount(), 0)
        self.assertEqual(model.columnCount(), 0)


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class EditableRawDataTableModelTests(unittest.TestCase):
    def _model(self):
        df = pd.DataFrame({"Time": [0.0, 1.0, 2.0], "A": [10.0, 20.0, 30.0]})
        vm = RawDataViewModel(AppState(df=df.copy()))
        return EditableRawDataTableModel(vm.coerce_edit_value, df.copy())

    def test_cells_are_editable(self) -> None:
        model = self._model()
        self.assertTrue(model.flags(model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable)

    def test_edit_role_returns_string(self) -> None:
        model = self._model()
        self.assertEqual(model.data(model.index(1, 1), Qt.ItemDataRole.EditRole), "20.0")

    def test_edit_role_blank_for_nan(self) -> None:
        df = pd.DataFrame({"A": [float("nan"), 1.0]})
        vm = RawDataViewModel(AppState(df=df.copy()))
        model = EditableRawDataTableModel(vm.coerce_edit_value, df.copy())
        self.assertEqual(model.data(model.index(0, 0), Qt.ItemDataRole.EditRole), "")

    def test_valid_edit_emits_cell_edited(self) -> None:
        model = self._model()
        edited: list[tuple] = []
        model.cellEdited.connect(lambda idx, col, val: edited.append((idx, col, val)))
        self.assertTrue(model.setData(model.index(1, 1), "999", Qt.ItemDataRole.EditRole))
        self.assertEqual(edited, [(1, "A", 999.0)])
        self.assertEqual(model.data(model.index(1, 1), Qt.ItemDataRole.DisplayRole), "999")

    def test_invalid_edit_emits_edit_failed(self) -> None:
        model = self._model()
        failures: list[str] = []
        model.editFailed.connect(failures.append)
        self.assertFalse(model.setData(model.index(0, 1), "abc", Qt.ItemDataRole.EditRole))
        self.assertTrue(failures)

    def test_unchanged_edit_is_rejected(self) -> None:
        model = self._model()
        edited: list[tuple] = []
        model.cellEdited.connect(lambda idx, col, val: edited.append((idx, col, val)))
        self.assertFalse(model.setData(model.index(0, 1), "10", Qt.ItemDataRole.EditRole))
        self.assertEqual(edited, [])


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class MathsChannelsPanelTests(unittest.TestCase):
    """Construct the Maths Channels panel offscreen and drive it through its VM.

    The panel's success/error/confirm dialogs are patched to non-blocking stubs
    so the modal message boxes never appear during the headless run.
    """

    def setUp(self) -> None:
        from test_data_analyser.qt_app.widgets import maths_channels_panel as panel_module

        self._panel_module = panel_module
        self._service = panel_module.qt_message_service
        self._original = {
            name: getattr(self._service, name)
            for name in ("info", "warning", "error", "confirm", "show_result")
        }
        self._service.info = lambda *args, **kwargs: None
        self._service.warning = lambda *args, **kwargs: None
        self._service.error = lambda *args, **kwargs: None
        self._service.confirm = lambda *args, **kwargs: True
        self._service.show_result = lambda *args, **kwargs: None

        df = pd.DataFrame({"Time": [0.0, 1.0, 2.0], "A": [10.0, 20.0, 30.0], "B": [1.0, 2.0, 3.0]})
        self.state = AppState(df=df)
        self.vm = MathsChannelsViewModel(self.state)
        self.panel = panel_module.MathsChannelsPanel(self.vm)

    def tearDown(self) -> None:
        for name, original in self._original.items():
            setattr(self._service, name, original)

    def test_apply_creates_channel_and_table_row(self) -> None:
        self.panel.name_edit.setText("Sum")
        self.panel.formula_edit.setPlainText("A + B")
        self.panel._apply()
        self.assertIn("Sum", self.state.calculated_channels)
        self.assertIn("Sum", self.state.df.columns)
        self.assertEqual(self.panel.model.rowCount(), 1)

    def test_selection_loads_form(self) -> None:
        self.vm.apply_channel("Sum", "A + B")
        self.panel.refresh()
        self.panel.table.selectRow(0)
        self.assertEqual(self.panel.name_edit.text(), "Sum")
        self.assertEqual(self.panel.formula_edit.toPlainText(), "A + B")

    def test_delete_removes_channel(self) -> None:
        self.vm.apply_channel("Sum", "A + B")
        self.panel.refresh()
        self.panel._selected_name = "Sum"
        self.panel._delete()
        self.assertNotIn("Sum", self.state.calculated_channels)
        self.assertEqual(self.panel.model.rowCount(), 0)

    def test_insert_column_wraps_in_backticks(self) -> None:
        self.panel.column_combo.setCurrentText("A")
        self.panel._insert_column()
        self.assertIn("`A`", self.panel.formula_edit.toPlainText())

    def test_clear_form_resets_state(self) -> None:
        self.panel.name_edit.setText("X")
        self.panel.formula_edit.setPlainText("A + B")
        self.panel._selected_name = "X"
        self.panel.clear_form()
        self.assertEqual(self.panel.name_edit.text(), "")
        self.assertEqual(self.panel.formula_edit.toPlainText(), "")
        self.assertIsNone(self.panel._selected_name)


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class LimitsPanelTests(unittest.TestCase):
    """Construct the Limits panel offscreen and drive it through its VMs.

    The panel's confirm/error dialogs are patched to non-blocking stubs so the
    modal message boxes never appear during the headless run.
    """

    def setUp(self) -> None:
        from test_data_analyser.qt_app.widgets import limits_panel as panel_module

        self._service = panel_module.qt_message_service
        self._original = {
            name: getattr(self._service, name)
            for name in ("info", "warning", "error", "confirm", "show_result")
        }
        self._service.info = lambda *args, **kwargs: None
        self._service.warning = lambda *args, **kwargs: None
        self._service.error = lambda *args, **kwargs: None
        self._service.confirm = lambda *args, **kwargs: True
        self._service.show_result = lambda *args, **kwargs: None

        df = pd.DataFrame({"Time": [0.0, 1.0, 2.0], "A": [1.0, 2.0, 3.0]})
        self.state = AppState(df=df)
        self.limits_vm = LimitsViewModel(self.state)
        self.plot_vm = PlotWorkspaceViewModel(self.state)
        self.panel = panel_module.LimitsPanel(self.limits_vm, self.plot_vm)
        self.panel.set_selection_provider(lambda: ("Time", ["A"], None, None))

    def tearDown(self) -> None:
        for name, original in self._original.items():
            setattr(self._service, name, original)

    def test_add_line_populates_table_and_form(self) -> None:
        self.panel._add_line()
        self.assertEqual(self.panel.lines_model.rowCount(), 1)
        self.assertEqual(self.panel.name_edit.text(), "Limit 1")

    def test_add_point_updates_points_table(self) -> None:
        self.panel._add_line()
        self.panel.point_x_edit.setText("0")
        self.panel.point_y_edit.setText("10")
        self.panel._add_point()
        self.assertEqual(self.panel.points_model.rowCount(), 1)
        self.assertEqual(len(self.state.limit_lines[0]["points"]), 1)

    def test_metadata_edit_writes_to_state(self) -> None:
        self.panel._add_line()
        self.panel.name_edit.setText("Upper Bound")
        self.panel._store_metadata()
        self.assertEqual(self.state.limit_lines[0]["name"], "Upper Bound")

    def test_colour_preset_sets_colour(self) -> None:
        self.panel._add_line()
        self.panel.colour_combo.setCurrentText("Red")
        self.panel._on_colour_preset(0)
        self.assertEqual(self.state.limit_lines[0]["color"].upper(), "#C4262E")

    def test_refresh_margins_reports_pass(self) -> None:
        self.panel._add_line()
        self.panel.vm.update_active_metadata(
            name="Max", limit_type="Upper Limit", applies_to="All selected Y channels", colour="#005A8C"
        )
        self.panel.vm.add_point("0", "10")
        self.panel.vm.add_point("2", "10")
        self.panel.refresh_margins()
        self.assertIn("PASS", self.panel.summary_text.toPlainText())

    def test_limits_changed_emitted_on_add(self) -> None:
        emitted = []
        self.panel.limitsChanged.connect(lambda: emitted.append(True))
        self.panel._add_line()
        self.assertTrue(emitted)


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class EngineeringNotesPanelTests(unittest.TestCase):
    def setUp(self) -> None:
        from test_data_analyser.qt_app.widgets import engineering_notes_panel as panel_module

        self._service = panel_module.qt_message_service
        self._original = {name: getattr(self._service, name) for name in ("info", "warning", "error", "confirm")}
        self._service.confirm = lambda *args, **kwargs: True
        for name in ("info", "warning", "error"):
            setattr(self._service, name, lambda *args, **kwargs: None)

        self.state = AppState()
        self.vm = EngineeringNotesViewModel(self.state)
        self.panel = panel_module.EngineeringNotesPanel(self.vm)
        self.panel.set_context_provider(lambda: ("data.csv", "Time", "A"))

    def tearDown(self) -> None:
        for name, original in self._original.items():
            setattr(self._service, name, original)

    def test_editing_field_updates_state(self) -> None:
        self.panel._editors["observations"].setPlainText("Spike at 2 s.")
        self.assertEqual(self.state.engineering_notes["observations"], "Spike at 2 s.")

    def test_refresh_report_includes_text(self) -> None:
        self.panel._editors["objective"].setPlainText("Verify response.")
        self.panel.refresh_report()
        self.assertIn("Verify response.", self.panel.report_text.toPlainText())

    def test_load_from_state_populates_editors(self) -> None:
        self.vm.set_notes({"rationale": "Because physics."})
        self.panel.load_from_state()
        self.assertEqual(self.panel._editors["rationale"].toPlainText(), "Because physics.")

    def test_clear_empties_editors(self) -> None:
        self.panel._editors["actions"].setPlainText("Retest.")
        self.panel._clear()
        self.assertEqual(self.panel._editors["actions"].toPlainText(), "")


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class RunsComparisonPanelTests(unittest.TestCase):
    def setUp(self) -> None:
        from test_data_analyser.qt_app.widgets import runs_comparison_panel as panel_module

        self._service = panel_module.qt_message_service
        self._original = {name: getattr(self._service, name) for name in ("info", "warning", "error", "confirm")}
        self._service.confirm = lambda *args, **kwargs: True
        for name in ("info", "warning", "error"):
            setattr(self._service, name, lambda *args, **kwargs: None)

        self.state = AppState()
        self.vm = RunsComparisonViewModel(self.state)
        self.state.runs = [
            self.vm.make_run_entry("Run 1", "r1.csv", "", pd.DataFrame({"Time": [0.0, 1.0], "A": [1.0, 2.0]}), enabled=True),
            self.vm.make_run_entry("Run 2", "r2.csv", "", pd.DataFrame({"Time": [0.0, 1.0], "A": [3.0, 4.0]}), enabled=True),
        ]
        self.state.active_run_index = 0
        self.panel = panel_module.RunsComparisonPanel(self.vm)
        self.panel.set_selection_provider(lambda: ("Time", ["A"], None, None))

    def tearDown(self) -> None:
        for name, original in self._original.items():
            setattr(self._service, name, original)

    def test_refresh_populates_runs_table(self) -> None:
        self.panel.refresh()
        self.assertEqual(self.panel.runs_model.rowCount(), 2)

    def test_statistics_populated_from_selection(self) -> None:
        self.panel.update_statistics()
        self.assertEqual(self.panel.stats_model.rowCount(), 2)

    def test_toggle_enabled_via_double_click_row(self) -> None:
        self.panel._toggle_via_index(1)
        self.assertFalse(self.state.runs[1]["enabled"])

    def test_remove_run_updates_table(self) -> None:
        self.panel.runs_table.selectRow(1)
        self.panel._remove_run()
        self.assertEqual(self.panel.runs_model.rowCount(), 1)

    def test_options_write_through(self) -> None:
        self.panel.common_x_check.setChecked(True)
        self.assertTrue(self.vm.get_setting("comparison_common_x_range"))


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class AxisSelectionPanelTests(unittest.TestCase):
    def setUp(self) -> None:
        from test_data_analyser.qt_app.widgets.axis_selection_panel import AxisSelectionPanel

        self.panel = AxisSelectionPanel()
        self.panel.set_columns(["Time", "A", "B"], "Time")

    def test_set_columns_populates_both_lists(self) -> None:
        self.assertEqual(self.panel.y_list.count(), 2)
        self.assertEqual(self.panel.secondary_y_list.count(), 2)

    def test_secondary_selection(self) -> None:
        for row in range(self.panel.secondary_y_list.count()):
            item = self.panel.secondary_y_list.item(row)
            if item.text() == "B":
                item.setCheckState(Qt.CheckState.Checked)
        self.assertEqual(self.panel.selected_secondary_y(), ["B"])

    def test_plot_kind_default(self) -> None:
        self.assertEqual(self.panel.plot_kind(), "Line")

    def test_filter_settings_defaults(self) -> None:
        use_filter, cutoff, order = self.panel.filter_settings()
        self.assertFalse(use_filter)
        self.assertIsNone(cutoff)
        self.assertEqual(order, 4)

    def test_filter_settings_parsed(self) -> None:
        self.panel.filter_check.setChecked(True)
        self.panel.cutoff_edit.setText("50")
        self.panel.order_edit.setText("6")
        self.assertEqual(self.panel.filter_settings(), (True, 50.0, 6))

    def test_update_columns_preserves_secondary(self) -> None:
        for row in range(self.panel.secondary_y_list.count()):
            item = self.panel.secondary_y_list.item(row)
            if item.text() == "B":
                item.setCheckState(Qt.CheckState.Checked)
        self.panel.update_columns(["Time", "A", "B", "C"])
        self.assertEqual(self.panel.selected_secondary_y(), ["B"])


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class PlotWorkspaceParityTests(unittest.TestCase):
    def setUp(self) -> None:
        import numpy as np

        from test_data_analyser.qt_app.widgets.plot_workspace import PlotWorkspace

        t = np.linspace(0.0, 1.0, 200)
        df = pd.DataFrame({"Time": t, "A": np.sin(2 * np.pi * 5 * t), "B": 100 * np.cos(2 * np.pi * 2 * t)})
        self.state = AppState(df=df)
        self.plot_vm = PlotWorkspaceViewModel(self.state)
        self.settings_vm = SettingsViewModel(None)
        self.panel = PlotWorkspace(self.plot_vm, self.settings_vm)

    def test_basic_plot_single_axes(self) -> None:
        result = self.panel.generate_plot("Time", ["A"])
        self.assertTrue(result.ok)
        self.assertEqual(len(self.panel.canvas.figure.axes), 1)

    def test_secondary_axis_creates_twin(self) -> None:
        result = self.panel.generate_plot("Time", ["A", "B"], secondary_y=["B"])
        self.assertTrue(result.ok)
        self.assertEqual(len(self.panel.canvas.figure.axes), 2)

    def test_scatter_plot_kind(self) -> None:
        result = self.panel.generate_plot("Time", ["A"], plot_kind="Scatter")
        self.assertTrue(result.ok)
        self.assertTrue(self.panel.canvas.axes.collections)

    def test_low_pass_filter(self) -> None:
        result = self.panel.generate_plot("Time", ["A"], use_filter=True, cutoff=10.0, order=4)
        self.assertTrue(result.ok, result.message)
        self.assertTrue(self.panel.canvas.axes.get_lines())

    def test_filter_requires_cutoff(self) -> None:
        result = self.panel.generate_plot("Time", ["A"], use_filter=True, cutoff=None)
        self.assertFalse(result.ok)


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class CursorComparePanelTests(unittest.TestCase):
    class _Event:
        def __init__(self, xdata, inaxes, button=1):
            self.xdata = xdata
            self.inaxes = inaxes
            self.button = button

    def setUp(self) -> None:
        import numpy as np

        from test_data_analyser.qt_app.widgets.cursor_compare_panel import CursorComparePanel
        from test_data_analyser.qt_app.widgets.plot_workspace import PlotWorkspace

        df = pd.DataFrame({"Time": np.linspace(0.0, 3.0, 4), "A": [10.0, 20.0, 30.0, 40.0]})
        self.state = AppState(df=df)
        self.cursor_vm = CursorCompareViewModel()
        self.plot = PlotWorkspace(PlotWorkspaceViewModel(self.state), SettingsViewModel(None))
        self.plot.set_cursor_viewmodel(self.cursor_vm)
        self.panel = CursorComparePanel(self.cursor_vm, self.plot)
        self.plot.generate_plot("Time", ["A"])

    def test_compare_toggle_enables_mode(self) -> None:
        self.panel.compare_check.setChecked(True)
        self.assertTrue(self.plot._point_compare)

    def test_click_locks_point_and_refreshes_table(self) -> None:
        self.plot.set_point_compare_enabled(True)
        self.plot._on_canvas_click(self._Event(0.1, self.plot.canvas.axes))
        self.assertEqual(len(self.cursor_vm.points), 1)
        self.assertEqual(self.panel.model.rowCount(), 1)

    def test_click_ignored_when_disabled(self) -> None:
        self.plot.set_point_compare_enabled(False)
        self.plot._on_canvas_click(self._Event(0.1, self.plot.canvas.axes))
        self.assertEqual(len(self.cursor_vm.points), 0)

    def test_clear_points(self) -> None:
        self.plot.set_point_compare_enabled(True)
        self.plot._on_canvas_click(self._Event(0.1, self.plot.canvas.axes))
        self.panel._clear()
        self.assertEqual(self.panel.model.rowCount(), 0)

    def test_use_as_window_emits_signal(self) -> None:
        self.plot.set_point_compare_enabled(True)
        self.plot._on_canvas_click(self._Event(3.0, self.plot.canvas.axes))
        self.plot._on_canvas_click(self._Event(1.0, self.plot.canvas.axes))
        captured = []
        self.panel.analysisWindowRequested.connect(lambda a, b: captured.append((a, b)))
        self.panel._use_as_window()
        self.assertEqual(captured, [(1.0, 3.0)])

    def test_replot_clears_locked_points(self) -> None:
        self.plot.set_point_compare_enabled(True)
        self.plot._on_canvas_click(self._Event(0.1, self.plot.canvas.axes))
        self.plot.generate_plot("Time", ["A"])
        self.assertEqual(len(self.cursor_vm.points), 0)


class SettingsOptionsHelperTests(unittest.TestCase):
    """The options_for helper is pure Python and does not need PySide6."""

    def test_options_for_pluralises_key(self) -> None:
        from test_data_analyser.viewmodels.settings_vm import SettingsViewModel

        class _FakeSettings:
            def get(self, section: str, key: str):
                data = {
                    "plot_appearance": {
                        "colour_cycle": "eaton",
                        "available_colour_cycles": ["eaton", "matplotlib"],
                    }
                }
                return data[section][key]

        vm = SettingsViewModel(_FakeSettings())
        self.assertEqual(vm.options_for("plot_appearance", "colour_cycle"), ["eaton", "matplotlib"])

    def test_options_for_returns_none_when_absent(self) -> None:
        from test_data_analyser.viewmodels.settings_vm import SettingsViewModel

        class _FakeSettings:
            def get(self, section: str, key: str):
                raise KeyError(key)

        self.assertIsNone(SettingsViewModel(_FakeSettings()).options_for("general_ui", "theme"))


if __name__ == "__main__":
    unittest.main()
