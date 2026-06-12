---
name: pyside6-qt-gui-maintainer
description: "Use when: modifying PySide6 / Qt UI layout, widgets, signals, slots, tabs, splitters, tables, dialogs, settings UI, or Matplotlib Qt canvas behaviour."
---

# PySide6 Qt GUI Maintainer

Use this skill when changing the Test Data Analyser Qt interface.

## Rules

- Keep PySide6 imports inside `test_data_analyser/qt_app/` only.
- If a task requires PySide6 types outside `test_data_analyser/qt_app/` (for
  example, in tests or utilities), place the import inside
  `test_data_analyser/qt_app/` and expose only plain Python types at the
  boundary. Never import PySide6 directly in test files; use the patch approach
  described in the testing rule instead.
- Widgets must contain no business logic. Their only responsibilities are:
  reading UI state, invoking viewmodel methods, rendering viewmodel output, and
  emitting signals. Do not add conditional logic or data transformations inside
  widget classes.
- Keep viewmodels free of Qt objects, dialogs, and message boxes.
- Preserve existing widget attribute names and signal contracts. Only rename
  them when the user instruction contains an explicit renaming directive (for
  example, "rename X to Y" or "change the attribute name"). Do not rename as a
  side-effect of refactoring.
- Use `qt_file_dialogs` and `qt_message_service` at the Qt boundary instead of
  opening dialogs from services or viewmodels.
- Keep Eaton styling in `theme.py` and colour sources in `core/config.py`.
- Use fully qualified Qt enum forms in new code, such as
  `Qt.CheckState.Checked` and `QHeaderView.ResizeMode.Interactive`.
- When modifying an existing file that contains Qt4/Qt5-style short-form enums
  (for example, `Qt.Checked` or `QHeaderView.Interactive`), update all enums in
  that file to fully qualified form as part of the change. Do not leave mixed
  enum styles within the same file.
- Apply these widget-specific rules:
  - `QTabWidget` / `QStackedWidget`: do not change selected indices
    programmatically without updating the companion viewmodel state.
  - `QSplitter`: preserve object names, saved sizes, and restore-state keys.
  - `QTableView`: set resize modes explicitly; do not rely on header defaults.
  - `QListWidget`: preserve item data roles and selection mode when changing
    display labels.
  - `QComboBox`: preserve stored item data and signal blocking during programmatic
    refreshes.
  - `QScrollArea`: keep `setWidgetResizable(True)` unless the task explicitly
    changes scroll sizing behaviour.
  - `QDialog`: keep modal helpers behind `qt_message_service` or dedicated Qt
    boundary helpers.
  - Matplotlib canvas: call `canvas.draw_idle()` for UI redraws; reserve
    `canvas.draw()` for export or deterministic test paths that require an
    immediate render.
- For tests that touch modal helpers, patch `qt_message_service` functions so
  headless tests do not block.

## Manual checks

- Launch with `python run_qt_app.py` or `python -m test_data_analyser` when a
  visible UI check is needed.
- Use `QT_QPA_PLATFORM=offscreen` for explicit headless Qt smoke tests.
