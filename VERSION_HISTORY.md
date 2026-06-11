# Version History

This file records released versions of Test Data Analyser - Eaton Edition. The
code source of truth for the current version is `__version__` in
`test_data_analyser/core/config.py`.

## Versioning policy

Use `MAJOR.MINOR.PATCH`, with two digits for `MINOR` and `PATCH` to match the
current release format.

- Increase `MAJOR` for large releases, breaking workflow changes, or incompatible
  session/data format changes.
- Increase `MINOR` for new user-facing features or meaningful workflow additions
  that remain compatible with existing sessions.
- Increase `PATCH` for bug fixes, documentation updates, tests, small UI polish,
  and compatible maintenance changes.

When releasing an update, change `__version__` and add a new entry at the top of
this file.

## 1.00.00 - 2026-06-11

First release baseline.

- PySide6 / Qt desktop application with Eaton branding.
- CSV, XLSX, and XLS data loading with tolerant numeric conversion.
- X-axis selection, primary Y-axis channels, secondary Y-axis channels, channel
  grouping, plot options, and Matplotlib figure export.
- Multiple plot profiles with per-plot labels, limits, ticks, legend state,
  generated state, and session restore.
- Statistics, Raw Data editing/export, Maths Channels, Requirements/Limits with
  margin summaries, Engineering Notes, Runs / Comparison, and Point Compare.
- Analysis session save/load with source-file and run relinking support.
- Light/dark theme settings, remembered data/session folders, and configurable
  axis padding/statistics formatting.
- Guided Help window with workflow, ribbon, plot-control, run-management,
  troubleshooting, and About content.