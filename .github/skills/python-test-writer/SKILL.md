---
name: python-test-writer
description: "Use when: creating or updating unittest tests for services, domain models, viewmodels, plotting helpers, pandas logic, Qt adapters, or PySide6 panels."
---

# Python Test Writer

Write practical tests for this project using the existing stdlib `unittest`
suite.

## Rules

- Use `python -m unittest discover -s tests` as the default test command.
- Prioritize pure functions, services, and viewmodels before Qt widget tests.
- Use small pandas DataFrames as fixtures.
- Keep tests readable and close to realistic engineering data cases.
- For Qt tests, run under the offscreen platform and skip gracefully when
  PySide6 is unavailable, matching existing patterns in `tests/test_qt_adapters.py`.
- Patch `qt_message_service` modal functions in panel tests so tests do not
  block.
- Prefer regression tests for fixed bugs.
- Do not over-mock service/viewmodel logic.

## Useful cases

- Numeric strings, blanks, `N/A`, commas, dashes, and units.
- Grouped Excel-style columns and multiple Y columns.
- Secondary Y-axis selections and analysis-window filtering.
- Limit-line interpolation/margins, FFT, cursor point compare, raw-data edits,
  maths channels, runs comparison, session save/load, and figure export guards.
