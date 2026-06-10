---
name: pytest-test-writer
description: Use this when creating or updating pytest tests for pure Python functions, data processing, plotting helpers, or refactored modules.
---

# Pytest Test Writer

Write practical pytest tests for this Python project.

## Rules

- Prioritize pure functions first.
- Avoid requiring the Tkinter GUI unless necessary.
- Use small pandas DataFrames as fixtures.
- Test realistic engineering data cases:
  - numeric strings
  - blanks
  - `N/A` values
  - comma-separated numbers
  - grouped Excel-style columns
  - multiple Y columns
  - secondary Y-axis selections where pure logic allows
  - analysis-window filtering
  - limit-line interpolation/margins
- Keep tests readable and maintainable.
- Prefer regression tests for bugs that were fixed.
- Do not over-mock unless necessary.
