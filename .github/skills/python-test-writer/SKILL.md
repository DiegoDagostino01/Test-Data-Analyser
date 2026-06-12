---
name: python-test-writer
description: "Use when: creating or updating unittest tests for services, domain models, viewmodels, plotting helpers, pandas logic, Qt adapters, or PySide6 panels."
---

# Python Test Writer

Write practical tests for this project using the existing stdlib `unittest`
suite.

## Rules

- Use `python -m unittest discover -s tests` as the default test command.
- Place all new test files under the `tests/` directory, named
  `test_<module_name>.py`, so they are discovered by
  `python -m unittest discover -s tests`.
- When no existing test file for the module exists, follow the structure of
  `tests/test_qt_adapters.py` as the style reference for imports,
  `setUp`/`tearDown`, and fixture patterns.
- Prioritize pure functions, services, and viewmodels before Qt widget tests.
- Use small pandas DataFrames as fixtures.
- Keep tests readable and close to realistic engineering data cases.
- For Qt tests, run under the offscreen platform. At the top of each Qt test
  method, use:
  ```python
  try:
      import PySide6
  except ImportError:
      raise unittest.SkipTest("PySide6 not available")
  ```
- Patch `qt_message_service` modal functions in panel tests so tests do not
  block.
- Prefer regression tests for fixed bugs.
- Mock only I/O boundaries and Qt modal dialogs (e.g. `qt_message_service`).
  Do not mock internal service methods or viewmodel calculations.

## Useful cases

- Numeric strings, blanks, `N/A`, commas, dashes, and units.
- Grouped Excel-style columns and multiple Y columns.
- Secondary Y-axis selections and analysis-window filtering.
- Limit-line interpolation/margins, cursor point compare, raw-data edits,
  maths channels, runs comparison, session save/load, and figure export guards.
