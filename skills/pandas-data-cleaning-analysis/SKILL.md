---
name: pandas-data-cleaning-analysis
description: Use this when working on CSV/Excel loading, numeric conversion, raw data filtering, statistics, data quality checks, or export.
---

# Pandas Data Cleaning Analysis

This project handles engineering test data using **pandas** and **numpy**.

## Rules

- Preserve CSV, XLSX, and XLS support.
- Use `openpyxl` for `.xlsx` and `xlrd` for `.xls`.
- Keep numeric conversion tolerant of:
  - strings
  - commas
  - blanks
  - dashes
  - `N/A`
  - units embedded in text
- Avoid unnecessary full-dataframe copies.
- Avoid `pd.concat` in hot paths unless justified.
- Preserve index alignment between X and Y series.
- Preserve per-series X mapping for grouped Excel files.
- Keep analysis-window filtering consistent across:
  - plotting
  - raw data
  - statistics
  - export
- When improving efficiency, prefer caching or vectorized operations.
- Do not silently discard data without making the rule clear.
