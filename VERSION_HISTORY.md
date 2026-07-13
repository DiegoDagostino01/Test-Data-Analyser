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

## 1.03.00 - In-Work

Full-system optimization and reliability pass started from the released
1.02.02 baseline.

**Performance**

- Replaced full-dataframe undo snapshots for individual **Edit dataset** cell
  edits and single-cell Find/Replace operations with compact cell-level undo
  records. Structural and block edits continue to use full snapshots so their
  wider state changes remain reversible.

**Workspace modernization**

- Added the V1.03 dockable workspace using Qt Advanced Docking System, with
  stable singleton panel IDs, floating/tabbed panels, auto-hide, built-in
  Analysis/Comparison/Reporting/Data Editing layouts, one Custom layout,
  restart persistence, and missing-monitor recovery.
- Made the complete Plot Workspace detachable while preserving one
  authoritative plot-profile tab bar, Matplotlib canvas, annotation/cursor
  wiring, and export path. Closing the floating Plot Workspace returns the same
  widget to the main window.
- Moved mutable settings and workspace geometry to per-user Local AppData with
  copy-first migration from existing repository settings. Workspace state stays
  separate from analysis sessions and plot profiles.
- Reworked Plot Controls into a dockable Plot Navigator with collapsible Axes,
  Channels, Plot Type, Analysis Window, and Filter sections; added keyboard
  channel toggling and fast name/classification search that preserves hidden
  primary/secondary selections and natural group order.
- Modernized the docked Legend with name and classification filters, accessible
  visibility toggles, an explicit style shortcut, and a direct colour shortcut.
  Legend filtering remains panel-only, preserving profile and figure-export
  behavior.
- Centralized application commands behind stable IDs and shared Qt actions;
  added the `Ctrl+Shift+P` command palette for actions, panels, and workspace
  layouts, including disabled-command reasons and keyboard execution.
- Replaced the five legacy ribbon groups with Home, Data, Plot, Analysis,
  Requirements, Reporting, and Settings groups rendered by `RibbonManager`,
  while preserving existing shortcuts and Recent menu behavior.
- Added durable status indicators for plot currency, saved/unsaved analysis
  state, recovery auto-save, and the active workspace. Recovery auto-save
  remains recovery-only and never clears the Unsaved state.
- Added the no-data Dashboard with shared commands, recent data/session lists,
  startup behavior, and a bounded recovery lifecycle that never silently
  deletes stale or dismissed recovery files.
- Added persisted Basic and Advanced modes. Basic masks advanced commands and
  panels without changing engineering state; Advanced restores the unmasked
  workspace arrangement and protects the Custom layout.
- Added keyboard focus treatment, accessible status names, polite screen-reader
  announcements, and automated 125%/150%/200% light/dark scaling checks.
- Increased the on-screen Matplotlib canvas base resolution from 100 to 150 DPI
  while retaining independently configured export DPI.
- Added a sanitized PyInstaller `onedir` release pipeline with ADS notices and
  license, artifact path/state scanning, shortcut creation, and packaged startup
  smoke testing. Mutable settings remain exclusively in Local AppData.
- Removed the obsolete repository `config/settings.json` template. New installs
  create Local AppData defaults directly; the historical root `settings.json`
  migration remains available for older source deployments.

**Fixes**

- Made Maths Channel recalculation follow dependency order, so dependent
  channels restore correctly regardless of definition order, and reject
  circular dependencies before changing the dataset.
- Made Maths Channel renames preserve dependent formulas, plot selections,
  best-fit settings, legend overrides, Requirements / Limits references, and
  live primary/secondary axis selections.
- Hardened saved major-tick handling so zero, negative, non-finite, or invalid
  values fall back to automatic ticks instead of reaching Matplotlib.
- Fixed ribbon groups hiding all commands during initial construction.
- Fixed panel commands opening behind another ADS tab; Raw Data now becomes the
  current tab and refreshes its selected frame when opened.

**Tests**

- Added regression coverage for compact single-cell undo, dependency-ordered
  Maths Channel recalculation, circular dependency rejection, rename reference
  propagation, invalid major-tick values, live Qt axis-selection remapping,
  dashboard/mode behavior, accessibility metadata, display scaling, release
  sanitization, ribbon visibility, ADS tab selection, Raw Data display, and plot
  display resolution.

## 1.02.02 - 2026-07-13

Large-file performance update: faster loading, plotting, and axis auto-fit for
multi-million-row CSV captures, plus a plot-tab axis-limit persistence fix,
an unsaved-changes prompt on exit, and Raw Data editing productivity additions.

**Performance**

- Sped up loading large `.csv` files by sniffing the delimiter so the fast C
  parser is used instead of the slower Python parser, and by detecting the first
  numeric data row so a leading units row (for example `(ms),(A),(V)` beneath the
  header) no longer forces the numeric columns to load as text. On a ~345 MB,
  9.6-million-row oscilloscope capture this cut load time from about 30 s to
  about 4 s; the units row is now treated as header metadata and no longer
  appears as a Raw Data row, matching how grouped Excel headers are handled.
- Cached the tolerant text-to-number conversion per column, scoped to the loaded
  dataframe and refreshed after edits, so generating a plot and its statistics no
  longer repeats the same expensive full-column coercion several times. Combined
  with the loading change, a first plot of the large capture dropped from roughly
  two minutes to a few seconds.
- Vectorised the Figure Options **Auto-fit X / Y / Secondary Y** range
  calculation using NumPy reductions instead of a per-point Python loop, making
  auto-fit effectively instant on multi-million-point plots (about 7 s to under
  0.1 s per axis on the large capture) while producing identical axis limits.
- Made **Edit dataset** mode load a sliding 1,000-row window for very large
  datasets instead of binding millions of rows to the live editable table, which
  could make the whole app sluggish for several seconds. The window auto-advances
  as you scroll to its top or bottom, a **Go to row** box jumps anywhere in the
  dataset, and the status bar shows the loaded row range. Smaller datasets remain
  fully editable in a single view.

**Fixes**

- Fixed manual axis limits resetting when switching between plot tabs (or
  returning to a tab after loading a session). Adjusting a tab's axes and then
  leaving and coming back no longer reverts to the original limits; live axis
  edits are now kept when the plot was restored from its cached snapshot.
- Added a failsafe so a major tick step too small for the axis range (for
  example 2 on a 0-90000 flow-rate axis) no longer crashes plotting with a
  Matplotlib MAXTICKS error; the oversize step is ignored and automatic ticks
  are kept.
- Fixed the spin box up/down arrows (for example the Best Fits **Order** field
  and Settings number boxes) rendering as blank or flat lines. The theme now
  draws clear **+** / **-** step buttons that follow the active theme colour.

**Raw Data**

- Added **Ctrl+Z** as an Undo shortcut for the Raw Data table, mirroring the
  existing **Undo Edit** button for cell edits, row/column changes, renames, and
  reorders.
- Made dataset columns drag-reorderable in **Edit dataset** mode: drag a column
  header left or right to reorder it across the dataframe and channel registry,
  with the move captured as a single undo step.

**Sessions**

- Added an unsaved-changes prompt when closing the app. If changes have been
  made since the last save, a dialog offers **Save**, **Don't Save**, or
  **Cancel**; choosing Save and then cancelling the file dialog keeps the app
  open so work is not lost.
- Made unsaved-change detection reliable: plot edits (channels, axis, labels,
  limits, plot kind, profile add/rename/delete/reorder, legend), normal Raw Data
  cell edits, Maths Channels, Runs/Comparison, Engineering Notes, and
  Requirements/Limits now all mark the session unsaved, and pending Figure
  Options/panel edits are folded in on close so the prompt is not missed.
- Made auto-save recovery-only: a background auto-save (including the
  `autosave.json` fallback before you have saved a session) no longer clears the
  unsaved state, so the close prompt still appears for changes not written to
  your chosen session file.

**Tests**

- Added regression tests for fast CSV loading (delimiter sniffing, units-row
  skipping, text-only tables), the cached numeric coercion and its invalidation
  after edits, the vectorised auto-fit range calculation, and the Edit dataset
  sliding-window loading, row mapping, and Go-to-row navigation.
- Added a regression test confirming manual axis-limit edits persist when
  switching away from and back to a snapshot-restored plot tab.
- Added regression tests for dataset column reordering (service, viewmodel undo)
  and for the Raw Data movable columns and Undo shortcut.
- Added a regression test confirming a tick step too small for the axis range is
  ignored instead of exceeding the Matplotlib tick limit.
- Added a regression test confirming the theme styles spin box step buttons and
  arrows.
- Added regression tests for the unsaved-changes close prompt (Save, Don't Save,
  Cancel, save-cancelled, and no-prompt-when-clean paths).
- Added regression tests for unsaved-change tracking (Raw Data edits, Maths
  Channels, Runs, plot-profile capture/CRUD), recovery-only auto-save keeping the
  unsaved flag, and the close prompt firing after edits without false positives.

## 1.02.01 - 2026-06-23

Performance, Raw Data usability, productivity, architecture refactor, packaging,
and layout maintenance update.

**Fixes and Improvements**

- Improved `.xlsx` workbook opening by reading sheet names from workbook
  metadata and using a direct XML fast path for standard numeric worksheets,
  with fallback to `openpyxl` for date-formatted or unusual workbook features.
- Preserved numeric dtypes during fast `.xlsx` loading so channel-registry type
  detection no longer repeats expensive full-column numeric coercion for native
  numeric data.
- Fixed left rail resizing for workbooks with long engineering channel names:
  the axis controls, sheet selector, and loaded-file label now shrink cleanly,
  and the left rail can expand wider when needed before capping at a practical
  maximum.
- Improved Raw Data table editing: selected cells accept direct typed numeric
  entry, Enter commits and moves down, active editors have more vertical space,
  and **Undo Edit** now restores recent Raw Data and dataset edits.
- Updated Raw Data full-dataset editing controls: double-click column headers to
  rename them, use blue header **+** controls to add columns or rows, and use
  right-click context menus to delete selected rows or one or more selected
  columns. Data columns now expand to fit header titles while the **+** controls
  remain compact.
- Deferred optional Help and Settings dialog imports until those dialogs are
  opened, and kept Matplotlib editor integration behind lazy-compatible access
  points.
- Trimmed unused runtime dependencies and PyInstaller hidden imports that are no
  longer referenced by the app source.
- Consolidated small shared helpers for defensive float conversion, active-index
  clamping, limit-point handling, legend override propagation, and plot-profile
  capture to reduce duplication without changing workflows.
- Added architecture boundary tests that verify PySide6 remains isolated to
  `qt_app/` and internal imports continue to follow the documented layer order.
- Moved plot-profile CRUD, legend override handling, plot-profile capture,
  column-reference propagation, and session assembly into framework-independent
  services so viewmodels remain thinner coordinators.
- Split `core/utils.py` into focused helper modules for naming, indexing,
  grouped-column matching, and channel classification, while keeping `utils.py`
  as a compatibility facade for older imports.
- Added strict validation for newly written session payloads while preserving
  tolerant legacy session/profile loading.
- Added `AppStateController` as the viewmodel-layer mutation boundary for
  dataset undo snapshots, dataframe updates, dirty-state marking, and plot
  profile state replacement.
- Added an internal plot colour-cycle registry so future palettes can be
  registered without adding branching to the plot colour resolver.
- Removed obsolete archived migration/reference notes from `Archive/` and
  refreshed active architecture/README documentation to match the current
  source tree.

**Productivity and workflow**

- Added a **Recent** drop-down to the File ribbon listing up to ten most-recent
  data files and sessions (most recent first); entries whose file no longer
  exists are shown disabled rather than removed. Backed by a new `recent`
  settings section and recent-list helpers on `MainWindowViewModel`.
- Added drag-and-drop opening: dropping a `.csv`, `.xlsx`, `.xls`, or `.json`
  session file onto the window loads it (the first supported file is used).
- Added a public data-file panel load-by-path entry point and ribbon menu-button
  support so recent files, drag-and-drop, and future batch import share one load
  path and a consistent ribbon affordance.
- Added a **Keyboard Shortcuts** Help topic covering file, Raw Data, and editing
  shortcuts.
- Wired **auto-save**: when enabled in Settings, a background poll saves the
  session at the configured interval while there are unsaved changes, writing to
  the active session path or an `autosave.json` fallback beside the data file,
  reporting only on the status bar with no modal interruption.
- Added Raw Data display **sorting** and per-column **filtering**: click a column
  header to cycle ascending -> descending -> unsorted (natural order for text
  channels, with NaN/blank sinking to the bottom), and toggle a per-column filter
  row supporting substring and numeric (`>n`, `<n`, `>=n`, `<=n`, `a..b`, `=n`)
  matches. Both are display-only and preserve the source dataframe index so cell
  edits still map back to the correct row; both are disabled in **Edit dataset**
  mode.
- Added Excel-compatible **copy / cut / paste** for Raw Data cell ranges
  (`Ctrl+C` / `Ctrl+X` / `Ctrl+V`): copy works in either mode, while cut and
  paste require **Edit dataset** mode. Paste auto-expands the dataset with extra
  rows and `Column N` columns when the pasted block runs past the current shape,
  coerces values to each target column's type (keeping non-numeric text with a
  warning), and records the whole paste or cut as a single undo step.
- Added **Find & Replace** for the Raw Data table (`Ctrl+F` / `Ctrl+H`): a
  non-modal dialog with optional regex, case sensitivity, and a full-dataset vs
  displayed-view scope. Searches match each cell's displayed text (so numeric
  values match by their shown form); Replace All applies as a single undo step,
  and replacements into a numeric column keep non-numeric text with a warning
  rather than discarding it.
- Added Excel-style **fill** for the dataset editor: a right-click **Fill Down**
  copies the top selected row down a range, and the fill engine infers a
  constant, linear, or repeat series from the seed cells (text repeats verbatim).
  Each fill is a single undo step.
- Added **batch run import**: a Runs / Comparison **Batch Import…** dialog imports
  every matching data file in a folder as a run (semicolon-separated globs,
  optional recursion, optional regex run-naming), skipping and reporting files
  that fail to load.
- Added **limit templates**: save the current requirement limit lines to a JSON
  template and reload them later, choosing replace or merge.
- Added **peak detection**: right-click the plot and choose **Mark Peaks…** to
  detect peaks (and optionally troughs) for a plotted channel with a prominence
  control, dropping a text annotation at each. Detection uses
  `scipy.signal.find_peaks` behind a lazy import.
- Added **plot tab drag-to-reorder**: drag a plot tab to reorder it (the trailing
  "+" tab stays last) and the active plot follows the move.
- Added a **Reset Axis** button to the plot Figure Options that clears the active
  plot's manual title, labels, axis limits, and ticks and re-renders with
  auto-generated defaults, keeping the plotted data and best-fit settings.

**Compatibility**

- CSV, XLSX, and XLS support is preserved. `.xlsx` export continues to use
  `openpyxl`; `xlsxwriter` is not required by the current export path.
- Existing sessions and plot profiles remain compatible; no session/file-format
  changes were introduced.
- Existing UI-facing `OperationResult` contracts are preserved; result payload
  handling is now centralised through compatibility helpers where refactored.

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
- Updated the in-app Help to document the renamed **Open Excel** command, the
  new **Create Session** manual-session workflow, and full-dataset editing via
  the Raw Data **Edit dataset** mode, including a new **Manual Sessions and
  Dataset Editing** Help topic.

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