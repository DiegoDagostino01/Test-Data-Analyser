"""Tests for the Qt ``PandasTableModel`` adapter and the settings options helper.

These tests construct a Qt model and therefore need a ``QApplication``. They run
headless under the offscreen platform and are skipped entirely if PySide6 is not
installed, so the rest of the suite stays GUI-free.

Run with:

    python -m unittest discover -s tests
"""
from __future__ import annotations

import os
import tempfile
import unittest

import pandas as pd

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import (
        QApplication,
        QFrame,
        QGroupBox,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSplitter,
        QStackedWidget,
        QTabWidget,
    )
    from PySide6.QtTest import QTest

    from test_data_analyser.core.config import EATON_HEADER_BLUE
    from test_data_analyser.core.settings_manager import SettingsManager
    from test_data_analyser.qt_app import theme
    from test_data_analyser.qt_app.adapters import matplotlib_qt_adapter, qt_file_dialogs, qt_message_service
    from test_data_analyser.qt_app.adapters.editable_raw_data_model import EditableRawDataTableModel
    from test_data_analyser.qt_app.adapters.pandas_table_model import PandasTableModel
    from test_data_analyser.qt_app.main_window import MainWindow
    from test_data_analyser.qt_app.widgets.no_wheel_combo_box import NoWheelComboBox
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

    def test_dense_content_is_scroll_wrapped(self) -> None:
        self.assertIsInstance(self.panel.content_scroll, QScrollArea)
        self.assertFalse(self.panel.content_splitter.childrenCollapsible())
        self.assertGreaterEqual(self.panel.content_splitter.minimumHeight(), 340)


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

    def test_dense_content_is_scroll_wrapped(self) -> None:
        self.assertIsInstance(self.panel.content_scroll, QScrollArea)
        self.assertFalse(self.panel.content_splitter.childrenCollapsible())
        self.assertGreaterEqual(self.panel.content_splitter.minimumHeight(), 380)

    def test_margin_summary_is_separate_panel(self) -> None:
        self.assertIsNot(self.panel.summary_panel.parentWidget(), self.panel)
        self.assertEqual(self.panel.summary_text.parentWidget(), self.panel.summary_panel)

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
        self.assertTrue(self.panel.clear_notes())
        self.assertEqual(self.panel._editors["actions"].toPlainText(), "")

    def test_notes_actions_are_not_embedded_in_panel(self) -> None:
        self.assertEqual(self.panel.findChildren(QPushButton), [])


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
        self.assertEqual(self._checkable_count(self.panel.y_list), 2)
        self.assertEqual(self._checkable_count(self.panel.secondary_y_list), 2)

    @staticmethod
    def _checkable_count(widget) -> int:
        return sum(
            1
            for row in range(widget.count())
            if widget.item(row).flags() & Qt.ItemFlag.ItemIsUserCheckable
        )

    @staticmethod
    def _checkable_texts(widget) -> list[str]:
        return [
            widget.item(row).text()
            for row in range(widget.count())
            if widget.item(row).flags() & Qt.ItemFlag.ItemIsUserCheckable
        ]

    @staticmethod
    def _checked_texts(widget) -> list[str]:
        return [
            widget.item(row).text()
            for row in range(widget.count())
            if widget.item(row).flags() & Qt.ItemFlag.ItemIsUserCheckable
            and widget.item(row).checkState() == Qt.CheckState.Checked
        ]

    def test_y_axis_lists_are_alphabetical(self) -> None:
        self.panel.set_columns(["Time", "Zeta", "alpha", "Beta", "A10", "A2"], "Time")
        expected = ["A2", "A10", "alpha", "Beta", "Zeta"]
        self.assertEqual(self._checkable_texts(self.panel.y_list), expected)
        self.assertEqual(self._checkable_texts(self.panel.secondary_y_list), expected)

    def test_primary_and_secondary_lists_have_equal_sizing(self) -> None:
        self.assertEqual(self.panel.y_list.minimumHeight(), self.panel.secondary_y_list.minimumHeight())
        self.assertEqual(self.panel.y_list.maximumHeight(), self.panel.secondary_y_list.maximumHeight())

    def test_compact_controls_expand_with_available_width(self) -> None:
        self.assertLessEqual(self.panel.minimumWidth(), 240)
        for widget in [
            self.panel.primary_select_all_button,
            self.panel.primary_clear_all_button,
            self.panel.secondary_select_all_button,
            self.panel.secondary_clear_all_button,
            self.panel.plot_kind_combo,
            self.panel.xmin_edit,
            self.panel.xmax_edit,
            self.panel.cutoff_edit,
            self.panel.order_edit,
        ]:
            self.assertEqual(widget.minimumWidth(), 0)
            self.assertEqual(widget.sizePolicy().horizontalPolicy(), QSizePolicy.Policy.Expanding)

    def test_secondary_selection(self) -> None:
        for row in range(self.panel.secondary_y_list.count()):
            item = self.panel.secondary_y_list.item(row)
            if item.text() == "B":
                item.setCheckState(Qt.CheckState.Checked)
        self.assertEqual(self.panel.selected_secondary_y(), ["B"])

    def test_clicking_primary_row_toggles_channel(self) -> None:
        self.panel.show()
        QApplication.processEvents()
        for row in range(self.panel.y_list.count()):
            item = self.panel.y_list.item(row)
            if item.text() == "A":
                rect = self.panel.y_list.visualItemRect(item)
                point = rect.center()
                point.setX(rect.right() - 2)
                QTest.mouseClick(
                    self.panel.y_list.viewport(),
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier,
                    point,
                )
                break
        self.assertEqual(self.panel.selected_y(), ["A"])

    def test_clicking_secondary_row_toggles_channel(self) -> None:
        self.panel.show()
        QApplication.processEvents()
        for row in range(self.panel.secondary_y_list.count()):
            item = self.panel.secondary_y_list.item(row)
            if item.text() == "B":
                rect = self.panel.secondary_y_list.visualItemRect(item)
                point = rect.center()
                point.setX(rect.right() - 2)
                QTest.mouseClick(
                    self.panel.secondary_y_list.viewport(),
                    Qt.MouseButton.LeftButton,
                    Qt.KeyboardModifier.NoModifier,
                    point,
                )
                break
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

    def test_axes_figure_options_are_not_duplicated_in_left_panel(self) -> None:
        group_titles = [group.title() for group in self.panel.findChildren(QGroupBox)]
        self.assertNotIn("Plot Labels", group_titles)
        self.assertNotIn("Axis Limits", group_titles)
        self.assertNotIn("Filter / FFT", group_titles)
        self.assertIn("Filter", group_titles)

    def test_channel_group_filter_preserves_checked_items(self) -> None:
        self.panel.set_columns(["Time", "Outlet Pressure", "Current on Phase A", "Voltage"], "Time")
        for row in range(self.panel.y_list.count()):
            item = self.panel.y_list.item(row)
            if item.text() == "Current on Phase A":
                item.setCheckState(Qt.CheckState.Checked)
        self.panel.group_combo.setCurrentText("Pressure")
        self.assertEqual(self.panel.y_list.count(), 1)
        self.assertEqual(self.panel.y_list.item(0).text(), "Outlet Pressure")
        self.assertEqual(self.panel.selected_y(), ["Current on Phase A"])
        self.panel.group_combo.setCurrentText("All")
        group_headers = [self.panel.y_list.item(row).text() for row in range(self.panel.y_list.count())]
        self.assertIn("Pressure", group_headers)
        self.assertIn("Current", group_headers)
        checked = [
            self.panel.y_list.item(row).text()
            for row in range(self.panel.y_list.count())
            if self.panel.y_list.item(row).checkState() == Qt.CheckState.Checked
        ]
        self.assertEqual(checked, ["Current on Phase A"])

    def test_primary_select_all_respects_channel_group(self) -> None:
        self.panel.set_columns(["Time", "TC1", "TC2", "Outlet Pressure"], "Time")
        self.panel.group_combo.setCurrentText("Temperature")
        self.panel.primary_select_all_button.click()
        self.assertEqual(self.panel.selected_y(), ["TC1", "TC2"])
        self.assertEqual(self.panel.selected_secondary_y(), [])

    def test_primary_clear_all_clears_hidden_group_selections(self) -> None:
        self.panel.set_columns(["Time", "TC1", "Outlet Pressure", "Current on Phase A"], "Time")
        self.panel.primary_select_all_button.click()
        self.panel.group_combo.setCurrentText("Temperature")
        self.panel.primary_clear_all_button.click()
        self.assertEqual(self.panel.selected_y(), [])
        self.panel.group_combo.setCurrentText("All")
        self.assertEqual(self._checked_texts(self.panel.y_list), [])

    def test_secondary_buttons_are_independent_from_primary_buttons(self) -> None:
        self.panel.set_columns(["Time", "TC1", "Outlet Pressure"], "Time")
        self.panel.group_combo.setCurrentText("Pressure")
        self.panel.secondary_select_all_button.click()
        self.assertEqual(self.panel.selected_y(), [])
        self.assertEqual(self.panel.selected_secondary_y(), ["Outlet Pressure"])

        self.panel.group_combo.setCurrentText("Temperature")
        self.panel.primary_select_all_button.click()
        self.assertEqual(self.panel.selected_y(), ["TC1"])
        self.assertEqual(self.panel.selected_secondary_y(), ["Outlet Pressure"])

        self.panel.secondary_clear_all_button.click()
        self.assertEqual(self.panel.selected_y(), ["TC1"])
        self.assertEqual(self.panel.selected_secondary_y(), [])


class _PaddingSettingsVM:
    """Settings-VM stand-in returning controlled axis-padding values."""

    def __init__(self, overrides: dict | None = None) -> None:
        self._overrides = overrides or {}

    def get(self, section, key, default=None):
        return self._overrides.get((section, key), default)


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

    def test_plot_labels_and_axis_limits_are_applied(self) -> None:
        result = self.panel.generate_plot(
            "Time",
            ["A"],
            title="Pump Run",
            x_label="Seconds",
            y_label="Pressure",
            axis_limits={"xmin": 0.2, "xmax": 0.8, "ymin": -0.5, "ymax": 0.5},
            auto_fit_axes=False,
        )
        self.assertTrue(result.ok, result.message)
        self.assertEqual(self.panel.canvas.axes.get_title(), "Pump Run")
        self.assertEqual(self.panel.canvas.axes.get_xlabel(), "Seconds")
        self.assertEqual(self.panel.canvas.axes.get_ylabel(), "Pressure")
        self.assertEqual(tuple(round(value, 1) for value in self.panel.canvas.axes.get_xlim()), (0.2, 0.8))
        self.assertEqual(tuple(round(value, 1) for value in self.panel.canvas.axes.get_ylim()), (-0.5, 0.5))

    def test_legend_panel_includes_secondary_channels_without_canvas_legend(self) -> None:
        result = self.panel.generate_plot("Time", ["A", "B"], secondary_y=["B"])
        self.assertTrue(result.ok, result.message)
        self.assertFalse(self.panel.legend_panel.isHidden())
        self.assertIsNone(self.panel.canvas.axes.get_legend())
        self.assertEqual(self.panel.legend_table.rowCount(), 2)
        table_labels = [self.panel.legend_table.item(row, 1).text() for row in range(self.panel.legend_table.rowCount())]
        self.assertIn("A", table_labels)
        self.assertIn("B [Right Y]", table_labels)

    def test_graph_legend_mode_hides_panel_and_draws_canvas_legend(self) -> None:
        self.panel.set_legend_display("graph")
        result = self.panel.generate_plot("Time", ["A", "B"], secondary_y=["B"])
        self.assertTrue(result.ok, result.message)
        self.assertTrue(self.panel.legend_panel.isHidden())
        legend = self.panel.canvas.axes.get_legend()
        self.assertIsNotNone(legend)
        assert legend is not None
        labels = [text.get_text() for text in legend.get_texts()]
        self.assertIn("A", labels)
        self.assertIn("B [Right Y]", labels)

    def test_switching_back_to_panel_removes_canvas_legend(self) -> None:
        self.panel.generate_plot("Time", ["A"])
        self.panel.set_legend_display("graph")
        self.assertIsNotNone(self.panel.canvas.axes.get_legend())
        self.panel.set_legend_display("panel")
        self.assertFalse(self.panel.legend_panel.isHidden())
        self.assertIsNone(self.panel.canvas.axes.get_legend())

    def test_toolbar_keeps_navigation_and_promotes_edit_axis(self) -> None:
        toolbar = self.panel.canvas.toolbar
        tool_names = [item[0] for item in toolbar.toolitems if item[0]]
        self.assertIn("Pan", tool_names)
        self.assertIn("Zoom", tool_names)
        self.assertNotIn("Subplots", tool_names)
        self.assertNotIn("Customize", tool_names)
        self.assertNotIn("Save", tool_names)

        self.assertEqual(toolbar.edit_axis_button.text(), "Edit Axis")
        self.assertEqual(toolbar.edit_axis_button.objectName(), "PrimaryButton")
        self.assertIsInstance(toolbar.edit_axis_button, QPushButton)
        action_labels = [action.text().replace("&", "") for action in toolbar.actions() if action.text()]
        self.assertIn("Edit Axis", action_labels)
        self.assertNotIn("Save", action_labels)

    def test_figure_options_includes_legend_tab(self) -> None:
        captured: dict[str, object] = {}
        original_figure_edit = matplotlib_qt_adapter.figureoptions.figure_edit
        original_fedit = matplotlib_qt_adapter._formlayout.fedit

        def fake_figure_edit(axes, parent):
            def apply(data):
                captured["matplotlib_data"] = data

            matplotlib_qt_adapter._formlayout.fedit(
                [([("Title", "")], "Axes", "")],
                title="Figure options",
                parent=parent,
                apply=apply,
            )

        def fake_fedit(data, title="", comment="", icon=None, parent=None, apply=None):
            captured["tabs"] = [section[1] for section in data]
            if apply is not None:
                apply([["updated title"], ["graph"]])

        matplotlib_qt_adapter.figureoptions.figure_edit = fake_figure_edit
        matplotlib_qt_adapter._formlayout.fedit = fake_fedit
        try:
            self.panel.canvas.toolbar._figure_edit_with_legend(self.panel.canvas.axes)
        finally:
            matplotlib_qt_adapter.figureoptions.figure_edit = original_figure_edit
            matplotlib_qt_adapter._formlayout.fedit = original_fedit

        self.assertEqual(captured["tabs"], ["Axes", "Legend"])
        self.assertEqual(captured["matplotlib_data"], [["updated title"]])
        self.assertEqual(self.panel.legend_display(), "graph")

    def test_panel_legend_is_rendered_into_saved_figure(self) -> None:
        self.panel.generate_plot("Time", ["A", "B"], secondary_y=["B"])
        self.assertIsNone(self.panel.canvas.axes.get_legend())
        captured: dict[str, object] = {}
        original_base_save = matplotlib_qt_adapter.NavigationToolbar2QT.save_figure

        def fake_base_save(toolbar, *args):
            legend = self.panel.canvas.axes.get_legend()
            captured["labels"] = [text.get_text() for text in legend.get_texts()] if legend else None

        matplotlib_qt_adapter.NavigationToolbar2QT.save_figure = fake_base_save
        try:
            self.panel.canvas.toolbar.save_figure()
        finally:
            matplotlib_qt_adapter.NavigationToolbar2QT.save_figure = original_base_save

        labels = captured["labels"]
        self.assertIsNotNone(labels)
        assert labels is not None
        self.assertIn("A", labels)
        self.assertIn("B [Right Y]", labels)
        # The temporary export legend is removed afterwards so the screen stays clean.
        self.assertIsNone(self.panel.canvas.axes.get_legend())

    def test_graph_legend_is_preserved_when_saving_figure(self) -> None:
        self.panel.set_legend_display("graph")
        self.panel.generate_plot("Time", ["A"])
        self.assertIsNotNone(self.panel.canvas.axes.get_legend())
        captured: dict[str, object] = {}
        original_base_save = matplotlib_qt_adapter.NavigationToolbar2QT.save_figure

        def fake_base_save(toolbar, *args):
            captured["had_legend"] = self.panel.canvas.axes.get_legend() is not None

        matplotlib_qt_adapter.NavigationToolbar2QT.save_figure = fake_base_save
        try:
            self.panel.canvas.toolbar.save_figure()
        finally:
            matplotlib_qt_adapter.NavigationToolbar2QT.save_figure = original_base_save

        self.assertTrue(captured["had_legend"])
        self.assertIsNotNone(self.panel.canvas.axes.get_legend())

    def _panel_with_padding(self, overrides):
        from test_data_analyser.qt_app.widgets.plot_workspace import PlotWorkspace

        return PlotWorkspace(self.plot_vm, _PaddingSettingsVM(overrides))

    def test_axis_padding_defaults_to_five_percent(self) -> None:
        panel = self._panel_with_padding({})
        panel.generate_plot("Time", ["A"])
        xmin, xmax = panel.canvas.axes.get_xlim()
        # Data X spans exactly [0, 1]; the default 5% padding expands both ends.
        self.assertAlmostEqual(xmin, -0.05, places=3)
        self.assertAlmostEqual(xmax, 1.05, places=3)

    def test_disabling_x_padding_removes_x_margin(self) -> None:
        panel = self._panel_with_padding({("axis_scaling", "pad_x_axis"): False})
        panel.generate_plot("Time", ["A"])
        xmin, xmax = panel.canvas.axes.get_xlim()
        self.assertAlmostEqual(xmin, 0.0, places=6)
        self.assertAlmostEqual(xmax, 1.0, places=6)

    def test_custom_x_padding_percent_is_applied(self) -> None:
        panel = self._panel_with_padding({("axis_scaling", "pad_x_percent"): 10})
        panel.generate_plot("Time", ["A"])
        xmin, xmax = panel.canvas.axes.get_xlim()
        self.assertAlmostEqual(xmin, -0.10, places=3)
        self.assertAlmostEqual(xmax, 1.10, places=3)

    def test_current_axis_appearance_reads_live_axes(self) -> None:
        self.panel.generate_plot("Time", ["A"])
        # Simulate Figure Options edits applied directly to the axes.
        self.panel.canvas.axes.set_title("Edited Title")
        self.panel.canvas.axes.set_xlabel("Edited X")
        self.panel.canvas.axes.set_ylabel("Edited Y")
        self.panel.canvas.axes.set_xlim(0.1, 0.9)
        self.panel.canvas.axes.set_ylim(-2.0, 2.0)

        appearance = self.panel.current_axis_appearance()
        self.assertEqual(appearance["title"], "Edited Title")
        self.assertEqual(appearance["x_label"], "Edited X")
        self.assertEqual(appearance["y_label"], "Edited Y")
        self.assertFalse(appearance["auto_fit_axes"])
        self.assertAlmostEqual(float(appearance["axis_limits"]["xmin"]), 0.1, places=3)
        self.assertAlmostEqual(float(appearance["axis_limits"]["xmax"]), 0.9, places=3)
        self.assertAlmostEqual(float(appearance["axis_limits"]["ymin"]), -2.0, places=3)
        self.assertAlmostEqual(float(appearance["axis_limits"]["ymax"]), 2.0, places=3)

    def test_current_axis_appearance_empty_without_plot(self) -> None:
        self.assertEqual(self.panel.current_axis_appearance().get("title", None), "")

    def test_save_plot_png_writes_file(self) -> None:
        self.panel.generate_plot("Time", ["A"])
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "plot.png")
            result = self.panel.save_plot_png(path)
            self.assertTrue(result.ok, result.message)
            self.assertTrue(os.path.exists(path))

    def test_save_plot_png_appends_extension(self) -> None:
        self.panel.generate_plot("Time", ["A"])
        with tempfile.TemporaryDirectory() as directory:
            base = os.path.join(directory, "plot")
            result = self.panel.save_plot_png(base)
            self.assertTrue(result.ok, result.message)
            self.assertTrue(os.path.exists(base + ".png"))

    def test_save_plot_png_requires_a_plot(self) -> None:
        result = self.panel.save_plot_png("unused.png")
        self.assertFalse(result.ok)

    def test_clear_plot_removes_drawn_content(self) -> None:
        self.panel.generate_plot("Time", ["A", "B"], secondary_y=["B"])
        self.assertEqual(len(self.panel.canvas.figure.axes), 2)
        self.assertTrue(self.panel.canvas.axes.get_lines())
        self.assertGreater(self.panel.legend_table.rowCount(), 0)

        result = self.panel.clear_plot()

        self.assertTrue(result.ok, result.message)
        self.assertEqual(len(self.panel.canvas.figure.axes), 1)
        self.assertFalse(self.panel.canvas.axes.get_lines())
        self.assertFalse(self.panel.canvas.axes.collections)
        self.assertEqual(self.panel.legend_table.rowCount(), 0)
        self.assertFalse(self.panel.save_plot_png("unused.png").ok)


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class SettingsDialogTests(unittest.TestCase):
    def setUp(self) -> None:
        from test_data_analyser.qt_app.widgets.settings_dialog import SettingsDialog

        self._tmp = tempfile.TemporaryDirectory()
        manager = SettingsManager(os.path.join(self._tmp.name, "settings.json"))
        self.vm = SettingsViewModel(manager)
        self.dialog = SettingsDialog(self.vm)

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_axis_padding_fields_present(self) -> None:
        self.assertIn(("axis_scaling", "pad_x_axis"), self.dialog._editors)
        self.assertIn(("axis_scaling", "pad_x_percent"), self.dialog._editors)
        self.assertIn(("axis_scaling", "pad_y_axis"), self.dialog._editors)
        self.assertIn(("axis_scaling", "pad_y_percent"), self.dialog._editors)

    def test_save_persists_axis_padding_and_combo_fields(self) -> None:
        self.dialog._editors[("axis_scaling", "pad_x_axis")].setChecked(False)
        self.dialog._editors[("axis_scaling", "pad_y_percent")].setValue(12.0)
        self.dialog._on_save()
        self.assertFalse(self.vm.get("axis_scaling", "pad_x_axis"))
        self.assertEqual(self.vm.get("axis_scaling", "pad_y_percent"), 12.0)
        # The combo save path must not raise (regression guard for QComboBox import).
        self.assertIn(self.vm.get("general_ui", "theme"), ("light", "dark"))


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


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class NoWheelComboBoxTests(unittest.TestCase):
    """The critical comboboxes ignore mouse-wheel scrolling to avoid accidental changes."""

    def test_plot_kind_combo_is_no_wheel(self) -> None:
        from test_data_analyser.qt_app.widgets.axis_selection_panel import AxisSelectionPanel

        panel = AxisSelectionPanel()
        self.assertIsInstance(panel.plot_kind_combo, NoWheelComboBox)
        self.assertIsInstance(panel.x_combo, NoWheelComboBox)

    def test_wheel_event_is_ignored_and_selection_unchanged(self) -> None:
        combo = NoWheelComboBox()
        combo.addItems(["Line", "Scatter", "Line + Markers"])
        combo.setCurrentIndex(1)

        class _StubWheelEvent:
            def __init__(self) -> None:
                self.ignored = False

            def ignore(self) -> None:
                self.ignored = True

        event = _StubWheelEvent()
        combo.wheelEvent(event)  # type: ignore[arg-type]
        self.assertTrue(event.ignored)
        self.assertEqual(combo.currentIndex(), 1)


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class OpenDataFileInitialDirTests(unittest.TestCase):
    """File dialog wrappers accept initial directories without breaking callers."""

    def setUp(self) -> None:
        self._original_dialog = qt_file_dialogs.QFileDialog
        self.captured: dict[str, object] = {}

        outer = self

        class _FakeDialog:
            @staticmethod
            def getOpenFileName(parent, caption, directory, filt):
                outer.captured["caption"] = caption
                outer.captured["directory"] = directory
                return ("C:/data/file.csv", filt)

            @staticmethod
            def getSaveFileName(parent, caption, directory, filt):
                outer.captured["caption"] = caption
                outer.captured["directory"] = directory
                return ("C:/sessions/analysis.json", filt)

        qt_file_dialogs.QFileDialog = _FakeDialog

    def tearDown(self) -> None:
        qt_file_dialogs.QFileDialog = self._original_dialog

    def test_initial_directory_is_passed_through(self) -> None:
        result = qt_file_dialogs.open_data_file(None, "C:/data")
        self.assertEqual(result, "C:/data/file.csv")
        self.assertEqual(self.captured["directory"], "C:/data")

    def test_default_directory_is_blank(self) -> None:
        result = qt_file_dialogs.open_data_file(None)
        self.assertEqual(result, "C:/data/file.csv")
        self.assertEqual(self.captured["directory"], "")

    def test_open_session_initial_directory_is_passed_through(self) -> None:
        result = qt_file_dialogs.open_session_file(None, "C:/sessions")
        self.assertEqual(result, "C:/data/file.csv")
        self.assertEqual(self.captured["caption"], "Load analysis session")
        self.assertEqual(self.captured["directory"], "C:/sessions")

    def test_save_session_initial_directory_is_passed_through(self) -> None:
        result = qt_file_dialogs.save_session_file(None, "C:/sessions")
        self.assertEqual(result, "C:/sessions/analysis.json")
        self.assertEqual(self.captured["caption"], "Save analysis session")
        self.assertEqual(self.captured["directory"], "C:/sessions")


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class MainWindowLayoutTests(unittest.TestCase):
    """The main window builds offscreen with a ribbon and smooth splitter."""

    def _window(self) -> "MainWindow":
        directory = tempfile.mkdtemp()
        manager = SettingsManager(os.path.join(directory, "settings.json"))
        return MainWindow(manager)

    def test_header_logo_builds(self) -> None:
        window = self._window()
        logo = window._build_logo_label()
        self.assertIsNotNone(logo)
        assert logo is not None  # narrow for the type checker
        self.assertFalse(logo.pixmap().isNull())

    def test_plot_and_lower_splitter_can_fully_collapse(self) -> None:
        window = self._window()
        window.show()
        QApplication.processEvents()
        self.assertTrue(window.right_splitter.childrenCollapsible())
        self.assertTrue(window.right_splitter.isCollapsible(0))
        self.assertTrue(window.right_splitter.isCollapsible(1))
        self.assertGreaterEqual(window.plot_workspace.minimumHeight(), 260)
        self.assertGreaterEqual(window.lower_stack.minimumHeight(), 150)

        total_height = sum(window.right_splitter.sizes())
        window.right_splitter.setSizes([100, total_height - 100])
        QApplication.processEvents()
        self.assertGreaterEqual(window.right_splitter.sizes()[0], window.plot_workspace.minimumHeight())

        total_height = sum(window.right_splitter.sizes())
        window.right_splitter.setSizes([total_height, 0])
        QApplication.processEvents()
        self.assertEqual(window.right_splitter.sizes()[1], 0)

        total_height = sum(window.right_splitter.sizes())
        window.right_splitter.setSizes([0, total_height])
        QApplication.processEvents()
        self.assertEqual(window.right_splitter.sizes()[0], 0)

    def test_plot_layout_refreshes_when_splitter_shrinks(self) -> None:
        window = self._window()
        window.vm.state.df = pd.DataFrame({"Time": [0.0, 1.0, 2.0], "A": [1.0, 3.0, 2.0]})
        window.axis_panel.apply_selection(["Time", "A"], "Time", ["A"], [])
        window.show()
        QApplication.processEvents()

        result = window._generate_plot(
            {"title": "A Long Plot Title", "x_label": "Time (s)", "y_label": "Amplitude"}
        )
        self.assertIsNotNone(result)
        assert result is not None
        self.assertTrue(result.ok, result.message)

        total_height = sum(window.right_splitter.sizes())
        window.right_splitter.setSizes(
            [window.plot_workspace.minimumHeight(), total_height - window.plot_workspace.minimumHeight()]
        )
        QApplication.processEvents()

        plot_canvas = window.plot_workspace.canvas
        plot_canvas.canvas.draw()
        renderer = plot_canvas.canvas.get_renderer()
        figure_bbox = plot_canvas.figure.bbox
        for artist in (plot_canvas.axes.title, plot_canvas.axes.xaxis.label):
            bbox = artist.get_window_extent(renderer)
            self.assertGreaterEqual(bbox.y0, figure_bbox.y0)
            self.assertLessEqual(bbox.y1, figure_bbox.y1)

    def test_ribbon_has_required_groups_and_commands(self) -> None:
        window = self._window()
        self.assertFalse(hasattr(window, "header_tab_bar"))
        self.assertIsInstance(window.findChild(QFrame, "RibbonBar"), QFrame)
        self.assertIs(window.findChild(QFrame, "RibbonBar"), window.ribbon)
        self.assertIsInstance(window.findChild(QFrame, "CollapsedRibbonBar"), QFrame)
        self.assertTrue(window.collapsed_ribbon_bar.isHidden())
        self.assertTrue(window.show_ribbon_action.isChecked())
        self.assertEqual(window.hide_ribbon_button.text(), "Hide Ribbon")
        self.assertEqual(window.show_ribbon_button.text(), "Show Ribbon")
        collapsed_layout = window.collapsed_ribbon_bar.layout()
        self.assertEqual(collapsed_layout.itemAt(collapsed_layout.count() - 1).widget(), window.show_ribbon_button)
        for key in [
            "FILE:Open Data",
            "FILE:Save Session",
            "FILE:Load Session",
            "FILE:Export Data",
            "PLOT:Generate Plot",
            "PLOT:FFT",
            "PLOT:Save Plot",
            "PLOT:Clear Plot",
            "PLOT:Runs / Comparison",
            "ANALYSIS:Statistics",
            "ANALYSIS:Raw Data",
            "ANALYSIS:Maths Channels",
            "ANALYSIS:Cursor",
            "REQUIREMENTS:Limits",
            "REQUIREMENTS:Margins",
            "REQUIREMENTS:Refresh",
            "NOTES:Engineering Notes",
            "NOTES:Refresh Report Text",
            "NOTES:Clear Notes",
            "NOTES:Copy Notes",
        ]:
            self.assertIn(key, window.ribbon_buttons)
        self.assertIsInstance(window.lower_stack, QStackedWidget)
        self.assertEqual(window.lower_stack.count(), 4)
        self.assertEqual(window.right_panel.layout().itemAt(0).widget(), window.right_splitter)

    def test_ribbon_can_be_collapsed_and_restored(self) -> None:
        window = self._window()
        self.assertFalse(window.ribbon.isHidden())
        self.assertTrue(window.collapsed_ribbon_bar.isHidden())

        window.hide_ribbon_button.click()
        self.assertTrue(window.ribbon.isHidden())
        self.assertFalse(window.collapsed_ribbon_bar.isHidden())
        self.assertFalse(window.show_ribbon_action.isChecked())
        self.assertEqual(window.statusBar().currentMessage(), "Ribbon hidden.")

        window.show_ribbon_button.click()
        self.assertFalse(window.ribbon.isHidden())
        self.assertTrue(window.collapsed_ribbon_bar.isHidden())
        self.assertTrue(window.show_ribbon_action.isChecked())
        self.assertEqual(window.statusBar().currentMessage(), "Ribbon shown.")

        window.show_ribbon_action.setChecked(False)
        self.assertTrue(window.ribbon.isHidden())
        self.assertFalse(window.collapsed_ribbon_bar.isHidden())
        window.show_ribbon_action.setChecked(True)
        self.assertFalse(window.ribbon.isHidden())

    def test_ribbon_navigation_switches_lower_stack(self) -> None:
        window = self._window()
        window.ribbon_buttons["ANALYSIS:Statistics"].click()
        self.assertIs(window.lower_stack.currentWidget(), window.analysis_stack)
        window.ribbon_buttons["NOTES:Engineering Notes"].click()
        self.assertIs(window.lower_stack.currentWidget(), window.notes_panel)

    def test_notes_ribbon_actions_refresh_and_clear_panel(self) -> None:
        from test_data_analyser.qt_app.widgets import engineering_notes_panel as panel_module

        window = self._window()
        window.notes_panel._editors["objective"].setPlainText("Summarise this run.")
        window.ribbon_buttons["NOTES:Refresh Report Text"].click()
        self.assertIs(window.lower_stack.currentWidget(), window.notes_panel)
        self.assertIn("Summarise this run.", window.notes_panel.report_text.toPlainText())

        original_confirm = panel_module.qt_message_service.confirm
        panel_module.qt_message_service.confirm = lambda *args, **kwargs: True
        try:
            window.ribbon_buttons["NOTES:Clear Notes"].click()
        finally:
            panel_module.qt_message_service.confirm = original_confirm
        self.assertEqual(window.notes_panel._editors["objective"].toPlainText(), "")
        self.assertEqual(window.statusBar().currentMessage(), "Engineering notes cleared.")

    def test_plot_actions_moved_to_ribbon(self) -> None:
        window = self._window()
        self.assertEqual(window.lower_stack.currentIndex(), 0)
        self.assertIs(window.lower_stack.currentWidget(), window.plot_group)
        self.assertIsInstance(window.ribbon_buttons["PLOT:Generate Plot"], QPushButton)
        self.assertIsInstance(window.ribbon_buttons["PLOT:Save Plot"], QPushButton)
        self.assertTrue(window.ribbon_buttons["PLOT:Clear Plot"].isEnabled())
        self.assertEqual(window.plot_group.count(), 2)
        self.assertIs(window.plot_group.currentWidget(), window.runs_panel)

    def test_lower_middle_tab_widgets_are_removed(self) -> None:
        window = self._window()
        self.assertEqual(window.findChildren(QTabWidget), [])

    def test_duplicate_left_side_open_and_generate_buttons_are_removed(self) -> None:
        window = self._window()
        left_button_labels = [button.text() for button in window.data_panel.findChildren(QPushButton)]
        left_button_labels += [button.text() for button in window.axis_panel.findChildren(QPushButton)]
        self.assertNotIn("Open Data File…", left_button_labels)
        self.assertNotIn("Generate Plot", left_button_labels)
        self.assertNotIn("FFT", left_button_labels)

    def test_clear_plot_ribbon_command_clears_canvas(self) -> None:
        window = self._window()
        window.vm.state.df = pd.DataFrame({"Time": [0.0, 1.0], "A": [1.0, 2.0]})
        result = window.plot_workspace.generate_plot("Time", ["A"])
        self.assertTrue(result.ok, result.message)
        window._plot_generated = True

        window.ribbon_buttons["PLOT:Clear Plot"].click()

        self.assertFalse(window._plot_generated)
        self.assertFalse(window.plot_workspace.canvas.axes.get_lines())
        self.assertEqual(window.plot_workspace.legend_table.rowCount(), 0)
        self.assertEqual(window.statusBar().currentMessage(), "Plot cleared.")

    def test_inspector_and_quality_commands_are_removed(self) -> None:
        window = self._window()
        self.assertNotIn("ANALYSIS:Inspector", window.ribbon_buttons)
        self.assertNotIn("ANALYSIS:Quality", window.ribbon_buttons)

    def test_analysis_group_reaches_maths_panel(self) -> None:
        window = self._window()
        window.ribbon_buttons["ANALYSIS:Maths Channels"].click()
        self.assertIs(window.lower_stack.currentWidget(), window.analysis_stack)
        self.assertIs(window.analysis_stack.currentWidget(), window.maths_panel)

    def test_ribbon_reaches_raw_data_and_cursor_panels(self) -> None:
        window = self._window()
        window.ribbon_buttons["ANALYSIS:Raw Data"].click()
        self.assertIs(window.lower_stack.currentWidget(), window.analysis_stack)
        self.assertIs(window.analysis_stack.currentWidget(), window.raw_data_panel)
        window.ribbon_buttons["ANALYSIS:Cursor"].click()
        self.assertIs(window.lower_stack.currentWidget(), window.plot_group)
        self.assertIs(window.plot_group.currentWidget(), window.cursor_panel)
        window.ribbon_buttons["PLOT:Runs / Comparison"].click()
        self.assertIs(window.plot_group.currentWidget(), window.runs_panel)

    def test_requirements_group_has_margin_sub_tab(self) -> None:
        window = self._window()
        window.ribbon_buttons["REQUIREMENTS:Margins"].click()
        self.assertIs(window.lower_stack.currentWidget(), window.requirements_stack)
        self.assertIs(window.requirements_stack.currentWidget(), window.limits_panel.summary_panel)
        window.ribbon_buttons["REQUIREMENTS:Limits"].click()
        self.assertIs(window.requirements_stack.currentWidget(), window.limits_panel)

    def test_ribbon_styling_present(self) -> None:
        stylesheet = theme.build_stylesheet("light")
        self.assertIn("QFrame#RibbonBar", stylesheet)
        self.assertIn("QLabel#RibbonGroupLabel", stylesheet)
        self.assertNotIn("QTabBar#HeaderTabs", stylesheet)

    def test_header_labels_use_header_background(self) -> None:
        stylesheet = theme.build_stylesheet("light")
        self.assertIn("QFrame#EatonHeader QLabel", stylesheet)
        self.assertIn(f"background-color: {EATON_HEADER_BLUE};", stylesheet)

    def test_left_controls_are_scrollable(self) -> None:
        window = self._window()
        self.assertIsInstance(window.left_scroll, QScrollArea)
        self.assertTrue(window.left_scroll.widgetResizable())
        self.assertEqual(window.left_scroll.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.assertEqual(window.axis_panel.sizePolicy().verticalPolicy(), QSizePolicy.Policy.Expanding)

    def test_left_rail_opens_wide_but_can_shrink(self) -> None:
        window = self._window()
        window.show()
        QApplication.processEvents()
        self.assertIsInstance(window.body_splitter, QSplitter)
        self.assertFalse(window.body_splitter.childrenCollapsible())
        self.assertEqual(window.left_scroll.minimumWidth(), MainWindow.LEFT_RAIL_MINIMUM_WIDTH)
        self.assertLess(window.left_scroll.minimumWidth(), MainWindow.LEFT_RAIL_INITIAL_WIDTH)
        self.assertGreaterEqual(window.body_splitter.sizes()[0], MainWindow.LEFT_RAIL_INITIAL_WIDTH - 5)
        self.assertEqual(window.lower_stack.sizePolicy().horizontalPolicy(), QSizePolicy.Policy.Ignored)

    def test_load_session_uses_remembered_session_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session_dir = os.path.join(directory, "sessions")
            os.mkdir(session_dir)
            manager = SettingsManager(os.path.join(directory, "settings.json"))
            manager.set("general_ui", "last_session_directory", session_dir)
            window = MainWindow(manager)

            original = qt_file_dialogs.open_session_file
            captured: dict[str, str] = {}

            def fake_open(parent, initial_dir=""):
                captured["initial_dir"] = initial_dir
                return None

            qt_file_dialogs.open_session_file = fake_open
            try:
                window.load_session()
            finally:
                qt_file_dialogs.open_session_file = original
            self.assertEqual(captured["initial_dir"], session_dir)

    def test_save_session_updates_remembered_session_directory(self) -> None:
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            initial_dir = os.path.join(directory, "initial")
            selected_dir = os.path.join(directory, "selected")
            os.mkdir(initial_dir)
            os.mkdir(selected_dir)
            manager = SettingsManager(os.path.join(directory, "settings.json"))
            manager.set("general_ui", "last_session_directory", initial_dir)
            window = MainWindow(manager)

            original_save_dialog = qt_file_dialogs.save_session_file
            original_show_result = qt_message_service.show_result
            captured: dict[str, str] = {}
            save_path = os.path.join(selected_dir, "analysis.json")

            class _Result:
                ok = True
                message = "Saved."

            def fake_save_dialog(parent, initial_dir=""):
                captured["initial_dir"] = initial_dir
                return save_path

            qt_file_dialogs.save_session_file = fake_save_dialog
            qt_message_service.show_result = lambda *args, **kwargs: None
            window.vm.capture_working_state = lambda **kwargs: None
            window.vm.save_session = lambda path: _Result()
            try:
                window.save_session()
            finally:
                qt_file_dialogs.save_session_file = original_save_dialog
                qt_message_service.show_result = original_show_result

            self.assertEqual(captured["initial_dir"], initial_dir)
            self.assertEqual(
                manager.get("general_ui", "last_session_directory"),
                str(Path(save_path).resolve().parent),
            )

    def test_save_session_prefers_loaded_data_directory(self) -> None:
        from pathlib import Path

        with tempfile.TemporaryDirectory() as directory:
            remembered_session_dir = os.path.join(directory, "remembered_sessions")
            data_dir = os.path.join(directory, "data")
            selected_session_dir = os.path.join(directory, "selected_sessions")
            os.mkdir(remembered_session_dir)
            os.mkdir(data_dir)
            os.mkdir(selected_session_dir)
            data_path = os.path.join(data_dir, "run.csv")
            with open(data_path, "w", encoding="utf-8") as handle:
                handle.write("Time,A\n0,1\n")

            manager = SettingsManager(os.path.join(directory, "settings.json"))
            manager.set("general_ui", "last_session_directory", remembered_session_dir)
            window = MainWindow(manager)
            window.vm.state.filepath = Path(data_path)

            original_save_dialog = qt_file_dialogs.save_session_file
            original_show_result = qt_message_service.show_result
            captured: dict[str, str] = {}
            save_path = os.path.join(selected_session_dir, "analysis.json")

            class _Result:
                ok = True
                message = "Saved."

            def fake_save_dialog(parent, initial_dir=""):
                captured["initial_dir"] = initial_dir
                return save_path

            qt_file_dialogs.save_session_file = fake_save_dialog
            qt_message_service.show_result = lambda *args, **kwargs: None
            window.vm.capture_working_state = lambda **kwargs: None
            window.vm.save_session = lambda path: _Result()
            try:
                window.save_session()
            finally:
                qt_file_dialogs.save_session_file = original_save_dialog
                qt_message_service.show_result = original_show_result

            self.assertEqual(captured["initial_dir"], str(Path(data_path).resolve().parent))
            self.assertEqual(
                manager.get("general_ui", "last_session_directory"),
                str(Path(save_path).resolve().parent),
            )


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class MainWindowSessionRestoreTests(unittest.TestCase):
    """Saving then loading a session restores the plot and all analysis panels."""

    def _make_window(self, directory: str) -> "MainWindow":
        manager = SettingsManager(os.path.join(directory, "settings.json"))
        return MainWindow(manager)

    def _save_session(self, window, session_path: str) -> None:
        original_dialog = qt_file_dialogs.save_session_file
        original_show = qt_message_service.show_result
        qt_file_dialogs.save_session_file = lambda parent, initial_dir="": session_path
        qt_message_service.show_result = lambda *args, **kwargs: None
        try:
            window.save_session()
        finally:
            qt_file_dialogs.save_session_file = original_dialog
            qt_message_service.show_result = original_show

    def _load_session(self, window, session_path: str) -> None:
        original_dialog = qt_file_dialogs.open_session_file
        original_warn = qt_message_service.warning
        qt_file_dialogs.open_session_file = lambda parent, initial_dir="": session_path
        qt_message_service.warning = lambda *args, **kwargs: None
        try:
            window.load_session()
        finally:
            qt_file_dialogs.open_session_file = original_dialog
            qt_message_service.warning = original_warn

    def test_saved_plot_and_panels_restore_on_load(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = os.path.join(directory, "data.csv")
            pd.DataFrame({"Time": [0.0, 1.0, 2.0, 3.0], "A": [1.0, 2.0, 3.0, 4.0]}).to_csv(data_path, index=False)
            session_path = os.path.join(directory, "session.json")

            source = self._make_window(directory)
            source.vm.data_loading.load_file(data_path, None)
            source._on_file_loaded(source.vm.state.column_names())
            source.vm.maths_channels.apply_channel("Sum", "A + A")
            source._on_channels_changed()
            source.vm.state.limit_lines = [
                {
                    "name": "Max",
                    "type": "Upper Limit",
                    "applies_to": "All selected Y channels",
                    "color": "#005A8C",
                    "points": [{"x": 0, "y": 10}, {"x": 3, "y": 10}],
                }
            ]
            source.limits_panel.refresh()
            source.vm.engineering_notes.update_field("objective", "Verify response")
            source.axis_panel.apply_selection(source.vm.state.column_names(), "Time", ["A"], [])
            source._on_generate_plot()
            self.assertTrue(source._plot_generated)
            self.assertTrue(source.plot_workspace.canvas.axes.get_lines())

            self._save_session(source, session_path)
            self.assertTrue(os.path.exists(session_path))

            target = self._make_window(directory)
            self.assertFalse(target.plot_workspace.canvas.axes.get_lines())
            self._load_session(target, session_path)

            # Plot regenerated from the saved session.
            self.assertTrue(target._plot_generated)
            self.assertTrue(target.plot_workspace.canvas.axes.get_lines())
            # Maths channel restored into the dataframe and panel table.
            self.assertIn("Sum", target.vm.state.df.columns)
            self.assertGreaterEqual(target.maths_panel.model.rowCount(), 1)
            # Limit line restored into state and the panel table.
            self.assertEqual(len(target.vm.state.limit_lines), 1)
            self.assertGreaterEqual(target.limits_panel.lines_model.rowCount(), 1)
            # Engineering notes restored into state and the editor field.
            self.assertEqual(target.vm.engineering_notes.get_notes()["objective"], "Verify response")
            self.assertEqual(target.notes_panel._editors["objective"].toPlainText(), "Verify response")

    def test_session_without_plot_leaves_canvas_clean(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = os.path.join(directory, "data.csv")
            pd.DataFrame({"Time": [0.0, 1.0, 2.0], "A": [1.0, 2.0, 3.0]}).to_csv(data_path, index=False)
            session_path = os.path.join(directory, "session.json")

            source = self._make_window(directory)
            source.vm.data_loading.load_file(data_path, None)
            source._on_file_loaded(source.vm.state.column_names())
            source.axis_panel.apply_selection(source.vm.state.column_names(), "Time", ["A"], [])
            # No _on_generate_plot call: nothing was plotted.
            self._save_session(source, session_path)

            target = self._make_window(directory)
            self._load_session(target, session_path)
            self.assertFalse(target._plot_generated)
            self.assertFalse(target.plot_workspace.canvas.axes.get_lines())

    def test_save_plot_handler_writes_png_via_dialog(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = os.path.join(directory, "data.csv")
            pd.DataFrame({"Time": [0.0, 1.0, 2.0, 3.0], "A": [1.0, 2.0, 3.0, 4.0]}).to_csv(data_path, index=False)
            out_path = os.path.join(directory, "export.png")

            window = self._make_window(directory)
            window.vm.data_loading.load_file(data_path, None)
            window._on_file_loaded(window.vm.state.column_names())
            window.axis_panel.apply_selection(window.vm.state.column_names(), "Time", ["A"], [])
            window._on_generate_plot()

            original = qt_file_dialogs.save_image_file
            qt_file_dialogs.save_image_file = lambda parent, initial_dir="": out_path
            try:
                window._save_plot_png()
            finally:
                qt_file_dialogs.save_image_file = original
            self.assertTrue(os.path.exists(out_path))

    def test_figure_options_appearance_persists_across_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = os.path.join(directory, "data.csv")
            pd.DataFrame({"Time": [0.0, 1.0, 2.0, 3.0], "A": [1.0, 2.0, 3.0, 4.0]}).to_csv(data_path, index=False)
            session_path = os.path.join(directory, "session.json")

            source = self._make_window(directory)
            source.vm.data_loading.load_file(data_path, None)
            source._on_file_loaded(source.vm.state.column_names())
            source.axis_panel.apply_selection(source.vm.state.column_names(), "Time", ["A"], [])
            source._on_generate_plot()
            # Simulate the user editing title/labels/limits via Figure Options.
            ax = source.plot_workspace.canvas.axes
            ax.set_title("Custom Title")
            ax.set_xlabel("Custom X")
            ax.set_ylabel("Custom Y")
            ax.set_xlim(0.5, 2.5)
            ax.set_ylim(-1.0, 9.0)
            self._save_session(source, session_path)

            target = self._make_window(directory)
            self._load_session(target, session_path)
            tax = target.plot_workspace.canvas.axes
            self.assertTrue(target._plot_generated)
            self.assertEqual(tax.get_title(), "Custom Title")
            self.assertEqual(tax.get_xlabel(), "Custom X")
            self.assertEqual(tax.get_ylabel(), "Custom Y")
            self.assertAlmostEqual(tax.get_xlim()[0], 0.5, places=2)
            self.assertAlmostEqual(tax.get_xlim()[1], 2.5, places=2)
            self.assertAlmostEqual(tax.get_ylim()[0], -1.0, places=2)
            self.assertAlmostEqual(tax.get_ylim()[1], 9.0, places=2)


class LastDataDirectoryHelperTests(unittest.TestCase):
    """The last-data-directory helpers are pure Python and need no PySide6."""

    def test_remember_then_read_round_trip(self) -> None:
        from pathlib import Path

        from test_data_analyser.core.settings_manager import SettingsManager as Manager
        from test_data_analyser.qt_app.adapters import qt_widget_helpers

        with tempfile.TemporaryDirectory() as directory:
            manager = Manager(os.path.join(directory, "settings.json"))
            data_file = os.path.join(directory, "run.csv")
            with open(data_file, "w", encoding="utf-8") as handle:
                handle.write("Time,A\n0,1\n")
            qt_widget_helpers.remember_data_directory(manager, data_file)
            self.assertEqual(
                qt_widget_helpers.last_data_directory(manager),
                str(Path(data_file).resolve().parent),
            )

    def test_missing_directory_falls_back_to_blank(self) -> None:
        from test_data_analyser.core.settings_manager import SettingsManager as Manager
        from test_data_analyser.qt_app.adapters import qt_widget_helpers

        with tempfile.TemporaryDirectory() as directory:
            manager = Manager(os.path.join(directory, "settings.json"))
            manager.set("data_import", "last_data_directory", os.path.join(directory, "does_not_exist"))
            self.assertEqual(qt_widget_helpers.last_data_directory(manager), "")

    def test_none_manager_is_safe(self) -> None:
        from test_data_analyser.qt_app.adapters import qt_widget_helpers

        self.assertEqual(qt_widget_helpers.last_data_directory(None), "")
        qt_widget_helpers.remember_data_directory(None, "C:/whatever/file.csv")  # no raise

    def test_session_directory_round_trip(self) -> None:
        from pathlib import Path

        from test_data_analyser.core.settings_manager import SettingsManager as Manager
        from test_data_analyser.qt_app.adapters import qt_widget_helpers

        with tempfile.TemporaryDirectory() as directory:
            manager = Manager(os.path.join(directory, "settings.json"))
            session_file = os.path.join(directory, "analysis.json")
            qt_widget_helpers.remember_session_directory(manager, session_file)
            self.assertEqual(
                qt_widget_helpers.last_session_directory(manager),
                str(Path(session_file).resolve().parent),
            )

    def test_missing_session_directory_falls_back_to_blank(self) -> None:
        from test_data_analyser.core.settings_manager import SettingsManager as Manager
        from test_data_analyser.qt_app.adapters import qt_widget_helpers

        with tempfile.TemporaryDirectory() as directory:
            manager = Manager(os.path.join(directory, "settings.json"))
            manager.set("general_ui", "last_session_directory", os.path.join(directory, "does_not_exist"))
            self.assertEqual(qt_widget_helpers.last_session_directory(manager), "")

    def test_save_session_initial_directory_prefers_data_file(self) -> None:
        from pathlib import Path

        from test_data_analyser.core.settings_manager import SettingsManager as Manager
        from test_data_analyser.qt_app.adapters import qt_widget_helpers

        with tempfile.TemporaryDirectory() as directory:
            session_dir = os.path.join(directory, "sessions")
            data_dir = os.path.join(directory, "data")
            os.mkdir(session_dir)
            os.mkdir(data_dir)
            data_file = os.path.join(data_dir, "source.csv")
            with open(data_file, "w", encoding="utf-8") as handle:
                handle.write("Time,A\n0,1\n")
            manager = Manager(os.path.join(directory, "settings.json"))
            manager.set("general_ui", "last_session_directory", session_dir)

            self.assertEqual(
                qt_widget_helpers.save_session_initial_directory(manager, data_file),
                str(Path(data_file).resolve().parent),
            )

    def test_save_session_initial_directory_falls_back_to_session_folder(self) -> None:
        from test_data_analyser.core.settings_manager import SettingsManager as Manager
        from test_data_analyser.qt_app.adapters import qt_widget_helpers

        with tempfile.TemporaryDirectory() as directory:
            session_dir = os.path.join(directory, "sessions")
            os.mkdir(session_dir)
            manager = Manager(os.path.join(directory, "settings.json"))
            manager.set("general_ui", "last_session_directory", session_dir)

            self.assertEqual(qt_widget_helpers.save_session_initial_directory(manager, None), session_dir)


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
