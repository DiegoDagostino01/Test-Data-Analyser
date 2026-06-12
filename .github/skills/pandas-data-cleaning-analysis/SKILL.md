---
name: pandas-data-cleaning-analysis
description: "Use when: working on CSV/Excel loading, numeric conversion, raw data filtering/editing, statistics, data quality checks, dataframe export, or run comparison data."
---

# Pandas Data Cleaning Analysis

This project handles engineering test data with pandas and numpy.

## Rules

- Preserve CSV, XLSX, and XLS support.
- For CSV loading, default to UTF-8 with comma delimiter; if parsing yields a
  single column, retry with semicolon delimiter. Surface an encoding error to
  the user rather than silently producing garbled data.
- Use `openpyxl` for `.xlsx` and `xlrd` for `.xls`.
- If `xlrd` is not importable when loading an `.xls` file, raise an
  `ImportError` with the message: `xlrd is required to open .xls files. Install
  it with: pip install xlrd==1.2.0.`
- Prefer shared helpers in `core/data_io.py`, especially `numeric_series`, for
  tolerant numeric conversion.
- If `numeric_series` produces a result where more than 50% of values are
  `NaN`, emit a UI warning identifying the column name and the percentage of
  unparseable values before proceeding.
- Keep numeric conversion tolerant of strings, commas, blanks, dashes, `N/A`,
  and units embedded in text.
- Preserve index alignment between X and Y series.
- Preserve per-series X mapping for grouped Excel-style columns.
- Keep analysis-window filtering consistent across plotting, statistics, raw
  data, requirements/limits, runs comparison, and export.
- All six consumers must derive their filtered frame from a single shared helper
  such as `core/data_io.apply_analysis_window`. Do not reimplement filtering
  inline in any consumer.
- Avoid full-dataframe copies and `pd.concat` inside loops or functions called
  per-row or per-chunk. `pd.concat` is acceptable at load time or when combining
  a fixed number of frames (e.g., merging run results).
- Prefer vectorized operations or scoped caching for large data.
- Do not silently discard data without making the rule explicit in code or UI
  messaging.

## Test cases

- Numeric strings, blanks, `N/A`, commas, dashes, and units.
- Multiple Y columns and secondary-Y selections when the selected columns share
  a numeric dtype and a secondary axis has been explicitly assigned by the user.
- Grouped Excel-style columns and run comparison data.
- Raw data edits, undo, selected-frame export, and analysis-window filtering.
- If an undo is requested with no edit history available, show a UI message
  `Nothing to undo` and take no other action. Do not raise an exception.
