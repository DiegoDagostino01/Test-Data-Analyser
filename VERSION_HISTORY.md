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

## 1.01.00 - 2026-06-12

Plot styling, limits review, and channel-ordering update.

- Added direct legend-row editing for plotted channels, including display name,
  colour, plot type, line style, draw style, line width, marker style, marker
  size, marker face colour, and marker edge colour.
- Persisted per-channel legend styling in plot profiles and sessions, while
  keeping recurring channels on the same colour across plots.
- Moved curve styling out of Matplotlib Figure Options and into the Legend tab
  channel editor, making the Figure Options Curves tab redundant.
- Improved Generate Plot so plot-kind-only changes and similar channel additions
  preserve manual axis labels, limits, and tick settings, while materially
  different plot selections reset axis/tick appearance.
- Improved Requirements / Limits margin calculations with interpolated limit
  evaluation, channel-specific X data, first-failure reporting, data-value-based
  margin percentage, and WARN severity for PASS results within 5% margin.
- Replaced the margin-to-limit text summary with a structured table containing
  PASS/WARN/FAIL status cells, margin values, worst point, first failure point,
  and detailed messages.
- Standardised user-facing channel ordering with natural sorting, including axis
  selection, Maths Channels, Limits applies-to options, Statistics, Raw Data,
  Point Compare, Runs / Comparison, and margin summary rows.
- Added regression coverage for legend styling, plot appearance preservation,
  margin summary behaviour, grouped channel ordering, and naturally sorted
  channel outputs.

## 1.00.01 - 2026-06-11

Icon and packaging polish update.

- Added the new Test Data Analyser application icon asset.
- Set the icon for the running PySide6 / Qt application window.
- Rebuilt the Windows executable bundle so `Test Data Analyser.exe` uses the new
  icon.
- Kept the launch folder structure tidy for new users.

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