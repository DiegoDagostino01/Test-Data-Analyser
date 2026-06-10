---
name: pyside6-qt-gui-maintainer
description: "Use when: modifying PySide6 / Qt UI layout, widgets, signals, slots, tabs, splitters, tables, dialogs, settings UI, or Matplotlib Qt canvas behaviour."
---

# PySide6 Qt GUI Maintainer

Use this skill when changing the Test Data Analyser Qt interface.

## Rules

- Keep PySide6 imports inside `test_data_analyser/qt_app/` only.
- Keep widgets thin: read UI state, call a viewmodel, render the result, and
  emit explicit signals.
- Keep viewmodels free of Qt objects, dialogs, and message boxes.
- Preserve existing widget attribute names and signal contracts unless the task
  explicitly requires a rename.
- Use `qt_file_dialogs` and `qt_message_service` at the Qt boundary instead of
  opening dialogs from services or viewmodels.
- Keep Eaton styling in `theme.py` and colour sources in `core/config.py`.
- Use fully qualified Qt enum forms in new code, such as
  `Qt.CheckState.Checked` and `QHeaderView.ResizeMode.Interactive`.
- Be careful with `QTabWidget`, `QStackedWidget`, `QSplitter`, `QTableView`,
  `QListWidget`, `QComboBox`, `QScrollArea`, `QDialog`, and Matplotlib canvas
  redraw/export behaviour.
- For tests that touch modal helpers, patch `qt_message_service` functions so
  headless tests do not block.

## Manual checks

- Launch with `python run_qt_app.py` or `python -m test_data_analyser` when a
  visible UI check is needed.
- Use `QT_QPA_PLATFORM=offscreen` for explicit headless Qt smoke tests.
