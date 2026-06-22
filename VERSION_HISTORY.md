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

## 1.02.00 - 2026-06-22

Manual Raw Data Session Mode and a source-agnostic dataset abstraction with
stable channel IDs.

**New Additions**

- Added a **Create Session** command (File ribbon and `Ctrl+N`) that starts a
  blank manual data session with no linked Excel file. The existing **Open
  Data** command is renamed to **Open Excel**.
- Added a source-agnostic dataset layer: a `ChannelRegistry` of `ColumnSpec`
  entries gives every data column a stable internal channel ID (`ch_001`) that
  is independent of its display name, so a header can be renamed without
  breaking plots, Maths Channels, limits, or saved sessions.
- Added full-dataset editing to the Raw Data tab (an **Edit dataset** toggle):
  add, rename, and delete columns; add and delete rows; and edit cells, in both
  Excel and manual sessions. Edits affect the current session only and never
  modify the original Excel file.
- Added automatic numeric/text column detection. Plot X/Y selectors now offer
  only numeric-compatible channels; text columns remain visible in the Raw Data
  table.
- Added duplicate-header protection with a clear message, and graceful warnings
  when a deleted column is still used by a plot or a Maths Channel.
- Added manual datasets to the session file: a manual session embeds its column
  registry and row values and reloads with no Excel file required, while Excel
  sessions persist the registry and reconcile channel IDs by name on reload.

**Compatibility**

- Existing name-based sessions still load: a channel registry is rebuilt from
  the refreshed data and the saved name references are migrated to stable IDs.

## 1.01.02 - 2026-06-17

Session path persistence, live source-data restore, Maths Channel builder, plot
defaults, and small UI polish.

**New Additions**

- Added `root_file_directory` to analysis sessions so a relinked or changed
  source-data folder is saved with the active session and reused on the next
  Load Session. Existing sessions without the key still load by deriving the
  root from `file_path` where possible.
- Added restore warnings when saved plot profiles reference X/Y channels that
  are no longer present in the refreshed source data, without failing the load.
- Added plot annotations for text boxes, arrows, and boxes using data-coordinate
  Matplotlib artists so visible annotations are saved with plot profiles and
  included in PNG exports.
- Added Maths Channel formula-builder buttons for arithmetic operators,
  `sqrt()`, square, power, reciprocal, and brackets while keeping the existing
  restricted-AST formula engine as the only calculation path.

**Fixes and Improvements**

- Updated Load Session to use the saved root directory plus source filename,
  reload the linked CSV/XLSX/XLS file from disk, and keep session files focused
  on configuration rather than cached raw data.
- Recalculate Maths Channels from the refreshed source dataframe during session
  restore, so changed Excel values flow through derived channels, plots, raw
  data, statistics, and channel lists.
- Preserved the currently selected X-axis when creating new plot tabs, falling
  back to the suggested/default X column only when the remembered channel is no
  longer available.
- Fixed PNG export legend generation so hidden legend/channel entries are not
  reintroduced into the exported image legend.
- Improved Maths Channel validation feedback with an in-panel status message and
  retained manual formula entry plus safe channel insertion for names requiring
  quoting.
- Expanded the Requirements / Limits X/Y point table into spare vertical space
  so larger point sets are easier to review in a maximised Limits tab.

**Others**

- Added regression coverage for session root persistence, live Excel reload,
  missing-channel warnings, X-axis preservation for new plots, plot annotation
  persistence/export rendering, Maths Channel formula-builder behavior, and the
  Limits point-table layout.

## 1.01.01 - 2026-06-15

Startup, workbook navigation, plot preservation, and best-fit update.

**New Additions**

- Added right-side Legend panel Hide / Show checkboxes for plotted Y-axis
  channels without changing each channel's colour, line style, marker style, or
  display-name settings.
- Added an `Edit Axis` Best Fits tab for up to five plotted Y-axis channels,
  supporting linear, squared, and polynomial fits with selectable polynomial
  order.
- Added the Analysis ribbon's Best Fit Formulas panel so generated fit equations
  can be reviewed without drawing the formulas on top of the plot.

**Fixes and Improvements**

- Improved source startup by lazy-loading SciPy filtering and Matplotlib colour
  cycle imports until those features are actually needed.
- Made Excel sheet-name discovery lighter by reading workbook metadata directly
  instead of creating a pandas `ExcelFile` for the sheet list.
- Preserved plot profiles, generated plot snapshots, Requirements / Limits, and
  Engineering Notes when switching sheets in a multi-sheet Excel workbook.
- Kept generated plots available across sheet changes and plot-tab switches even
  when the active sheet does not contain the original plotted columns.
- Persisted best-fit line settings and per-channel legend visibility in plot
  profiles and sessions.
- Reused already loaded dataframes during session restore when saved runs point
  at the same workbook and sheet as the main session data.

**Others**

- Updated Help, architecture notes, and regression coverage for the new workbook
  navigation, legend visibility, best-fit, session-restore, and startup paths.

## 1.01.00 - 2026-06-12

Plot styling, limits review, and channel-ordering update.

**New Additions**

- Added direct legend-row editing for plotted channels, including display name,
  colour, plot type, line style, draw style, line width, marker style, marker
  size, marker face colour, and marker edge colour.

**Fixes and Improvements**

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

**Others**

- Added regression coverage for legend styling, plot appearance preservation,
  margin summary behaviour, grouped channel ordering, and naturally sorted
  channel outputs.

## 1.00.01 - 2026-06-11

Icon and packaging polish update.

**New Additions**

- Added the new Test Data Analyser application icon asset.

**Fixes and Improvements**

- Set the icon for the running PySide6 / Qt application window.

**Others**

- Rebuilt the Windows executable bundle so `Test Data Analyser.exe` uses the new
  icon.
- Kept the launch folder structure tidy for new users.

## 1.00.00 - 2026-06-11

First release baseline.

**New Additions**

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