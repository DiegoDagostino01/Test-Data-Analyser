---
name: pandas-data-cleaning-analysis
description: "Use when: working on CSV/Excel loading, numeric conversion, raw data filtering/editing, statistics, data quality checks, dataframe export, or run comparison data."
---

# Pandas Data Cleaning Analysis

This project handles engineering test data with pandas and numpy.

## Rules

- Preserve CSV, XLSX, and XLS support.
- Use `openpyxl` for `.xlsx` and `xlrd` for `.xls`.
- Prefer shared helpers in `core/data_io.py`, especially `numeric_series`, for
  tolerant numeric conversion.
- Keep numeric conversion tolerant of strings, commas, blanks, dashes, `N/A`,
  and units embedded in text.
- Preserve index alignment between X and Y series.
- Preserve per-series X mapping for grouped Excel-style columns.
- Keep analysis-window filtering consistent across plotting, statistics, raw
  data, requirements/limits, runs comparison, and export.
- Avoid unnecessary full-dataframe copies and avoid `pd.concat` in hot paths
  unless justified.
- Prefer vectorized operations or scoped caching for large data.
- Do not silently discard data without making the rule explicit in code or UI
  messaging.

## Test cases

- Numeric strings, blanks, `N/A`, commas, dashes, and units.
- Multiple Y columns and secondary-Y selections where pure logic allows.
- Grouped Excel-style columns and run comparison data.
- Raw data edits, undo, selected-frame export, and analysis-window filtering.
