"""Tests for the Qt ``PandasTableModel`` adapter and the settings options helper.

These tests construct a Qt model and therefore need a ``QApplication``. They run
headless under the offscreen platform and are skipped entirely if PySide6 is not
installed, so the rest of the suite stays GUI-free.

Run with:

    python -m unittest discover -s tests
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import QItemSelectionModel, Qt
    from PySide6.QtWidgets import (
        QApplication,
        QCheckBox,
        QDialog,
        QFrame,
        QGroupBox,
        QHeaderView,
        QLabel,
        QMenu,
        QPushButton,
        QScrollArea,
        QSizePolicy,
        QSplitter,
        QSpinBox,
        QStackedWidget,
        QTabBar,
        QTabWidget,
    )
    from PySide6.QtTest import QTest

    from test_data_analyser.core.config import __version__, EATON_HEADER_BLUE, EATON_PLOT_COLORS
    from test_data_analyser.core.settings_manager import SettingsManager
    from test_data_analyser.qt_app import theme
    from test_data_analyser.qt_app.adapters import matplotlib_qt_adapter, qt_file_dialogs, qt_message_service
    from test_data_analyser.qt_app.adapters.editable_dataset_model import EditableDatasetModel
    from test_data_analyser.qt_app.adapters.editable_raw_data_model import EditableRawDataTableModel
    from test_data_analyser.qt_app.adapters.pandas_table_model import PandasTableModel
    from test_data_analyser.qt_app.main_qt import _app_icon_path
    from test_data_analyser.qt_app.main_window import MainWindow
    from test_data_analyser.qt_app.widgets.help_dialog import HelpDialog
    from test_data_analyser.qt_app.widgets.no_wheel_combo_box import NoWheelComboBox
    from test_data_analyser.qt_app.widgets.raw_data_panel import RawDataPanel
    from test_data_analyser.services import dataset_service, plot_render_service
    from test_data_analyser.viewmodels.app_state import AppState
    from test_data_analyser.viewmodels.cursor_compare_vm import CursorCompareViewModel
    from test_data_analyser.viewmodels.dataset_vm import DatasetViewModel
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
class EditableDatasetModelTests(unittest.TestCase):
    def _model(self):
        df = pd.DataFrame({"Time": [0.0, 1.0], "Pressure": [10.0, 20.0]})
        state = AppState(df=df.copy())
        state.channel_registry = dataset_service.build_registry_for_dataframe(state.df)
        vm = DatasetViewModel(state)
        model = EditableDatasetModel(vm)
        model.refresh()
        return model, state

    def test_inline_add_row_and_column_are_exposed(self) -> None:
        model, state = self._model()
        add_row = len(state.df)
        add_column = len(state.df.columns)

        self.assertEqual(model.rowCount(), add_row + 1)
        self.assertEqual(model.columnCount(), add_column + 1)
        self.assertEqual(model.headerData(add_column, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole), "+")
        self.assertEqual(model.headerData(add_row, Qt.Orientation.Vertical, Qt.ItemDataRole.DisplayRole), "+")
        self.assertIsNone(model.data(model.index(add_row, 0), Qt.ItemDataRole.DisplayRole))
        self.assertIsNone(model.data(model.index(0, add_column), Qt.ItemDataRole.DisplayRole))

    def test_inline_add_controls_are_not_editable_cells(self) -> None:
        model, state = self._model()
        add_row = len(state.df)
        add_column = len(state.df.columns)

        self.assertTrue(model.flags(model.index(0, 0)) & Qt.ItemFlag.ItemIsEditable)
        self.assertFalse(model.flags(model.index(add_row, 0)) & Qt.ItemFlag.ItemIsEditable)
        self.assertFalse(model.flags(model.index(0, add_column)) & Qt.ItemFlag.ItemIsEditable)
        self.assertFalse(model.flags(model.index(add_row, 0)) & Qt.ItemFlag.ItemIsSelectable)
        self.assertFalse(model.flags(model.index(0, add_column)) & Qt.ItemFlag.ItemIsSelectable)
        self.assertFalse(model.setData(model.index(add_row, 0), "99", Qt.ItemDataRole.EditRole))

    def test_raw_data_panel_expands_columns_to_fit_headers(self) -> None:
        long_title = "Pressure Sensor With Long Engineering Header"
        df = pd.DataFrame({"Time": [0.0, 1.0], long_title: [10.0, 20.0]})
        state = AppState(df=df.copy())
        state.channel_registry = dataset_service.build_registry_for_dataframe(state.df)
        panel = RawDataPanel(RawDataViewModel(state), DatasetViewModel(state))

        panel.enter_edit_mode()
        title_column = 1
        expected_minimum = panel.table.horizontalHeader().fontMetrics().horizontalAdvance(long_title) + 34

        self.assertGreaterEqual(panel.table.columnWidth(title_column), expected_minimum)
        self.assertEqual(panel.table.columnWidth(panel.dataset_model.data_column_count()), 36)

    def test_raw_data_panel_collects_multiple_selected_columns(self) -> None:
        df = pd.DataFrame(
            {"Time": [0.0, 1.0], "Pressure": [10.0, 20.0], "Flow": [1.0, 2.0]}
        )
        state = AppState(df=df.copy())
        state.channel_registry = dataset_service.build_registry_for_dataframe(state.df)
        panel = RawDataPanel(RawDataViewModel(state), DatasetViewModel(state))
        panel.enter_edit_mode()

        selection_model = panel.table.selectionModel()
        selection_model.select(
            panel.dataset_model.index(0, 1),
            QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Columns,
        )
        selection_model.select(
            panel.dataset_model.index(0, 2),
            QItemSelectionModel.SelectionFlag.Select | QItemSelectionModel.SelectionFlag.Columns,
        )

        selected_names = [state.name_for_channel_id(channel_id) for channel_id in panel._selected_column_ids(2)]
        self.assertEqual(selected_names, ["Pressure", "Flow"])


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class RawDataSortFilterPanelTests(unittest.TestCase):
    def _panel(self, df: pd.DataFrame) -> "RawDataPanel":
        state = AppState(df=df.copy())
        state.channel_registry = dataset_service.build_registry_for_dataframe(state.df)
        panel = RawDataPanel(RawDataViewModel(state), DatasetViewModel(state))
        panel.set_selection_provider(lambda: ("Time", ["A"], None, None))
        panel.refresh()
        return panel

    def test_clicking_column_header_cycles_sort(self) -> None:
        panel = self._panel(pd.DataFrame({"Time": [0.0, 1.0, 2.0], "A": [30.0, 10.0, 20.0]}))
        header = panel.table.horizontalHeader()
        section = panel._section_for_column("A")
        self.assertIsNotNone(section)
        assert section is not None

        panel._on_horizontal_header_clicked(section)
        self.assertEqual(panel._sort_state, ("A", True))
        self.assertTrue(header.isSortIndicatorShown())
        self.assertEqual(header.sortIndicatorOrder(), Qt.SortOrder.AscendingOrder)

        panel._on_horizontal_header_clicked(section)
        self.assertEqual(panel._sort_state, ("A", False))
        self.assertEqual(header.sortIndicatorOrder(), Qt.SortOrder.DescendingOrder)

        panel._on_horizontal_header_clicked(section)
        self.assertIsNone(panel._sort_state)
        self.assertFalse(header.isSortIndicatorShown())

    def test_sorting_disabled_in_edit_mode(self) -> None:
        panel = self._panel(pd.DataFrame({"Time": [0.0, 1.0], "A": [2.0, 1.0]}))
        panel.enter_edit_mode()
        panel._on_horizontal_header_clicked(0)
        self.assertIsNone(panel._sort_state)

    def test_filter_row_visible_only_when_enabled(self) -> None:
        panel = self._panel(pd.DataFrame({"Time": [0.0, 1.0], "A": [1.0, 2.0]}))
        self.assertTrue(panel.filter_row.isHidden())

        panel.filter_check.setChecked(True)
        self.assertFalse(panel.filter_row.isHidden())

        panel.filter_check.setChecked(False)
        self.assertTrue(panel.filter_row.isHidden())

    def test_filter_row_updates_table_rows(self) -> None:
        panel = self._panel(pd.DataFrame({"Time": [0.0, 1.0, 2.0, 3.0], "A": [1.0, 5.0, 10.0, 50.0]}))
        full_rows = panel.model.rowCount()

        panel.filter_check.setChecked(True)
        panel._filter_edits["A"].setText(">5")

        self.assertEqual(full_rows, 4)
        self.assertEqual(panel.model.rowCount(), 2)

        panel._clear_filters()
        self.assertEqual(panel.model.rowCount(), 4)


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class RawDataClipboardTests(unittest.TestCase):
    def _edit_panel(self, df: pd.DataFrame):
        state = AppState(df=df.copy())
        state.channel_registry = dataset_service.build_registry_for_dataframe(state.df)
        panel = RawDataPanel(RawDataViewModel(state), DatasetViewModel(state))
        panel.enter_edit_mode()
        return panel, state

    def _select(self, panel, model, cells) -> None:
        selection = panel.table.selectionModel()
        selection.clearSelection()
        for row, col in cells:
            selection.select(model.index(row, col), QItemSelectionModel.SelectionFlag.Select)

    def test_copy_selection_writes_tsv_to_clipboard(self) -> None:
        panel, _state = self._edit_panel(pd.DataFrame({"A": [1.0, 2.0], "B": [3.0, 4.0]}))
        self._select(panel, panel.dataset_model, [(0, 0), (0, 1), (1, 0), (1, 1)])

        QApplication.clipboard().setText("")
        panel._on_copy()

        self.assertEqual(QApplication.clipboard().text(), "1.0\t3.0\n2.0\t4.0")

    def test_cut_selection_clears_and_pushes_undo(self) -> None:
        panel, state = self._edit_panel(pd.DataFrame({"A": [1.0, 2.0], "B": [3.0, 4.0]}))
        self._select(panel, panel.dataset_model, [(0, 0)])

        panel._on_cut()

        self.assertEqual(QApplication.clipboard().text(), "1.0")
        self.assertTrue(pd.isna(state.df.at[0, "A"]))
        self.assertTrue(panel.dataset_vm.can_undo)

    def test_paste_at_anchor_expands_table(self) -> None:
        panel, state = self._edit_panel(pd.DataFrame({"A": [1.0], "B": [2.0]}))
        QApplication.clipboard().setText("5\t6\n7\t8")
        panel.table.setCurrentIndex(panel.dataset_model.index(0, 0))

        panel._on_paste()

        self.assertEqual(len(state.df), 2)
        self.assertEqual(state.df.at[0, "A"], 5.0)
        self.assertEqual(state.df.at[0, "B"], 6.0)
        self.assertEqual(state.df.at[1, "A"], 7.0)
        self.assertEqual(state.df.at[1, "B"], 8.0)

    def test_copy_works_in_view_mode_but_paste_does_not(self) -> None:
        state = AppState(df=pd.DataFrame({"Time": [0.0, 1.0], "A": [10.0, 20.0]}))
        state.channel_registry = dataset_service.build_registry_for_dataframe(state.df)
        panel = RawDataPanel(RawDataViewModel(state), DatasetViewModel(state))
        panel.set_selection_provider(lambda: ("Time", ["A"], None, None))
        panel.refresh()

        self._select(panel, panel.model, [(0, 0)])
        QApplication.clipboard().setText("")
        panel._on_copy()
        self.assertEqual(QApplication.clipboard().text(), "0.0")

        QApplication.clipboard().setText("99")
        panel.table.setCurrentIndex(panel.model.index(0, 0))
        panel._on_paste()
        self.assertEqual(state.df.at[0, "Time"], 0.0)


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class FindReplaceDialogTests(unittest.TestCase):
    def _panel(self, df: pd.DataFrame):
        state = AppState(df=df.copy())
        state.channel_registry = dataset_service.build_registry_for_dataframe(state.df)
        panel = RawDataPanel(RawDataViewModel(state), DatasetViewModel(state))
        panel.set_selection_provider(lambda: ("Time", ["A"], None, None))
        panel.refresh()
        return panel, state

    def test_dialog_opens_in_find_only_for_ctrl_f(self) -> None:
        panel, _state = self._panel(pd.DataFrame({"Time": [0.0], "A": [1.0]}))
        panel._open_find_replace(False)
        dialog = panel._find_replace_dialog
        self.assertIsNotNone(dialog)
        self.assertFalse(dialog.replacement_edit.isEnabled())
        self.assertFalse(dialog.replace_all_button.isEnabled())
        dialog.close()

    def test_dialog_opens_with_replace_for_ctrl_h(self) -> None:
        panel, _state = self._panel(pd.DataFrame({"Time": [0.0], "A": [1.0]}))
        panel._open_find_replace(True)
        dialog = panel._find_replace_dialog
        self.assertTrue(dialog.replacement_edit.isEnabled())
        self.assertTrue(dialog.replace_all_button.isEnabled())
        dialog.close()

    def test_find_next_navigates_matches(self) -> None:
        panel, _state = self._panel(pd.DataFrame({"Time": [0.0, 1.0, 2.0], "A": [5.0, 5.0, 9.0]}))
        panel._open_find_replace(False)
        dialog = panel._find_replace_dialog
        dialog.query_edit.setText("5.0")

        dialog._on_find_next()
        self.assertIn("Match 1 of", dialog.status_label.text())
        dialog._on_find_next()
        self.assertIn("Match 2 of", dialog.status_label.text())
        dialog.close()

    def test_replace_all_shows_summary(self) -> None:
        panel, state = self._panel(pd.DataFrame({"Time": [0.0, 1.0], "A": [5.0, 5.0]}))
        panel._open_find_replace(True)
        dialog = panel._find_replace_dialog
        dialog.query_edit.setText("5.0")
        dialog.replacement_edit.setText("8.0")

        dialog._on_replace_all()

        self.assertIn("Replaced 2", dialog.status_label.text())
        self.assertEqual(state.df.at[0, "A"], 8.0)
        self.assertEqual(state.df.at[1, "A"], 8.0)
        dialog.close()


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class FillHandleTests(unittest.TestCase):
    def _edit_panel(self, df: pd.DataFrame):
        state = AppState(df=df.copy())
        state.channel_registry = dataset_service.build_registry_for_dataframe(state.df)
        panel = RawDataPanel(RawDataViewModel(state), DatasetViewModel(state))
        panel.enter_edit_mode()
        return panel, state

    def test_fill_handle_visible_in_edit_mode(self) -> None:
        panel, _state = self._edit_panel(pd.DataFrame({"A": [1.0, 2.0]}))
        panel.table.selectionModel().clearSelection()
        self.assertFalse(panel.fill_handle_visible())

        panel.table.selectionModel().select(
            panel.dataset_model.index(0, 0), QItemSelectionModel.SelectionFlag.Select
        )
        self.assertTrue(panel.fill_handle_visible())

    def test_fill_handle_hidden_in_view_mode(self) -> None:
        state = AppState(df=pd.DataFrame({"Time": [0.0, 1.0], "A": [1.0, 2.0]}))
        state.channel_registry = dataset_service.build_registry_for_dataframe(state.df)
        panel = RawDataPanel(RawDataViewModel(state), DatasetViewModel(state))
        panel.set_selection_provider(lambda: ("Time", ["A"], None, None))
        panel.refresh()
        panel.table.selectionModel().select(
            panel.model.index(0, 0), QItemSelectionModel.SelectionFlag.Select
        )
        self.assertFalse(panel.fill_handle_visible())

    def test_context_menu_fill_down_invokes_viewmodel(self) -> None:
        panel, state = self._edit_panel(pd.DataFrame({"A": [5.0, 0.0, 0.0]}))
        calls: list = []
        original = panel.dataset_vm.fill_down
        panel.dataset_vm.fill_down = lambda rows, ids: calls.append((list(rows), list(ids))) or original(rows, ids)

        panel._fill_down([0, 1, 2], [state.channel_registry.ids()[0]])

        self.assertEqual(len(calls), 1)
        self.assertEqual(list(state.df["A"]), [5.0, 5.0, 5.0])


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class BatchImportDialogTests(unittest.TestCase):
    def _dialog(self, **kwargs):
        from test_data_analyser.qt_app.widgets.batch_import_dialog import BatchImportDialog

        return BatchImportDialog(**kwargs)

    def test_settings_round_trip(self) -> None:
        dialog = self._dialog(initial_dir="C:/data")
        dialog.folder_edit.setText("C:/runs")
        dialog.glob_edit.setText("*.csv")
        dialog.regex_edit.setText(r"SN(\d+)")
        dialog.recursive_check.setChecked(True)
        dialog.sheet_edit.setText("Sheet1")

        settings = dialog.settings()
        self.assertEqual(settings["folder"], "C:/runs")
        self.assertEqual(settings["glob"], "*.csv")
        self.assertEqual(settings["name_regex"], r"SN(\d+)")
        self.assertTrue(settings["recursive"])
        self.assertEqual(settings["sheet_name"], "Sheet1")
        dialog.close()

    def test_blank_optional_fields_become_none_and_glob_defaults(self) -> None:
        dialog = self._dialog()
        dialog.folder_edit.setText("C:/runs")

        settings = dialog.settings()
        self.assertIsNone(settings["name_regex"])
        self.assertIsNone(settings["sheet_name"])
        self.assertEqual(settings["glob"], "*.csv;*.xlsx")
        self.assertFalse(settings["recursive"])
        dialog.close()


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

    def test_formula_builder_buttons_insert_backend_syntax(self) -> None:
        expected = {
            "+": " + ",
            "−": " - ",
            "×": " * ",
            "÷": " / ",
            "√x": "sqrt()",
            "x²": "**2",
            "x^n": "**",
            "1/x": "1 / ()",
            "( )": "()",
        }
        for label, syntax in expected.items():
            with self.subTest(label=label):
                self.panel.formula_edit.clear()
                self.panel.formula_buttons[label].click()
                self.assertEqual(self.panel.formula_edit.toPlainText(), syntax)

    def test_formula_builder_inserts_channel_inside_function_parentheses(self) -> None:
        self.panel.formula_buttons["√x"].click()
        self.panel.column_combo.setCurrentText("A")
        self.panel._insert_column()
        self.assertEqual(self.panel.formula_edit.toPlainText(), "sqrt(`A`)")

    def test_formula_builder_addition_creates_channel(self) -> None:
        self.panel.name_edit.setText("Built Sum")
        self.panel.column_combo.setCurrentText("A")
        self.panel._insert_column()
        self.panel.formula_buttons["+"].click()
        self.panel.column_combo.setCurrentText("B")
        self.panel._insert_column()

        self.panel._apply()

        self.assertIn("Built Sum", self.state.calculated_channels)
        self.assertEqual(list(self.state.df["Built Sum"]), [11.0, 22.0, 33.0])

    def test_formula_builder_reciprocal_creates_channel(self) -> None:
        self.panel.name_edit.setText("Inverse B")
        self.panel.formula_buttons["1/x"].click()
        self.panel.column_combo.setCurrentText("B")
        self.panel._insert_column()

        self.panel._apply()

        self.assertIn("Inverse B", self.state.calculated_channels)
        self.assertAlmostEqual(float(self.state.df["Inverse B"].iloc[0]), 1.0)
        self.assertAlmostEqual(float(self.state.df["Inverse B"].iloc[1]), 0.5)
        self.assertAlmostEqual(float(self.state.df["Inverse B"].iloc[2]), 1.0 / 3.0)

    def test_formula_builder_invalid_formula_updates_status(self) -> None:
        self.panel.formula_edit.setPlainText("A /")
        self.panel._validate()
        self.assertIn("Invalid formula", self.panel.validation_status_label.text())

    def test_insert_column_with_backtick_uses_quoted_reference(self) -> None:
        self.state.df = pd.DataFrame({"A`B": [1.0, 2.0]})
        self.panel.refresh()
        self.panel.column_combo.setCurrentText("A`B")
        self.panel._insert_column()
        self.assertEqual(self.panel.formula_edit.toPlainText(), "'A`B'")

    def test_existing_column_combo_is_grouped_and_naturally_sorted(self) -> None:
        self.state.df = pd.DataFrame(
            {
                "TC10": [1.0],
                "Outlet Pressure": [2.0],
                "Power": [3.0],
                "Time": [0.0],
                "TC2": [4.0],
            }
        )
        self.state.calculated_channels["Power"] = {
            "name": "Power",
            "formula": "TC2 + TC10",
            "description": "",
            "enabled": True,
            "created_from_columns": ["TC2", "TC10"],
        }

        self.panel.refresh()

        items = [self.panel.column_combo.itemText(index) for index in range(self.panel.column_combo.count())]
        self.assertEqual(items, ["Time", "TC2", "TC10", "Outlet Pressure", "Power"])

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
        status_index = self.panel.summary_model.index(0, 2)
        self.assertEqual(self.panel.summary_model.data(status_index, Qt.ItemDataRole.DisplayRole), "PASS")
        self.assertIsNotNone(self.panel.summary_table.itemDelegateForColumn(2))

    def test_refresh_margins_colours_near_pass_status_amber(self) -> None:
        self.panel._add_line()
        self.panel.vm.update_active_metadata(
            name="Max", limit_type="Upper Limit", applies_to="All selected Y channels", colour="#005A8C"
        )
        self.panel.vm.add_point("0", "3.1")
        self.panel.vm.add_point("2", "3.1")
        self.panel.refresh_margins()
        status_index = self.panel.summary_model.index(0, 2)
        brush = self.panel.summary_model.data(status_index, Qt.ItemDataRole.BackgroundRole)

        self.assertEqual(self.panel.summary_model.data(status_index, Qt.ItemDataRole.DisplayRole), "PASS")
        self.assertEqual(self.panel.summary_model.data(status_index, Qt.ItemDataRole.UserRole), "WARN")
        self.assertEqual(brush.color().name().upper(), "#F9C74F")

    def test_dense_content_is_scroll_wrapped(self) -> None:
        self.assertIsInstance(self.panel.content_scroll, QScrollArea)
        self.assertFalse(self.panel.content_splitter.childrenCollapsible())
        self.assertGreaterEqual(self.panel.content_splitter.minimumHeight(), 380)

    def test_limit_points_table_expands_vertically(self) -> None:
        self.assertEqual(self.panel.points_group.sizePolicy().verticalPolicy(), QSizePolicy.Policy.Expanding)
        self.assertEqual(self.panel.points_table.sizePolicy().verticalPolicy(), QSizePolicy.Policy.Expanding)

    def test_margin_summary_is_separate_panel(self) -> None:
        self.assertIsNot(self.panel.summary_panel.parentWidget(), self.panel)
        self.assertEqual(self.panel.summary_table.parentWidget(), self.panel.summary_panel)

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

    def test_x_axis_combo_is_alphabetical(self) -> None:
        self.panel.set_columns(["Time", "Zeta", "alpha", "Beta", "A10", "A2"], "Time")

        items = [self.panel.x_combo.itemText(index) for index in range(self.panel.x_combo.count())]

        self.assertEqual(items, ["A2", "A10", "alpha", "Beta", "Time", "Zeta"])

    def test_selected_y_accessors_return_display_order(self) -> None:
        self.panel.set_columns(["Time", "TC10", "Outlet Pressure", "TC2"], "Time")
        for row in range(self.panel.y_list.count()):
            item = self.panel.y_list.item(row)
            if item.flags() & Qt.ItemFlag.ItemIsUserCheckable:
                item.setCheckState(Qt.CheckState.Checked)

        self.assertEqual(self.panel.selected_y(), ["TC2", "TC10", "Outlet Pressure"])

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
            self.panel.xmin_edit,
            self.panel.xmax_edit,
            self.panel.cutoff_edit,
            self.panel.order_edit,
        ]:
            self.assertEqual(widget.minimumWidth(), 0)
            self.assertEqual(widget.sizePolicy().horizontalPolicy(), QSizePolicy.Policy.Expanding)
        for combo in [self.panel.x_combo, self.panel.group_combo, self.panel.plot_kind_combo]:
            self.assertEqual(combo.minimumWidth(), 0)
            self.assertEqual(combo.sizePolicy().horizontalPolicy(), QSizePolicy.Policy.Ignored)

    def test_long_channel_names_do_not_force_wide_controls(self) -> None:
        self.panel.resize(260, 700)
        self.panel.set_columns(
            [
                "Time (mins)",
                "TC25 Structural Interface Temperature 240 Deg (C)",
                "TC27 Composite Spar Temperature 120 Deg (C)",
                "Max Spar Temperature Requirement (C)",
            ],
            "Time (mins)",
        )
        self.panel.show()
        QApplication.processEvents()

        available_width = self.panel.width() - 48
        self.assertLessEqual(self.panel.x_combo.width(), available_width)
        self.assertLessEqual(self.panel.y_list.width(), available_width)
        self.assertEqual(self.panel.y_list.textElideMode(), Qt.TextElideMode.ElideRight)
        self.assertEqual(self.panel.y_list.horizontalScrollBarPolicy(), Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

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

    def test_maths_channels_use_dedicated_group(self) -> None:
        self.panel.set_columns(
            ["Time", "Outlet Pressure", "Pressure Drop", "Power"],
            "Time",
            maths_channel_names=["Pressure Drop", "Power"],
        )
        self.assertGreaterEqual(self.panel.group_combo.findText("Maths Channel"), 0)

        self.panel.group_combo.setCurrentText("Pressure")
        self.assertEqual(self._checkable_texts(self.panel.y_list), ["Outlet Pressure"])

        self.panel.group_combo.setCurrentText("Maths Channel")
        self.assertEqual(self._checkable_texts(self.panel.y_list), ["Power", "Pressure Drop"])

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

    def test_mark_peaks_adds_annotations(self) -> None:
        import test_data_analyser.qt_app.widgets.plot_workspace as plot_workspace_module

        self.state.plot_profiles = [{"name": "P1", "x_column": "Time", "y_columns": ["A"]}]
        self.state.active_plot_profile_index = 0
        self.state.current_x_axis = "Time"

        class _FakeInput:
            @staticmethod
            def getDouble(*args, **kwargs):
                return (0.0, True)

            @staticmethod
            def getItem(*args, **kwargs):
                return ("A", True)

        class _FakeMsg:
            @staticmethod
            def confirm(*args, **kwargs):
                return False

            @staticmethod
            def warning(*args, **kwargs):
                return None

            @staticmethod
            def info(*args, **kwargs):
                return None

        original_input = plot_workspace_module.QInputDialog
        original_msg = plot_workspace_module.qt_message_service
        plot_workspace_module.QInputDialog = _FakeInput
        plot_workspace_module.qt_message_service = _FakeMsg
        try:
            self.panel.mark_peaks()
        finally:
            plot_workspace_module.QInputDialog = original_input
            plot_workspace_module.qt_message_service = original_msg

        self.assertTrue(self.panel.current_annotations())
        self.assertEqual(self.panel.current_annotations()[0]["type"], "text")

    def test_annotation_controls_live_on_plot_toolbar(self) -> None:
        self.assertIsNone(self.panel.findChild(QFrame, "AnnotationToolbar"))
        self.assertIs(self.panel.layout().itemAt(0).widget(), self.panel.plot_legend_splitter)
        for button in self.panel._annotation_buttons.values():
            self.assertIs(button.parentWidget(), self.panel.canvas.toolbar)
        self.assertIs(self.panel.delete_annotation_button.parentWidget(), self.panel.canvas.toolbar)

    def test_secondary_axis_creates_twin(self) -> None:
        result = self.panel.generate_plot("Time", ["A", "B"], secondary_y=["B"])
        self.assertTrue(result.ok)
        self.assertEqual(len(self.panel.canvas.figure.axes), 2)

    def test_single_plot_uses_default_colour_cycle_without_repeated_map(self) -> None:
        result = self.panel.generate_plot("Time", ["A", "B"])
        self.assertTrue(result.ok, result.message)
        colours = [str(line.get_color()).lower() for line in self.panel.canvas.axes.get_lines()]
        self.assertEqual(colours, [EATON_PLOT_COLORS[0].lower(), EATON_PLOT_COLORS[1].lower()])

    def test_repeated_channel_colour_reserves_colour_for_partial_repeats(self) -> None:
        channel_colours = {plot_render_service.normalise_channel_name("A"): EATON_PLOT_COLORS[0]}
        result = self.panel.generate_plot("Time", ["B", "A"], channel_colours=channel_colours)
        self.assertTrue(result.ok, result.message)

        colours = [str(line.get_color()).lower() for line in self.panel.canvas.axes.get_lines()]
        self.assertEqual(colours[1], EATON_PLOT_COLORS[0].lower())
        self.assertNotEqual(colours[0], EATON_PLOT_COLORS[0].lower())
        self.assertEqual(len(set(colours)), 2)

    def test_repeated_secondary_channel_colour_matches_legend_handle(self) -> None:
        channel_colours = {plot_render_service.normalise_channel_name("B"): EATON_PLOT_COLORS[3]}
        result = self.panel.generate_plot("Time", ["A", "B"], secondary_y=["B"], channel_colours=channel_colours)
        self.assertTrue(result.ok, result.message)

        secondary_axes = self.panel.canvas.figure.axes[1]
        secondary_colour = str(secondary_axes.get_lines()[0].get_color()).lower()
        self.assertEqual(secondary_colour, EATON_PLOT_COLORS[3].lower())
        handles, labels = self.panel._legend_handles_and_labels(self.panel.canvas.axes, secondary_axes)
        handle_by_label = dict(zip(labels, handles))
        self.assertEqual(str(handle_by_label["B [Right Y]"].get_color()).lower(), secondary_colour)

    def test_best_fit_line_renders_with_formula_label(self) -> None:
        self.panel.set_best_fit_settings(
            [{"channel": "A", "fit_type": "Polynomial", "order": 3}]
        )
        result = self.panel.generate_plot("Time", ["A"])

        self.assertTrue(result.ok, result.message)
        best_fit_lines = [line for line in self.panel.canvas.axes.get_lines() if bool(getattr(line, "_tda_best_fit", False))]
        self.assertEqual(len(best_fit_lines), 1)
        self.assertEqual(best_fit_lines[0].get_linestyle(), "--")
        self.assertEqual(best_fit_lines[0].get_label(), "A polynomial fit")
        self.assertEqual(len(self.panel.best_fit_formula_rows()), 1)
        self.assertIn("y =", self.panel.best_fit_formula_rows()[0]["Formula"])
        self.assertEqual(self.panel.best_fit_settings()[0]["order"], 3)

    def test_scatter_plot_kind(self) -> None:
        result = self.panel.generate_plot("Time", ["A"], plot_kind="Scatter")
        self.assertTrue(result.ok)
        self.assertTrue(self.panel.canvas.axes.collections)

    def test_channel_style_override_changes_label_colour_and_plot_kind(self) -> None:
        from matplotlib.colors import to_hex

        result = self.panel.generate_plot(
            "Time",
            ["A", "B"],
            plot_kind="Line",
            channel_styles={"A": {"channel": "A", "label": "Pump Pressure", "colour": "#123456", "plot_kind": "Scatter"}},
        )

        self.assertTrue(result.ok, result.message)
        collections = {collection.get_label(): collection for collection in self.panel.canvas.axes.collections}
        self.assertIn("Pump Pressure", collections)
        self.assertEqual(to_hex(collections["Pump Pressure"].get_facecolors()[0]).lower(), "#123456")
        self.assertEqual([line.get_label() for line in self.panel.canvas.axes.get_lines()], ["B"])
        table_labels = [self.panel.legend_table.item(row, 1).text() for row in range(self.panel.legend_table.rowCount())]
        self.assertIn("Pump Pressure", table_labels)

    def test_channel_style_override_applies_curve_options(self) -> None:
        from matplotlib.colors import to_hex

        result = self.panel.generate_plot(
            "Time",
            ["A"],
            plot_kind="Line",
            channel_styles={
                "A": {
                    "channel": "A",
                    "label": "Styled A",
                    "colour": "#123456",
                    "plot_kind": "Line + Markers",
                    "line_style": "--",
                    "draw_style": "steps-post",
                    "line_width": "4",
                    "marker_style": "s",
                    "marker_size": "8",
                    "marker_face_colour": "#ABCDEF",
                    "marker_edge_colour": "#654321",
                }
            },
        )

        self.assertTrue(result.ok, result.message)
        line = self.panel.canvas.axes.get_lines()[0]
        self.assertEqual(line.get_label(), "Styled A")
        self.assertEqual(line.get_linestyle(), "--")
        self.assertEqual(line.get_drawstyle(), "steps-post")
        self.assertEqual(line.get_linewidth(), 4.0)
        self.assertEqual(line.get_marker(), "s")
        self.assertEqual(line.get_markersize(), 8.0)
        self.assertEqual(to_hex(line.get_color()).lower(), "#123456")
        self.assertEqual(to_hex(line.get_markerfacecolor()).lower(), "#abcdef")
        self.assertEqual(to_hex(line.get_markeredgecolor()).lower(), "#654321")

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

    def test_major_tick_steps_are_applied_to_x_primary_y_and_secondary_y(self) -> None:
        result = self.panel.generate_plot(
            "Time",
            ["A", "B"],
            secondary_y=["B"],
            axis_limits={"xmin": 0.0, "xmax": 1.0, "ymin": -1.0, "ymax": 1.0, "y2min": -100.0, "y2max": 100.0},
            auto_fit_axes=False,
            axis_tick_settings={"x_major_tick": "0.25", "y_major_tick": "0.5", "y2_major_tick": "50"},
        )
        self.assertTrue(result.ok, result.message)
        secondary_axes = self.panel.canvas.figure.axes[1]

        x_ticks = self._visible_ticks(self.panel.canvas.axes.get_xticks(), self.panel.canvas.axes.get_xlim())
        y_ticks = self._visible_ticks(self.panel.canvas.axes.get_yticks(), self.panel.canvas.axes.get_ylim())
        y2_ticks = self._visible_ticks(secondary_axes.get_yticks(), secondary_axes.get_ylim())
        self.assertEqual(x_ticks, [0.0, 0.25, 0.5, 0.75, 1.0])
        self.assertEqual(y_ticks, [-1.0, -0.5, 0.0, 0.5, 1.0])
        self.assertEqual(y2_ticks, [-100.0, -50.0, 0.0, 50.0, 100.0])

    def test_secondary_y_ticks_align_to_primary_grid_without_sharing_values(self) -> None:
        result = self.panel.generate_plot(
            "Time",
            ["A", "B"],
            secondary_y=["B"],
            axis_limits={"ymin": -1.0, "ymax": 1.0, "y2min": 0.0, "y2max": 100.0},
            auto_fit_axes=False,
            axis_tick_settings={
                "y_major_tick": "0.5",
                "y2_major_tick": "40",
                "align_secondary_y_axis_grid": True,
            },
        )
        self.assertTrue(result.ok, result.message)
        secondary_axes = self.panel.canvas.figure.axes[1]

        primary_ticks = self._visible_ticks(self.panel.canvas.axes.get_yticks(), self.panel.canvas.axes.get_ylim())
        secondary_ticks = self._visible_ticks(secondary_axes.get_yticks(), secondary_axes.get_ylim())
        self.assertEqual(primary_ticks, [-1.0, -0.5, 0.0, 0.5, 1.0])
        self.assertEqual(secondary_ticks, [0.0, 25.0, 50.0, 75.0, 100.0])
        self.assertNotEqual(secondary_ticks, primary_ticks)
        self.assertFalse(any(line.get_visible() for line in secondary_axes.get_ygridlines()))

    def test_axis_tick_settings_do_not_require_secondary_axis(self) -> None:
        result = self.panel.generate_plot(
            "Time",
            ["A"],
            axis_tick_settings={"x_major_tick": "0.25", "align_secondary_y_axis_grid": True},
        )
        self.assertTrue(result.ok, result.message)
        self.assertEqual(len(self.panel.canvas.figure.axes), 1)

    @staticmethod
    def _visible_ticks(ticks, limits) -> list[float]:
        lower, upper = min(limits), max(limits)
        return [round(float(tick), 6) for tick in ticks if lower <= float(tick) <= upper]

    def test_legend_panel_includes_secondary_channels_without_canvas_legend(self) -> None:
        result = self.panel.generate_plot("Time", ["A", "B"], secondary_y=["B"])
        self.assertTrue(result.ok, result.message)
        self.assertFalse(self.panel.legend_panel.isHidden())
        self.assertIsNone(self.panel.canvas.axes.get_legend())
        self.assertEqual(self.panel.legend_table.rowCount(), 2)
        table_labels = [self.panel.legend_table.item(row, 1).text() for row in range(self.panel.legend_table.rowCount())]
        self.assertIn("A", table_labels)
        self.assertIn("B [Right Y]", table_labels)
        swatch_cell = self.panel.legend_table.cellWidget(0, 0)
        self.assertIsNotNone(swatch_cell)
        assert swatch_cell is not None
        swatch = swatch_cell.findChild(QFrame, "LegendColourSwatch")
        self.assertIsNotNone(swatch)
        assert swatch is not None
        self.assertIn("background-color:", swatch.styleSheet())
        visibility_cell = self.panel.legend_table.cellWidget(0, 2)
        self.assertIsNotNone(visibility_cell)
        assert visibility_cell is not None
        self.assertIsInstance(visibility_cell.findChild(QCheckBox, "LegendVisibilityCheckBox"), QCheckBox)

    def test_legend_visibility_button_emits_hide_request(self) -> None:
        result = self.panel.generate_plot("Time", ["A"])
        self.assertTrue(result.ok, result.message)
        emitted: list[tuple[str, bool]] = []
        self.panel.legendChannelVisibilityChanged.connect(lambda channel, hidden: emitted.append((channel, hidden)))

        visibility_cell = self.panel.legend_table.cellWidget(0, 2)
        self.assertIsNotNone(visibility_cell)
        assert visibility_cell is not None
        checkbox = visibility_cell.findChild(QCheckBox, "LegendVisibilityCheckBox")
        self.assertIsInstance(checkbox, QCheckBox)
        assert isinstance(checkbox, QCheckBox)
        self.assertTrue(checkbox.isChecked())
        checkbox.setChecked(False)

        self.assertEqual(emitted, [("A", True)])

    def test_hidden_legend_channel_stays_listed_and_not_visible(self) -> None:
        channel_styles = {plot_render_service.normalise_channel_name("A"): {"channel": "A", "hidden": "true"}}
        result = self.panel.generate_plot("Time", ["A", "B"], channel_styles=channel_styles)
        self.assertTrue(result.ok, result.message)

        lines = {line.get_label(): line for line in self.panel.canvas.axes.get_lines()}
        self.assertFalse(lines["A"].get_visible())
        self.assertTrue(lines["B"].get_visible())
        table_labels = [self.panel.legend_table.item(row, 1).text() for row in range(self.panel.legend_table.rowCount())]
        self.assertIn("A", table_labels)
        row = table_labels.index("A")
        visibility_cell = self.panel.legend_table.cellWidget(row, 2)
        self.assertIsNotNone(visibility_cell)
        assert visibility_cell is not None
        checkbox = visibility_cell.findChild(QCheckBox, "LegendVisibilityCheckBox")
        self.assertIsInstance(checkbox, QCheckBox)
        assert isinstance(checkbox, QCheckBox)
        self.assertFalse(checkbox.isChecked())

    def test_clicking_legend_row_emits_channel_style_payload(self) -> None:
        from test_data_analyser.qt_app.widgets import plot_workspace as plot_workspace_module

        result = self.panel.generate_plot("Time", ["A"])
        self.assertTrue(result.ok, result.message)
        emitted: list[tuple[str, dict]] = []
        self.panel.legendChannelStyleChanged.connect(lambda channel, style: emitted.append((channel, style)))

        class _FakeLegendDialog:
            def __init__(self, channel: str, style: dict, parent=None) -> None:
                self.channel = channel
                self.style = style

            def exec(self):
                return QDialog.DialogCode.Accepted

            def values(self) -> dict:
                return {"channel": self.channel, "colour": "#654321", "plot_kind": "Scatter"}

        original_dialog = plot_workspace_module.LegendChannelStyleDialog
        try:
            plot_workspace_module.LegendChannelStyleDialog = _FakeLegendDialog
            self.panel._on_legend_cell_clicked(0, 1)
        finally:
            plot_workspace_module.LegendChannelStyleDialog = original_dialog

        self.assertEqual(emitted, [("A", {"channel": "A", "colour": "#654321", "plot_kind": "Scatter"})])

    def test_legend_entries_are_sorted_alphabetically(self) -> None:
        result = self.panel.generate_plot("Time", ["B", "A"])
        self.assertTrue(result.ok, result.message)
        table_labels = [self.panel.legend_table.item(row, 1).text() for row in range(self.panel.legend_table.rowCount())]
        self.assertEqual(table_labels, ["A", "B"])

        self.panel.set_legend_display("graph")
        legend = self.panel.canvas.axes.get_legend()
        self.assertIsNotNone(legend)
        assert legend is not None
        graph_labels = [text.get_text() for text in legend.get_texts()]
        self.assertEqual(graph_labels, ["A", "B"])

    def test_legend_entries_use_natural_numeric_order(self) -> None:
        source_df = self.state.df
        self.assertIsNotNone(source_df)
        assert source_df is not None
        source_df["TC1"] = source_df["A"]
        source_df["TC2"] = source_df["A"] + 1.0
        source_df["TC10"] = source_df["A"] + 2.0

        result = self.panel.generate_plot("Time", ["TC1", "TC10", "TC2"])

        self.assertTrue(result.ok, result.message)
        table_labels = [self.panel.legend_table.item(row, 1).text() for row in range(self.panel.legend_table.rowCount())]
        self.assertEqual(table_labels, ["TC1", "TC2", "TC10"])

    def test_legend_panel_is_resizable_and_collapsible(self) -> None:
        splitter = self.panel.plot_legend_splitter
        self.assertIsInstance(splitter, QSplitter)
        self.assertFalse(splitter.isCollapsible(0))
        self.assertTrue(splitter.isCollapsible(1))
        self.assertEqual(self.panel.legend_panel.maximumWidth(), self.panel.LEGEND_MAXIMUM_WIDTH)
        header = self.panel.legend_table.horizontalHeader()
        self.assertEqual(header.sectionResizeMode(0), QHeaderView.ResizeMode.Fixed)
        self.assertEqual(header.sectionResizeMode(1), QHeaderView.ResizeMode.Stretch)
        self.assertEqual(header.sectionResizeMode(2), QHeaderView.ResizeMode.Fixed)
        self.assertLessEqual(header.sectionSize(0), 34)
        self.assertGreaterEqual(header.sectionSize(2), 80)
        self.assertLessEqual(header.sectionSize(2), 90)

        self.panel.resize(900, 420)
        self.panel.show()
        QApplication.processEvents()
        splitter.setSizes([900, 0])
        QApplication.processEvents()
        self.assertEqual(splitter.sizes()[1], 0)
        self.assertGreater(splitter.sizes()[0], 0)

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
                [([("Title", ""), ("(Re-)Generate automatic legend", False)], "Axes", "")],
                title="Figure options",
                parent=parent,
                apply=apply,
            )

        def fake_fedit(data, title="", comment="", icon=None, parent=None, apply=None):
            captured["tabs"] = [section[1] for section in data]
            captured["axes_fields"] = [field[0] for field in data[0][0]]
            captured["axis_tick_fields"] = [field[0] for field in data[1][0]]
            captured["best_fit_fields"] = [field[0] for field in data[2][0]]
            if apply is not None:
                best_fit_data = ["A", "Linear", "1"] + ["", "Linear", "1"] * 4
                apply([["updated title"], ["0.25", "0.5", "50", True], best_fit_data, ["graph"]])

        matplotlib_qt_adapter.figureoptions.figure_edit = fake_figure_edit
        matplotlib_qt_adapter._formlayout.fedit = fake_fedit
        try:
            self.panel.canvas.toolbar._figure_edit_with_legend(self.panel.canvas.axes)
        finally:
            matplotlib_qt_adapter.figureoptions.figure_edit = original_figure_edit
            matplotlib_qt_adapter._formlayout.fedit = original_fedit

        self.assertEqual(captured["tabs"], ["Axis", "Axis Ticks", "Best Fits", "Legend"])
        axes_fields = captured["axes_fields"]
        self.assertIsInstance(axes_fields, list)
        self.assertNotIn("(Re-)Generate automatic legend", axes_fields)
        self.assertEqual(
            captured["axis_tick_fields"],
            [
                "X major tick step",
                "Y major tick step",
                "Secondary Y major tick step",
                "Align secondary Y-axis grid with primary axis",
            ],
        )
        self.assertIn("Channel 1", captured["best_fit_fields"])
        self.assertNotIn("Show formula 1", captured["best_fit_fields"])
        self.assertEqual(captured["matplotlib_data"], [["updated title", False]])
        self.assertEqual(self.panel.legend_display(), "graph")
        self.assertEqual(self.panel.best_fit_settings()[0]["channel"], "A")
        self.assertEqual(
            self.panel.axis_tick_setting_texts(),
            {
                "x_major_tick": "0.25",
                "y_major_tick": "0.5",
                "y2_major_tick": "50",
                "align_secondary_y_axis_grid": True,
            },
        )

    def test_figure_options_hides_curves_tab_and_restores_curve_data_for_apply(self) -> None:
        captured: dict[str, object] = {}
        original_figure_edit = matplotlib_qt_adapter.figureoptions.figure_edit
        original_fedit = matplotlib_qt_adapter._formlayout.fedit

        curve_fields = [
            ("Label", "A"),
            (None, "<b>Line</b>"),
            ("Line style", ["-", ("-", "Solid"), ("--", "Dashed")]),
            ("Draw style", ["default", ("default", "Default"), ("steps-post", "Steps (Post)")]),
            ("Width", 1.5),
            ("Color (RGBA)", "#123456"),
            (None, "<b>Marker</b>"),
            ("Style", ["none", ("none", "None"), ("o", "circle")]),
            ("Size", 3.0),
            ("Face color (RGBA)", "#abcdef"),
            ("Edge color (RGBA)", "#654321"),
        ]

        def fake_figure_edit(axes, parent):
            def apply(data):
                captured["matplotlib_data"] = data

            matplotlib_qt_adapter._formlayout.fedit(
                [
                    ([('Title', ''), ('(Re-)Generate automatic legend', False)], "Axes", ""),
                    ([[curve_fields, "A", ""]], "Curves", ""),
                ],
                title="Figure options",
                parent=parent,
                apply=apply,
            )

        def fake_fedit(data, title="", comment="", icon=None, parent=None, apply=None):
            captured["tabs"] = [section[1] for section in data]
            if apply is not None:
                apply([["updated title"], ["", "", "", False], ["", "Linear", "1"] * 5, ["panel"]])

        matplotlib_qt_adapter.figureoptions.figure_edit = fake_figure_edit
        matplotlib_qt_adapter._formlayout.fedit = fake_fedit
        try:
            self.panel.canvas.toolbar._figure_edit_with_legend(self.panel.canvas.axes)
        finally:
            matplotlib_qt_adapter.figureoptions.figure_edit = original_figure_edit
            matplotlib_qt_adapter._formlayout.fedit = original_fedit

        self.assertEqual(captured["tabs"], ["Axis", "Axis Ticks", "Best Fits", "Legend"])
        self.assertEqual(
            captured["matplotlib_data"],
            [["updated title", False], [["A", "-", "default", 1.5, "#123456", "none", 3.0, "#abcdef", "#654321"]]],
        )

    def test_figure_options_axis_ticks_tab_updates_workspace_settings(self) -> None:
        self.panel.generate_plot("Time", ["A", "B"], secondary_y=["B"])
        toolbar = self.panel.canvas.toolbar
        toolbar._figure_edit_with_legend(self.panel.canvas.axes)
        dialog = toolbar._fedit_dialog
        try:
            axis_ticks_form = next(
                widget
                for widget in dialog.formwidget.widgetlist
                if any(label == "X major tick step" for label, _value in getattr(widget, "data", []))
            )
            fields = {label: widget for (label, _value), widget in zip(axis_ticks_form.data, axis_ticks_form.widgets)}
            fields["X major tick step"].setText("0.25")
            fields["Y major tick step"].setText("0.5")
            fields["Secondary Y major tick step"].setText("50")
            fields["Align secondary Y-axis grid with primary axis"].setChecked(True)

            dialog.apply()

            self.assertEqual(
                self.panel.axis_tick_setting_texts(),
                {
                    "x_major_tick": "0.25",
                    "y_major_tick": "0.5",
                    "y2_major_tick": "50",
                    "align_secondary_y_axis_grid": True,
                },
            )
        finally:
            dialog.close()

    def test_figure_options_auto_label_button_updates_axes_fields(self) -> None:
        self.panel.generate_plot("Time", ["A"])
        toolbar = self.panel.canvas.toolbar
        toolbar._figure_edit_with_legend(self.panel.canvas.axes)
        dialog = toolbar._fedit_dialog
        try:
            axes_form = dialog.formwidget.widgetlist[0]
            fields = toolbar._axes_form_fields(axes_form)
            buttons = {button.objectName(): button for button in axes_form.findChildren(QPushButton)}

            buttons["AxisAutoLabelButton"].click()

            self.assertEqual(fields["title"].text(), "A vs Time")
            self.assertEqual(fields["axes"]["x"]["label"].text(), "Time")
            self.assertEqual(fields["axes"]["y"]["label"].text(), "A")
        finally:
            dialog.close()

    def test_figure_options_best_fits_tab_updates_settings(self) -> None:
        self.panel.generate_plot("Time", ["A"])
        toolbar = self.panel.canvas.toolbar
        toolbar._figure_edit_with_legend(self.panel.canvas.axes)
        dialog = toolbar._fedit_dialog
        try:
            best_fits_form = next(
                widget
                for widget in dialog.formwidget.widgetlist
                if any(label == "Channel 1" for label, _value in getattr(widget, "data", []))
            )
            fields = {label: widget for (label, _value), widget in zip(best_fits_form.data, best_fits_form.widgets)}

            self.assertIsInstance(fields["Order 1"], QSpinBox)
            fields["Channel 1"].setCurrentText("A")
            fields["Fit 1"].setCurrentText("Linear")
            fields["Order 1"].setValue(1)
            dialog.apply()

            self.assertEqual(
                self.panel.best_fit_settings(),
                [{"channel": "A", "fit_type": "Linear", "order": 1}],
            )
            self.assertTrue(
                any(bool(getattr(line, "_tda_best_fit", False)) for line in self.panel.canvas.axes.get_lines())
            )
        finally:
            dialog.close()

    def test_figure_options_auto_fit_buttons_use_axis_padding_settings(self) -> None:
        panel = self._panel_with_padding(
            {
                ("axis_scaling", "pad_x_percent"): 10,
                ("axis_scaling", "pad_y_axis"): False,
            }
        )
        panel.generate_plot(
            "Time",
            ["A"],
            axis_limits={"xmin": -5.0, "xmax": 5.0, "ymin": -5.0, "ymax": 5.0},
            auto_fit_axes=False,
        )
        toolbar = panel.canvas.toolbar
        toolbar._figure_edit_with_legend(panel.canvas.axes)
        dialog = toolbar._fedit_dialog
        try:
            axes_form = dialog.formwidget.widgetlist[0]
            fields = toolbar._axes_form_fields(axes_form)
            buttons = {button.objectName(): button for button in axes_form.findChildren(QPushButton)}

            buttons["AxisAutoFitXButton"].click()
            buttons["AxisAutoFitYButton"].click()

            self.assertAlmostEqual(float(fields["axes"]["x"]["min"].text()), -0.1, places=3)
            self.assertAlmostEqual(float(fields["axes"]["x"]["max"].text()), 1.1, places=3)
            source_df = self.state.df
            self.assertIsNotNone(source_df)
            assert source_df is not None
            line_y = [float(value) for value in source_df["A"].to_list()]
            self.assertAlmostEqual(float(fields["axes"]["y"]["min"].text()), min(line_y), places=5)
            self.assertAlmostEqual(float(fields["axes"]["y"]["max"].text()), max(line_y), places=5)
        finally:
            dialog.close()

    def test_figure_options_secondary_y_axis_fields_apply_to_twin_axis(self) -> None:
        self.panel.generate_plot("Time", ["A", "B"], secondary_y=["B"])
        secondary_axes = self.panel.canvas.figure.axes[1]
        toolbar = self.panel.canvas.toolbar
        toolbar._figure_edit_with_legend(self.panel.canvas.axes)
        dialog = toolbar._fedit_dialog
        try:
            axes_form = dialog.formwidget.widgetlist[0]
            fields = toolbar._axes_form_fields(axes_form)
            self.assertIn("secondary_y", fields["axes"])
            buttons = {button.objectName(): button for button in axes_form.findChildren(QPushButton)}
            self.assertIn("AxisAutoFitSecondaryYButton", buttons)

            fields["axes"]["secondary_y"]["min"].setText("-125")
            fields["axes"]["secondary_y"]["max"].setText("125")
            fields["axes"]["secondary_y"]["label"].setText("Right Axis Current")
            dialog.apply()

            self.assertEqual(secondary_axes.get_ylabel(), "Right Axis Current")
            self.assertEqual(tuple(round(value) for value in secondary_axes.get_ylim()), (-125, 125))
        finally:
            dialog.close()

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

    def test_panel_export_legend_excludes_hidden_channels(self) -> None:
        channel_styles = {plot_render_service.normalise_channel_name("A"): {"channel": "A", "hidden": "true"}}
        self.panel.generate_plot("Time", ["A", "B"], channel_styles=channel_styles)
        captured: dict[str, object] = {}
        original_base_save = matplotlib_qt_adapter.NavigationToolbar2QT.save_figure

        def fake_base_save(toolbar, *args):
            legend = self.panel.canvas.axes.get_legend()
            captured["labels"] = [text.get_text() for text in legend.get_texts()] if legend else None
            captured["hidden_series_visible"] = self.panel.canvas.axes.get_lines()[0].get_visible()

        matplotlib_qt_adapter.NavigationToolbar2QT.save_figure = fake_base_save
        try:
            self.panel.canvas.toolbar.save_figure()
        finally:
            matplotlib_qt_adapter.NavigationToolbar2QT.save_figure = original_base_save

        self.assertEqual(captured["labels"], ["B"])
        self.assertFalse(captured["hidden_series_visible"])
        self.assertIsNone(self.panel.canvas.axes.get_legend())

    def test_panel_export_legend_omits_empty_legend_when_all_channels_hidden(self) -> None:
        channel_styles = {
            plot_render_service.normalise_channel_name("A"): {"channel": "A", "hidden": "true"},
            plot_render_service.normalise_channel_name("B"): {"channel": "B", "hidden": "true"},
        }
        self.panel.generate_plot("Time", ["A", "B"], channel_styles=channel_styles)
        captured: dict[str, object] = {}
        original_base_save = matplotlib_qt_adapter.NavigationToolbar2QT.save_figure

        def fake_base_save(toolbar, *args):
            captured["legend"] = self.panel.canvas.axes.get_legend()
            captured["lines_visible"] = [line.get_visible() for line in self.panel.canvas.axes.get_lines()]

        matplotlib_qt_adapter.NavigationToolbar2QT.save_figure = fake_base_save
        try:
            self.panel.canvas.toolbar.save_figure()
        finally:
            matplotlib_qt_adapter.NavigationToolbar2QT.save_figure = original_base_save

        self.assertIsNone(captured["legend"])
        self.assertEqual(captured["lines_visible"], [False, False])
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

    def test_plot_annotations_render_as_matplotlib_artists(self) -> None:
        annotations = [
            {"id": "txt", "type": "text", "text": "Pressure dip", "x": 0.2, "y": 0.5},
            {"id": "arr", "type": "arrow", "start_x": 0.2, "start_y": 0.2, "end_x": 0.4, "end_y": 0.4},
            {"id": "box", "type": "box", "x_min": 0.5, "x_max": 0.8, "y_min": -0.5, "y_max": 0.5},
        ]

        result = self.panel.generate_plot("Time", ["A"], annotations=annotations)

        self.assertTrue(result.ok, result.message)
        artist_ids = {
            str(getattr(artist, "get_gid", lambda: "")())
            for artists in self.panel._annotation_artists.values()
            for artist in artists
        }
        self.assertIn("annotation:txt", artist_ids)
        self.assertIn("annotation:arr", artist_ids)
        self.assertIn("annotation:box", artist_ids)
        self.assertEqual(len(self.panel.current_annotations()), 3)

    def test_annotations_save_with_png_without_selection_handles(self) -> None:
        annotations = [
            {"id": "arr", "type": "arrow", "start_x": 0.2, "start_y": 0.2, "end_x": 0.4, "end_y": 0.4},
        ]
        self.panel.generate_plot("Time", ["A"], annotations=annotations)
        self.panel._select_annotation("arr")
        self.assertTrue(any(bool(getattr(artist, "_tda_annotation_handle", False)) for artists in self.panel._annotation_artists.values() for artist in artists))

        captured = {"had_handle": True}
        original_savefig = self.panel.canvas.figure.savefig

        def fake_savefig(*args, **kwargs):
            captured["had_handle"] = any(
                bool(getattr(collection, "_tda_annotation_handle", False))
                for axes in self.panel.canvas.figure.axes
                for collection in axes.collections
            )

        self.panel.canvas.figure.savefig = fake_savefig
        try:
            result = self.panel.save_plot_png("dummy.png")
        finally:
            self.panel.canvas.figure.savefig = original_savefig

        self.assertTrue(result.ok, result.message)
        self.assertFalse(captured["had_handle"])
        self.assertEqual(self.panel.selected_annotation_id(), "arr")

    def test_annotation_move_and_resize_update_data_coordinates(self) -> None:
        self.panel.set_annotations(
            [
                {"id": "box", "type": "box", "x_min": 0.1, "x_max": 0.3, "y_min": 1.0, "y_max": 2.0},
                {"id": "arr", "type": "arrow", "start_x": 0.2, "start_y": 0.2, "end_x": 0.4, "end_y": 0.4},
            ]
        )
        box = self.panel._annotation_by_id("box")
        arrow = self.panel._annotation_by_id("arr")
        self.assertIsNotNone(box)
        self.assertIsNotNone(arrow)

        self.panel._move_annotation(box, dict(box), 0.5, -0.5)
        self.panel._resize_box_annotation(box, dict(box), "top_right", (1.2, 3.0))
        self.panel._apply_annotation_drag(arrow, dict(arrow), "end", 0.0, 0.0, (0.8, 0.9))

        self.assertAlmostEqual(float(box["x_min"]), 0.6)
        self.assertAlmostEqual(float(box["x_max"]), 1.2)
        self.assertAlmostEqual(float(box["y_min"]), 0.5)
        self.assertAlmostEqual(float(box["y_max"]), 3.0)
        self.assertAlmostEqual(float(arrow["end_x"]), 0.8)
        self.assertAlmostEqual(float(arrow["end_y"]), 0.9)

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
class HelpDialogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dialog = HelpDialog(theme_name="light")

    def tearDown(self) -> None:
        self.dialog.close()

    def _visible_topics(self) -> list[str]:
        return [
            self.dialog.topic_list.item(row).text()
            for row in range(self.dialog.topic_list.count())
            if not self.dialog.topic_list.item(row).isHidden()
        ]

    def test_initial_page_selected(self) -> None:
        self.assertEqual(self.dialog.windowTitle(), "Test Data Analyser Help")
        self.assertFalse(self.dialog.isModal())
        self.assertEqual(self.dialog.topic_list.count(), 15)
        self.assertEqual(self.dialog.topic_list.currentItem().text(), "Getting Started")
        self.assertIn("Normal workflow", self.dialog.content_browser.toPlainText())

    def test_topic_selection_updates_content(self) -> None:
        matches = self.dialog.topic_list.findItems("Troubleshooting", Qt.MatchFlag.MatchExactly)
        self.assertEqual(len(matches), 1)

        self.dialog.topic_list.setCurrentItem(matches[0])

        self.assertIn("Plot is blank", self.dialog.content_browser.toPlainText())

    def test_dataset_editing_help_describes_raw_data_controls(self) -> None:
        matches = self.dialog.topic_list.findItems("Manual Sessions and Dataset Editing", Qt.MatchFlag.MatchExactly)
        self.assertEqual(len(matches), 1)

        self.dialog.topic_list.setCurrentItem(matches[0])
        text = self.dialog.content_browser.toPlainText()

        self.assertIn("+ column header", text)
        self.assertIn("delete removes all selected columns", text)
        self.assertIn("Enter", text)
        self.assertIn("Undo Edit", text)

    def test_keyboard_shortcuts_topic_lists_known_shortcuts(self) -> None:
        matches = self.dialog.topic_list.findItems("Keyboard Shortcuts", Qt.MatchFlag.MatchExactly)
        self.assertEqual(len(matches), 1)

        self.dialog.topic_list.setCurrentItem(matches[0])
        text = self.dialog.content_browser.toPlainText()

        for shortcut in ("Ctrl+O", "Ctrl+S", "Ctrl+N", "Ctrl+L", "Enter", "Esc"):
            self.assertIn(shortcut, text)

    def test_search_filters_topic_titles_and_page_text(self) -> None:
        self.dialog.search_box.setText("legend is unclear")

        self.assertEqual(self._visible_topics(), ["Troubleshooting"])
        self.assertEqual(self.dialog.topic_list.currentItem().text(), "Troubleshooting")
        self.assertIn("Legend is unclear", self.dialog.content_browser.toPlainText())

    def test_search_finds_best_fit_help(self) -> None:
        self.dialog.search_box.setText("best fits")

        self.assertIn("Plot Interaction", self._visible_topics())
        self.assertIn("Best Fits", self.dialog.content_browser.toPlainText())

    def test_search_no_match_shows_empty_state(self) -> None:
        self.dialog.search_box.setText("not a real topic")

        self.assertEqual(self._visible_topics(), [])
        self.assertIn("No help topics matched", self.dialog.content_browser.toPlainText())

    def test_apply_theme_keeps_current_topic_content(self) -> None:
        matches = self.dialog.topic_list.findItems("Run Management", Qt.MatchFlag.MatchExactly)
        self.dialog.topic_list.setCurrentItem(matches[0])

        self.dialog.apply_theme("dark")

        self.assertIn("Generate Comparison Plot", self.dialog.content_browser.toPlainText())
        self.assertIn("QTextBrowser#HelpContent", self.dialog.styleSheet())

    def test_about_topic_contains_version_information(self) -> None:
        matches = self.dialog.topic_list.findItems("About", Qt.MatchFlag.MatchExactly)
        self.dialog.topic_list.setCurrentItem(matches[0])

        text = self.dialog.content_browser.toPlainText()
        self.assertIn("Test Data Analyser - Eaton Edition", text)
        self.assertIn(f"Version: {__version__}", text)


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

    def test_locate_data_file_uses_expected_filename_in_caption(self) -> None:
        result = qt_file_dialogs.locate_data_file(None, "C:/moved", "run.xlsx")
        self.assertEqual(result, "C:/data/file.csv")
        self.assertEqual(self.captured["caption"], "Locate moved data file: run.xlsx")
        self.assertEqual(self.captured["directory"], "C:/moved")


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class _FakeDropUrl:
    def __init__(self, path: str) -> None:
        self._path = path

    def toLocalFile(self) -> str:
        return self._path


class _FakeMimeData:
    def __init__(self, urls: list) -> None:
        self._urls = urls

    def hasUrls(self) -> bool:
        return bool(self._urls)

    def urls(self) -> list:
        return self._urls


class _FakeDropEvent:
    def __init__(self, paths: list) -> None:
        self._mime = _FakeMimeData([_FakeDropUrl(path) for path in paths])
        self.accepted = False
        self.ignored = False

    def mimeData(self) -> _FakeMimeData:
        return self._mime

    def acceptProposedAction(self) -> None:
        self.accepted = True

    def ignore(self) -> None:
        self.ignored = True


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

    def test_header_subtitle_uses_workspace_name(self) -> None:
        window = self._window()
        subtitle = window.findChild(QLabel, "EatonHeaderSubtitle")
        self.assertIsNotNone(subtitle)
        assert subtitle is not None
        self.assertEqual(subtitle.text(), f"Eaton Engineering - Analysis Workspace (V{__version__})")

    def test_application_icon_asset_exists(self) -> None:
        self.assertTrue(_app_icon_path().exists())

    def test_data_panel_load_path_loads_csv_without_dialog(self) -> None:
        window = self._window()
        directory = tempfile.mkdtemp()
        csv_path = os.path.join(directory, "sample.csv")
        pd.DataFrame({"Time": [0.0, 1.0, 2.0], "A": [1.0, 3.0, 2.0]}).to_csv(csv_path, index=False)

        window.data_panel.load_path(csv_path)
        QApplication.processEvents()

        self.assertIsNotNone(window.vm.state.df)
        assert window.vm.state.df is not None
        self.assertEqual(list(window.vm.state.df.columns), ["Time", "A"])
        self.assertEqual(window.data_panel.current_path(), csv_path)

    def test_ribbon_menu_button_repopulates_on_show(self) -> None:
        window = self._window()
        calls: list[object] = []

        def populator(menu: QMenu) -> None:
            calls.append(menu)
            menu.addAction("Example")

        button = window._build_ribbon_button("FILE", "Recent", None, populator)
        self.assertIsNotNone(button.menu())
        assert button.menu() is not None

        button.menu().aboutToShow.emit()
        button.menu().aboutToShow.emit()

        # The menu is cleared and rebuilt on every show, so it never duplicates.
        self.assertEqual(len(calls), 2)
        labels = [action.text() for action in button.menu().actions()]
        self.assertEqual(labels, ["Example"])

    def test_recent_files_menu_populates_from_viewmodel(self) -> None:
        window = self._window()
        directory = tempfile.mkdtemp()
        csv_path = os.path.join(directory, "data.csv")
        pd.DataFrame({"A": [1.0]}).to_csv(csv_path, index=False)
        session_path = os.path.join(directory, "session.json")
        with open(session_path, "w", encoding="utf-8") as handle:
            handle.write("{}")

        window.vm.register_recent_file(csv_path)
        window.vm.register_recent_session(session_path)

        button = window.ribbon_buttons["FILE:Recent"]
        menu = button.menu()
        self.assertIsNotNone(menu)
        assert menu is not None
        menu.aboutToShow.emit()

        entries = [action for action in menu.actions() if action.data()]
        labels = [action.text() for action in entries]
        self.assertIn("data.csv", labels)
        self.assertIn("session.json", labels)
        self.assertTrue(all(action.isEnabled() for action in entries))

    def test_recent_menu_disables_missing_entries(self) -> None:
        window = self._window()
        window.vm.register_recent_file(os.path.join(tempfile.mkdtemp(), "gone.csv"))

        button = window.ribbon_buttons["FILE:Recent"]
        menu = button.menu()
        assert menu is not None
        menu.aboutToShow.emit()

        entries = [action for action in menu.actions() if action.data()]
        self.assertEqual(len(entries), 1)
        self.assertFalse(entries[0].isEnabled())

    def test_drag_and_drop_data_file_calls_data_panel(self) -> None:
        window = self._window()
        directory = tempfile.mkdtemp()
        csv_path = os.path.join(directory, "drop.csv")
        pd.DataFrame({"A": [1.0]}).to_csv(csv_path, index=False)
        calls: list[str] = []
        window.data_panel.load_path = lambda path, sheet_name=None: calls.append(path)

        event = _FakeDropEvent([csv_path])
        window.dropEvent(event)

        self.assertEqual(calls, [csv_path])
        self.assertTrue(event.accepted)

    def test_drag_and_drop_session_calls_load_session_path(self) -> None:
        window = self._window()
        calls: list[str] = []
        window._load_session_path = lambda path: calls.append(path)

        event = _FakeDropEvent([os.path.join("x", "session.json")])
        window.dropEvent(event)

        self.assertEqual(calls, [os.path.join("x", "session.json")])
        self.assertTrue(event.accepted)

    def test_drag_enter_ignores_unsupported_files(self) -> None:
        window = self._window()
        event = _FakeDropEvent([os.path.join("x", "notes.txt")])

        window.dragEnterEvent(event)

        self.assertTrue(event.ignored)
        self.assertFalse(event.accepted)

    def test_autosave_timer_skips_when_no_data(self) -> None:
        window = self._window()
        window.settings_manager.set("general_ui", "auto_save_enabled", True)
        calls: list[str] = []
        window.vm.save_session = lambda path: calls.append(path)

        window._on_autosave_tick()

        self.assertEqual(calls, [])

    def test_autosave_timer_writes_when_dirty(self) -> None:
        window = self._window()
        directory = tempfile.mkdtemp()
        window.settings_manager.set("general_ui", "auto_save_enabled", True)
        window.vm.state.df = pd.DataFrame({"Time": [0.0, 1.0], "A": [1.0, 2.0]})
        window.vm.state.root_file_directory = directory
        window.vm.state.is_dirty = True

        window._on_autosave_tick()

        self.assertTrue(os.path.exists(os.path.join(directory, "autosave.json")))

    def test_plot_tab_bar_is_movable(self) -> None:
        window = self._window()
        self.assertTrue(window.plot_tab_bar.isMovable())

    def test_plot_tab_moved_reorders_profiles(self) -> None:
        window = self._window()
        window.vm.state.plot_profiles = [
            {"name": "P1", "x_column": "", "y_columns": []},
            {"name": "P2", "x_column": "", "y_columns": []},
        ]
        window.vm.state.active_plot_profile_index = 0
        window._sync_plot_tabs()

        window._on_plot_tab_moved(0, 1)

        self.assertEqual([profile["name"] for profile in window.vm.state.plot_profiles], ["P2", "P1"])

    def test_reset_axis_controller_is_wired(self) -> None:
        window = self._window()
        toolbar = window.plot_workspace.canvas.toolbar
        self.assertIsNotNone(toolbar._axis_reset_callback)

    def test_reset_axis_appearance_clears_manual_title(self) -> None:
        window = self._window()
        window.vm.state.plot_profiles = [
            {"name": "P1", "x_column": "", "y_columns": [], "title": "Custom Title"}
        ]
        window.vm.state.active_plot_profile_index = 0

        window._reset_axis_appearance()

        self.assertNotEqual(window.vm.state.plot_profiles[0].get("title"), "Custom Title")

    def test_workflow_help_opens_reusable_modeless_dialog(self) -> None:
        window = self._window()

        window.show_workflow_help()
        QApplication.processEvents()
        first_dialog = window._help_dialog
        window.show_workflow_help()
        QApplication.processEvents()

        self.assertIsInstance(first_dialog, HelpDialog)
        self.assertIs(window._help_dialog, first_dialog)
        self.assertFalse(first_dialog.isModal())
        self.assertTrue(first_dialog.isVisible())
        first_dialog.close()

    def test_direct_help_action_opens_help_dialog(self) -> None:
        window = self._window()
        help_action = window.menuBar().actions()[1]

        self.assertEqual(help_action.text(), "&Help")
        self.assertIsNone(help_action.menu())
        help_action.trigger()
        QApplication.processEvents()
        self.assertIsInstance(window._help_dialog, HelpDialog)
        self.assertTrue(window._help_dialog.isVisible())
        window._help_dialog.close()

    def test_top_menu_uses_direct_settings_action(self) -> None:
        window = self._window()
        menu_actions = window.menuBar().actions()
        labels = [action.text() for action in menu_actions]

        self.assertEqual(labels, ["&Settings", "&Help"])
        self.assertNotIn("&File", labels)
        self.assertNotIn("&Edit", labels)
        self.assertNotIn("&View", labels)
        settings_action = menu_actions[0]
        self.assertEqual(settings_action.text(), "&Settings")
        self.assertIsNone(settings_action.menu())
        self.assertIsNone(menu_actions[1].menu())
        self.assertEqual(window.show_ribbon_action.text(), "Show Ribbon")
        self.assertTrue(window.show_ribbon_action.isCheckable())

        shortcuts = {action.text(): action.shortcut().toString() for action in window.actions()}
        self.assertEqual(shortcuts.get("Open Excel"), "Ctrl+O")
        self.assertEqual(shortcuts.get("Create Session"), "Ctrl+N")
        self.assertEqual(shortcuts.get("Save Session"), "Ctrl+S")
        self.assertEqual(shortcuts.get("Load Session"), "Ctrl+L")

    def test_direct_settings_action_opens_settings_dialog(self) -> None:
        from test_data_analyser.qt_app import main_window as main_window_module

        opened = []

        class _FakeSettingsDialog:
            def __init__(self, view_model, parent) -> None:
                opened.append((view_model, parent))

            def exec(self) -> bool:
                return False

        original_dialog = main_window_module.SettingsDialog
        main_window_module.SettingsDialog = _FakeSettingsDialog
        try:
            window = self._window()
            settings_action = window.menuBar().actions()[0]
            settings_action.trigger()
        finally:
            main_window_module.SettingsDialog = original_dialog

        self.assertEqual(len(opened), 1)
        self.assertIs(opened[0][1], window)

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
        self.assertEqual(window.plot_area.height(), 0)

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
            "FILE:Open Excel",
            "FILE:Create Session",
            "FILE:Save Session",
            "FILE:Load Session",
            "FILE:Export Data",
            "PLOT:Generate Plot",
            "PLOT:Save Plot",
            "PLOT:Clear Plot",
            "PLOT:Runs / Comparison",
            "ANALYSIS:Statistics",
            "ANALYSIS:Raw Data",
            "ANALYSIS:Maths Channels",
            "ANALYSIS:Best Fit Formulas",
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
        self.assertEqual(window.right_splitter.widget(0), window.plot_area)
        self.assertIsInstance(window.plot_tab_bar, QTabBar)
        self.assertEqual(window.plot_tab_bar.count(), 2)
        self.assertEqual(window.plot_tab_bar.tabText(1), "+")
        self.assertNotIn("PLOT:New Plot", window.ribbon_buttons)

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
        self.assertFalse(hasattr(window, "new_plot_button"))
        self.assertEqual(window.plot_tab_bar.tabText(window.plot_tab_bar.count() - 1), "+")

    def test_plus_plot_tab_creates_new_profile(self) -> None:
        window = self._window()
        window.plot_tab_bar.setCurrentIndex(window.plot_tab_bar.count() - 1)
        self.assertEqual(len(window.vm.state.plot_profiles), 2)
        self.assertEqual(window.vm.state.active_plot_profile_index, 1)
        self.assertEqual(window.plot_tab_bar.count(), 3)
        self.assertEqual(window.plot_tab_bar.tabText(1), "Plot 2")
        self.assertEqual(window.plot_tab_bar.tabText(2), "+")

    def test_new_plot_preserves_current_x_axis_selection(self) -> None:
        window = self._window()
        window.vm.state.df = pd.DataFrame(
            {"Sample": [0.0, 1.0], "Time": [10.0, 20.0], "Flow": [5.0, 6.0], "A": [1.0, 2.0]}
        )
        window._on_file_loaded(window.vm.state.column_names())
        window.axis_panel.apply_selection(window.vm.state.column_names(), "Time", ["A"], [])

        window._new_plot_profile()
        self.assertEqual(window.axis_panel.x_column(), "Time")
        self.assertEqual(window.vm.state.plot_profiles[1]["x_column"], "Time")

        window.axis_panel.apply_selection(window.vm.state.column_names(), "Flow", [], [])
        window._new_plot_profile()
        self.assertEqual(window.axis_panel.x_column(), "Flow")
        self.assertEqual(window.vm.state.plot_profiles[2]["x_column"], "Flow")

    def test_new_plot_falls_back_when_current_x_axis_is_unavailable(self) -> None:
        window = self._window()
        window.vm.state.df = pd.DataFrame({"Sample": [0.0, 1.0], "A": [1.0, 2.0]})
        window._on_file_loaded(window.vm.state.column_names())
        window.vm.state.current_x_axis = "Removed Channel"

        window._new_plot_profile()

        self.assertEqual(window.axis_panel.x_column(), "Sample")
        self.assertEqual(window.vm.state.plot_profiles[1]["x_column"], "Sample")

    def test_plot_tabs_preserve_axis_selection_when_switching(self) -> None:
        window = self._window()
        window.vm.state.df = pd.DataFrame({"Time": [0.0, 1.0], "A": [1.0, 2.0], "B": [3.0, 4.0]})
        window._on_file_loaded(window.vm.state.column_names())
        window.axis_panel.apply_selection(window.vm.state.column_names(), "Time", ["A"], [])

        window._new_plot_profile()
        self.assertEqual(window.plot_tab_bar.count(), 3)
        self.assertEqual(window.vm.state.active_plot_profile_index, 1)
        window.axis_panel.apply_selection(window.vm.state.column_names(), "Time", ["B"], [])

        window.plot_tab_bar.setCurrentIndex(0)
        self.assertEqual(window.axis_panel.selected_y(), ["A"])
        window.plot_tab_bar.setCurrentIndex(1)
        self.assertEqual(window.axis_panel.selected_y(), ["B"])

    def test_sheet_change_preserves_profiles_limits_notes_and_plot(self) -> None:
        window = self._window()
        first_sheet = pd.DataFrame({"Time": [0.0, 1.0, 2.0], "A": [1.0, 2.0, 3.0], "B": [3.0, 2.0, 1.0]})
        window.vm.state.df = first_sheet
        window.vm.state.sheet_name = "First"
        window._on_file_loaded(window.vm.state.column_names())

        window._new_plot_profile()
        window.axis_panel.apply_selection(window.vm.state.column_names(), "Time", ["B"], [])
        window.vm.state.limit_lines = [
            {
                "name": "Max",
                "type": "Upper Limit",
                "applies_to": "All selected Y channels",
                "points": [{"x": 0.0, "y": 10.0}, {"x": 2.0, "y": 10.0}],
            }
        ]
        window.vm.engineering_notes.update_field("objective", "Keep these notes")
        window.notes_panel.load_from_state()
        window._on_generate_plot()
        self.assertTrue(window._plot_generated)
        self.assertTrue(window.plot_workspace.canvas.axes.get_lines())
        original_labels = [line.get_label() for line in window.plot_workspace.canvas.axes.get_lines()]
        original_y_data = [list(line.get_ydata()) for line in window.plot_workspace.canvas.axes.get_lines()]

        second_sheet = pd.DataFrame({"Elapsed": [0.0, 1.0, 2.0], "Voltage": [12.0, 12.5, 12.2]})
        window.vm.state.df = second_sheet
        window.vm.state.sheet_name = "Second"
        window._on_sheet_changed(window.vm.state.column_names())

        self.assertEqual(len(window.vm.state.plot_profiles), 2)
        self.assertEqual(window.plot_tab_bar.tabText(1), "Plot 2")
        self.assertEqual(window.axis_panel.selected_y(), [])
        self.assertEqual(len(window.vm.state.limit_lines), 1)
        self.assertEqual(window.vm.state.limit_lines[0]["name"], "Max")
        self.assertEqual(window.vm.engineering_notes.get_notes()["objective"], "Keep these notes")
        self.assertEqual(window.notes_panel._editors["objective"].toPlainText(), "Keep these notes")
        self.assertTrue(window._plot_generated)
        self.assertTrue(window.plot_workspace.canvas.axes.get_lines())
        self.assertEqual([line.get_label() for line in window.plot_workspace.canvas.axes.get_lines()], original_labels)
        self.assertEqual([list(line.get_ydata()) for line in window.plot_workspace.canvas.axes.get_lines()], original_y_data)

        window.plot_tab_bar.setCurrentIndex(0)
        window.plot_tab_bar.setCurrentIndex(1)
        self.assertTrue(window.plot_workspace.canvas.axes.get_lines())
        self.assertEqual([line.get_label() for line in window.plot_workspace.canvas.axes.get_lines()], original_labels)
        self.assertEqual([list(line.get_ydata()) for line in window.plot_workspace.canvas.axes.get_lines()], original_y_data)

    def test_plot_tab_duplicate_rename_delete_handlers(self) -> None:
        window = self._window()
        window._duplicate_plot_profile(0)
        self.assertEqual(window.plot_tab_bar.count(), 3)
        self.assertEqual(window.plot_tab_bar.tabText(1), "Plot 1 Copy")
        self.assertEqual(window.vm.state.active_plot_profile_index, 1)

        window._rename_plot_profile(1, "Renamed Plot")
        self.assertEqual(window.plot_tab_bar.tabText(1), "Renamed Plot")
        window._delete_plot_profile(1, confirm=False)
        self.assertEqual(window.plot_tab_bar.count(), 2)
        self.assertEqual(window.vm.state.active_plot_profile_index, 0)

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

    def test_analysis_group_reaches_best_fit_formulas_panel(self) -> None:
        window = self._window()
        window.ribbon_buttons["ANALYSIS:Best Fit Formulas"].click()
        self.assertIs(window.lower_stack.currentWidget(), window.analysis_stack)
        self.assertIs(window.analysis_stack.currentWidget(), window.best_fit_formulas_panel)

    def test_best_fit_formulas_panel_updates_after_plot_generation(self) -> None:
        window = self._window()
        window.vm.state.df = pd.DataFrame({"Time": [0.0, 1.0, 2.0], "A": [1.0, 3.0, 5.0]})
        window._on_file_loaded(window.vm.state.column_names())
        window.axis_panel.apply_selection(window.vm.state.column_names(), "Time", ["A"], [])
        window.plot_workspace.set_best_fit_settings(
            [{"channel": "A", "fit_type": "Linear", "order": 1}]
        )

        window._on_generate_plot()

        window.ribbon_buttons["ANALYSIS:Best Fit Formulas"].click()
        self.assertEqual(window.best_fit_formulas_panel.table.rowCount(), 1)
        self.assertEqual(window.best_fit_formulas_panel.table.item(0, 0).text(), "A")
        self.assertIn("y =", window.best_fit_formulas_panel.table.item(0, 3).text())

    def test_legend_hide_button_updates_profile_and_plot(self) -> None:
        window = self._window()
        window.vm.state.df = pd.DataFrame({"Time": [0.0, 1.0, 2.0], "A": [1.0, 2.0, 3.0], "B": [3.0, 2.0, 1.0]})
        window._on_file_loaded(window.vm.state.column_names())
        window.axis_panel.apply_selection(window.vm.state.column_names(), "Time", ["A", "B"], [])
        window._on_generate_plot()

        table_labels = [
            window.plot_workspace.legend_table.item(row, 1).text()
            for row in range(window.plot_workspace.legend_table.rowCount())
        ]
        row = table_labels.index("A")
        visibility_cell = window.plot_workspace.legend_table.cellWidget(row, 2)
        self.assertIsNotNone(visibility_cell)
        assert visibility_cell is not None
        checkbox = visibility_cell.findChild(QCheckBox, "LegendVisibilityCheckBox")
        self.assertIsInstance(checkbox, QCheckBox)
        assert isinstance(checkbox, QCheckBox)
        checkbox.setChecked(False)

        key = plot_render_service.normalise_channel_name("A")
        style = window.vm.state.active_plot_profile()["legend"]["channel_overrides"][key]
        self.assertEqual(style["hidden"], "true")
        lines = {line.get_label(): line for line in window.plot_workspace.canvas.axes.get_lines()}
        self.assertFalse(lines["A"].get_visible())
        self.assertTrue(lines["B"].get_visible())
        refreshed_labels = [
            window.plot_workspace.legend_table.item(row, 1).text()
            for row in range(window.plot_workspace.legend_table.rowCount())
        ]
        refreshed_row = refreshed_labels.index("A")
        show_cell = window.plot_workspace.legend_table.cellWidget(refreshed_row, 2)
        self.assertIsNotNone(show_cell)
        assert show_cell is not None
        show_checkbox = show_cell.findChild(QCheckBox, "LegendVisibilityCheckBox")
        self.assertIsInstance(show_checkbox, QCheckBox)
        assert isinstance(show_checkbox, QCheckBox)
        self.assertFalse(show_checkbox.isChecked())

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
        self.assertTrue(window.body_splitter.isCollapsible(0))
        self.assertFalse(window.body_splitter.isCollapsible(1))
        self.assertEqual(window.left_scroll.minimumWidth(), MainWindow.LEFT_RAIL_MINIMUM_WIDTH)
        self.assertEqual(window.left_scroll.maximumWidth(), MainWindow.LEFT_RAIL_MAXIMUM_WIDTH)
        self.assertLess(window.left_scroll.minimumWidth(), MainWindow.LEFT_RAIL_INITIAL_WIDTH)
        self.assertGreater(MainWindow.LEFT_RAIL_MAXIMUM_WIDTH, 500)
        self.assertGreaterEqual(window.body_splitter.sizes()[0], MainWindow.LEFT_RAIL_INITIAL_WIDTH - 5)
        self.assertEqual(window.lower_stack.sizePolicy().horizontalPolicy(), QSizePolicy.Policy.Ignored)

        window.body_splitter.setSizes([520, 800])
        QApplication.processEvents()
        self.assertGreaterEqual(window.body_splitter.sizes()[0], 500)

        window.data_panel.sheet_combo.addItems(
            ["Temperatures", "Thermal Fuses and Windings Temp", "Thermal Fuses and Windings  (2)"]
        )
        window.data_panel.sheet_row.setVisible(True)
        window.body_splitter.setSizes([MainWindow.LEFT_RAIL_MAXIMUM_WIDTH, 680])
        QApplication.processEvents()
        window.body_splitter.setSizes([MainWindow.LEFT_RAIL_MINIMUM_WIDTH, 1080])
        QApplication.processEvents()
        self.assertLessEqual(window.data_panel.sheet_combo.width(), window.left_scroll.viewport().width())
        self.assertLessEqual(window.axis_panel.x_combo.width(), window.left_scroll.viewport().width())

        total_width = sum(window.body_splitter.sizes())
        window.body_splitter.setSizes([total_width, 0])
        QApplication.processEvents()
        self.assertLessEqual(window.body_splitter.sizes()[0], MainWindow.LEFT_RAIL_MAXIMUM_WIDTH)
        self.assertGreater(window.body_splitter.sizes()[1], 0)

        total_width = sum(window.body_splitter.sizes())
        window.body_splitter.setSizes([0, total_width])
        QApplication.processEvents()
        self.assertEqual(window.body_splitter.sizes()[0], 0)
        self.assertGreater(window.body_splitter.sizes()[1], 0)

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

    def test_save_session_prefills_loaded_session_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            session_path = os.path.join(directory, "loaded_session.json")
            selected_save_path = os.path.join(directory, "saved_session.json")
            with open(session_path, "w", encoding="utf-8") as handle:
                handle.write("{}")

            manager = SettingsManager(os.path.join(directory, "settings.json"))
            window = MainWindow(manager)

            class _Result:
                ok = True
                message = "Session loaded."
                warnings: list[str] = []
                payload: object | None = {}

            class _SaveResult:
                ok = True
                message = "Saved."
                payload = selected_save_path

            original_open_dialog = qt_file_dialogs.open_session_file
            original_save_dialog = qt_file_dialogs.save_session_file
            original_show_result = qt_message_service.show_result
            captured: dict[str, str] = {}

            qt_file_dialogs.open_session_file = lambda parent, initial_dir="": session_path
            window.vm.restore_session = lambda path: _Result()
            window._apply_loaded_session = lambda selection: None

            def fake_save_dialog(parent, initial_dir=""):
                captured["initial_dir"] = initial_dir
                return selected_save_path

            qt_file_dialogs.save_session_file = fake_save_dialog
            qt_message_service.show_result = lambda *args, **kwargs: None
            window.vm.capture_working_state = lambda **kwargs: None
            window.vm.save_session = lambda path: _SaveResult()
            try:
                window.load_session()
                window.save_session()
            finally:
                qt_file_dialogs.open_session_file = original_open_dialog
                qt_file_dialogs.save_session_file = original_save_dialog
                qt_message_service.show_result = original_show_result

            self.assertEqual(captured["initial_dir"], session_path)
            self.assertEqual(window._current_session_path, selected_save_path)


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

    def test_plot_annotations_save_and_restore_with_session(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = os.path.join(directory, "data.csv")
            pd.DataFrame({"Time": [0.0, 1.0, 2.0, 3.0], "A": [1.0, 2.0, 3.0, 4.0]}).to_csv(data_path, index=False)
            session_path = os.path.join(directory, "session.json")

            source = self._make_window(directory)
            source.vm.data_loading.load_file(data_path, None)
            source._on_file_loaded(source.vm.state.column_names())
            source.axis_panel.apply_selection(source.vm.state.column_names(), "Time", ["A"], [])
            source._on_generate_plot()
            source.plot_workspace.set_annotations(
                [
                    {"id": "txt", "type": "text", "text": "Pressure dip", "x": 1.0, "y": 2.0},
                    {"id": "arr", "type": "arrow", "start_x": 1.0, "start_y": 3.0, "end_x": 2.0, "end_y": 2.0},
                    {"id": "box", "type": "box", "x_min": 0.5, "x_max": 2.5, "y_min": 1.5, "y_max": 3.5},
                ]
            )
            self._save_session(source, session_path)

            target = self._make_window(directory)
            self._load_session(target, session_path)

            restored = target.plot_workspace.current_annotations()
            self.assertEqual([annotation["type"] for annotation in restored], ["text", "arrow", "box"])
            self.assertEqual(restored[0]["text"], "Pressure dip")
            self.assertTrue(target._plot_generated)
            self.assertIn("txt", target.plot_workspace._annotation_artists)
            self.assertIn("arr", target.plot_workspace._annotation_artists)
            self.assertIn("box", target.plot_workspace._annotation_artists)

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

    def test_load_session_refreshes_modified_excel_plot_and_raw_data(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = os.path.join(directory, "data.xlsx")
            with pd.ExcelWriter(data_path, engine="openpyxl") as writer:
                pd.DataFrame({"Time": [0.0, 1.0, 2.0], "A": [1.0, 2.0, 3.0]}).to_excel(
                    writer,
                    sheet_name="Data",
                    index=False,
                )
            session_path = os.path.join(directory, "session.json")

            source = self._make_window(directory)
            source.vm.data_loading.load_file(data_path, "Data")
            source._on_file_loaded(source.vm.state.column_names())
            source.axis_panel.apply_selection(source.vm.state.column_names(), "Time", ["A"], [])
            source._on_generate_plot()
            self._save_session(source, session_path)

            with pd.ExcelWriter(data_path, engine="openpyxl") as writer:
                pd.DataFrame(
                    {"Time": [0.0, 1.0, 2.0], "A": [10.0, 20.0, 30.0], "New Channel": [7.0, 8.0, 9.0]}
                ).to_excel(writer, sheet_name="Data", index=False)

            target = self._make_window(directory)
            self._load_session(target, session_path)

            self.assertEqual(list(target.vm.state.df["A"]), [10.0, 20.0, 30.0])
            self.assertIn("New Channel", target.vm.state.column_names())
            self.assertTrue(target._plot_generated)
            lines = target.plot_workspace.canvas.axes.get_lines()
            self.assertTrue(lines)
            self.assertEqual(list(lines[0].get_ydata()), [10.0, 20.0, 30.0])
            self.assertEqual(list(target.raw_data_panel.model.dataframe["A"]), [10.0, 20.0, 30.0])

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

    def test_load_session_relinks_moved_main_data_file(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            old_dir = os.path.join(directory, "old")
            new_dir = os.path.join(directory, "new")
            os.mkdir(old_dir)
            os.mkdir(new_dir)
            data_path = os.path.join(old_dir, "data.csv")
            moved_path = os.path.join(new_dir, "data.csv")
            session_path = os.path.join(directory, "session.json")
            pd.DataFrame({"Time": [0.0, 1.0, 2.0], "A": [1.0, 2.0, 3.0]}).to_csv(data_path, index=False)

            source = self._make_window(directory)
            source.vm.data_loading.load_file(data_path, None)
            source._on_file_loaded(source.vm.state.column_names())
            source.axis_panel.apply_selection(source.vm.state.column_names(), "Time", ["A"], [])
            self._save_session(source, session_path)
            os.replace(data_path, moved_path)

            target = self._make_window(directory)
            original_session_dialog = qt_file_dialogs.open_session_file
            original_locate_dialog = qt_file_dialogs.locate_data_file
            original_warning = qt_message_service.warning
            captured: dict[str, str] = {}
            warnings: list[str] = []

            def fake_locate(parent, initial_dir="", expected_filename=""):
                captured["initial_dir"] = initial_dir
                captured["expected_filename"] = expected_filename
                return moved_path

            qt_file_dialogs.open_session_file = lambda parent, initial_dir="": session_path
            qt_file_dialogs.locate_data_file = fake_locate
            qt_message_service.warning = lambda parent, title, message: warnings.append(message)
            try:
                target.load_session()
            finally:
                qt_file_dialogs.open_session_file = original_session_dialog
                qt_file_dialogs.locate_data_file = original_locate_dialog
                qt_message_service.warning = original_warning

            self.assertEqual(captured["expected_filename"], "data.csv")
            self.assertEqual(target.vm.state.filepath, Path(moved_path))
            self.assertEqual(target.vm.state.column_names(), ["Time", "A"])
            self.assertEqual(target.axis_panel.x_column(), "Time")
            self.assertEqual(target.axis_panel.selected_y(), ["A"])
            self.assertIn("could not be loaded", warnings[0])
            self.assertEqual(target.data_panel.file_label.text(), str(Path(moved_path)))

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

    def test_generate_plot_preserves_appearance_for_plot_kind_only_change(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = os.path.join(directory, "data.csv")
            pd.DataFrame({"Time": [0.0, 1.0, 2.0, 3.0], "A": [1.0, 2.0, 3.0, 4.0]}).to_csv(data_path, index=False)

            window = self._make_window(directory)
            window.vm.data_loading.load_file(data_path, None)
            window._on_file_loaded(window.vm.state.column_names())
            window.axis_panel.apply_selection(window.vm.state.column_names(), "Time", ["A"], [])
            window._on_generate_plot()
            axes = window.plot_workspace.canvas.axes
            axes.set_title("Manual Title")
            axes.set_xlabel("Manual X")
            axes.set_ylabel("Manual Y")
            axes.set_xlim(0.5, 2.5)
            axes.set_ylim(-1.0, 9.0)
            window.plot_workspace.set_axis_tick_settings({"x_major_tick": "0.5", "y_major_tick": "2", "y2_major_tick": "", "align_secondary_y_axis_grid": False})
            window.axis_panel.plot_kind_combo.setCurrentText("Scatter")

            window._on_generate_plot()
            current_axes = window.plot_workspace.canvas.axes

            self.assertEqual(current_axes.get_title(), "Manual Title")
            self.assertEqual(current_axes.get_xlabel(), "Manual X")
            self.assertEqual(current_axes.get_ylabel(), "Manual Y")
            self.assertAlmostEqual(current_axes.get_xlim()[0], 0.5, places=2)
            self.assertAlmostEqual(current_axes.get_xlim()[1], 2.5, places=2)
            self.assertEqual(window.plot_workspace.axis_tick_setting_texts()["x_major_tick"], "0.5")
            self.assertTrue(window.plot_workspace.canvas.axes.collections)

    def test_generate_plot_resets_appearance_for_different_channel_range(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = os.path.join(directory, "data.csv")
            pd.DataFrame(
                {
                    "Time": [0.0, 1.0, 2.0, 3.0],
                    "A": [1.0, 2.0, 3.0, 4.0],
                    "High Pressure": [1000.0, 1200.0, 1400.0, 1600.0],
                }
            ).to_csv(data_path, index=False)

            window = self._make_window(directory)
            window.vm.data_loading.load_file(data_path, None)
            window._on_file_loaded(window.vm.state.column_names())
            window.axis_panel.apply_selection(window.vm.state.column_names(), "Time", ["A"], [])
            window._on_generate_plot()
            axes = window.plot_workspace.canvas.axes
            axes.set_title("Manual Title")
            axes.set_xlabel("Manual X")
            axes.set_ylabel("Manual Y")
            axes.set_xlim(0.5, 2.5)
            axes.set_ylim(-1.0, 9.0)
            window.plot_workspace.set_axis_tick_settings({"x_major_tick": "0.5", "y_major_tick": "2", "y2_major_tick": "", "align_secondary_y_axis_grid": False})
            window.axis_panel.apply_selection(window.vm.state.column_names(), "Time", ["High Pressure"], [])

            window._on_generate_plot()

            self.assertEqual(window.plot_workspace.canvas.axes.get_title(), "Engineering Test Data")
            self.assertEqual(window.plot_workspace.canvas.axes.get_xlabel(), "Time")
            self.assertEqual(window.plot_workspace.canvas.axes.get_ylabel(), "Selected Signals")
            self.assertNotAlmostEqual(window.plot_workspace.canvas.axes.get_xlim()[0], 0.5, places=2)
            self.assertEqual(window.plot_workspace.axis_tick_setting_texts()["x_major_tick"], "")

    def test_generate_plot_preserves_appearance_for_similar_added_channel(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            data_path = os.path.join(directory, "data.csv")
            pd.DataFrame(
                {
                    "Time": [0.0, 1.0, 2.0, 3.0],
                    "Motor Pressure 1": [10.0, 20.0, 30.0, 40.0],
                    "Motor Pressure 2": [11.0, 21.0, 31.0, 41.0],
                }
            ).to_csv(data_path, index=False)

            window = self._make_window(directory)
            window.vm.data_loading.load_file(data_path, None)
            window._on_file_loaded(window.vm.state.column_names())
            window.axis_panel.apply_selection(window.vm.state.column_names(), "Time", ["Motor Pressure 1"], [])
            window._on_generate_plot()
            window.plot_workspace.canvas.axes.set_title("Manual Title")
            window.plot_workspace.canvas.axes.set_ylim(0.0, 50.0)
            window.plot_workspace.set_axis_tick_settings({"x_major_tick": "1", "y_major_tick": "10", "y2_major_tick": "", "align_secondary_y_axis_grid": False})
            window.axis_panel.apply_selection(
                window.vm.state.column_names(),
                "Time",
                ["Motor Pressure 1", "Motor Pressure 2"],
                [],
            )

            window._on_generate_plot()

            self.assertEqual(window.plot_workspace.canvas.axes.get_title(), "Manual Title")
            self.assertEqual(window.plot_workspace.canvas.axes.get_ylim(), (0.0, 50.0))
            self.assertEqual(window.plot_workspace.axis_tick_setting_texts()["y_major_tick"], "10")


@unittest.skipUnless(PYSIDE_AVAILABLE, "PySide6 is not installed")
class ManualSessionUiTests(unittest.TestCase):
    """Create Session, full-dataset editing, and numeric-only selectors."""

    def _make_window(self, directory: str) -> "MainWindow":
        manager = SettingsManager(os.path.join(directory, "settings.json"))
        return MainWindow(manager)

    def test_create_session_enters_edit_mode_and_manual_label(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            window = self._make_window(directory)
            window.ribbon_buttons["FILE:Create Session"].click()
            self.assertTrue(window.vm.state.is_manual_source)
            self.assertTrue(window.raw_data_panel._edit_mode)
            self.assertTrue(window.raw_data_panel.edit_mode_check.isChecked())
            self.assertEqual(
                window.data_panel.file_label.text(), "Manual data session (no linked file)."
            )
            self.assertGreater(window.axis_panel.x_combo.count(), 0)

    def test_numeric_only_selectors_exclude_text_columns(self) -> None:
        from test_data_analyser.services import dataset_service

        with tempfile.TemporaryDirectory() as directory:
            window = self._make_window(directory)
            df = pd.DataFrame(
                {"Time": [0.0, 1.0], "Pressure": [10.0, 11.0], "Label": ["a", "b"]}
            )
            window.vm.state.df = df
            window.vm.state.channel_registry = dataset_service.build_registry_for_dataframe(df)
            window._on_file_loaded(window.vm.state.column_names())

            x_items = [window.axis_panel.x_combo.itemText(i) for i in range(window.axis_panel.x_combo.count())]
            self.assertIn("Time", x_items)
            self.assertIn("Pressure", x_items)
            self.assertNotIn("Label", x_items)

    def test_rename_column_updates_selectors(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            window = self._make_window(directory)
            window.ribbon_buttons["FILE:Create Session"].click()
            channel_id = window.vm.state.channel_registry.id_for_name("Column 1")
            self.assertTrue(window.vm.dataset.rename_column(channel_id, "Time").ok)
            window.raw_data_panel.datasetChanged.emit()

            x_items = [window.axis_panel.x_combo.itemText(i) for i in range(window.axis_panel.x_combo.count())]
            self.assertIn("Time", x_items)
            self.assertNotIn("Column 1", x_items)

    def test_manual_session_generates_plot(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            window = self._make_window(directory)
            window.ribbon_buttons["FILE:Create Session"].click()
            registry = window.vm.state.channel_registry
            window.vm.dataset.rename_column(registry.id_for_name("Column 1"), "Time")
            window.vm.dataset.rename_column(registry.id_for_name("Column 2"), "Pressure")
            time_id = registry.id_for_name("Time")
            pressure_id = registry.id_for_name("Pressure")
            for row, (t_value, p_value) in enumerate([(0.0, 10.0), (1.0, 11.0), (2.0, 12.0)]):
                window.vm.dataset.set_cell(time_id, row, str(t_value))
                window.vm.dataset.set_cell(pressure_id, row, str(p_value))
            window._on_dataset_changed()

            window.axis_panel.apply_selection(window._plottable_columns(), "Time", ["Pressure"], [])
            window._on_generate_plot()

            self.assertTrue(window._plot_generated)
            self.assertTrue(window.plot_workspace.canvas.axes.get_lines())


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
