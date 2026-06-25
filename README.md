# Test Data Analyser — Eaton Edition

A **PySide6 / Qt** desktop application for loading engineering test data
(CSV/XLSX/XLS), plotting it, and analysing it: statistics, requirement/limit
margins, multi-run comparison, cursor point comparison, maths (calculated)
channels, and structured engineering notes — with full analysis-session
save/load.

The application is built on a **framework-independent core** (domain models,
services, and viewmodels that import no UI toolkit) with a thin Qt UI on top, so
the engineering logic is unit-testable without a GUI. See
[ARCHITECTURE.md](ARCHITECTURE.md) for the layered design and
[VERSION_HISTORY.md](VERSION_HISTORY.md) for release history.

## Running the app

From the project root, run the entry-point script:

```bash
python run_qt_app.py
```

You can also run the package directly:

```bash
python -m test_data_analyser
```

or the Qt entry module:

```bash
python -m test_data_analyser.qt_app.main_qt
```

> **Note:** Do **not** run a module inside the package directly (e.g.
> `test_data_analyser/qt_app/main_window.py`). The package uses relative imports
> that only resolve when the code is imported as part of the `test_data_analyser`
> package. Always launch via `run_qt_app.py` or `python -m test_data_analyser`.

## Opening files

Open data with **Open Excel** (`Ctrl+O`) or start a blank manual session with
**Create Session** (`Ctrl+N`). The **File** ribbon's **Recent** menu lists the
most recently opened data files and sessions, and you can drag a `.csv`,
`.xlsx`, `.xls`, or `.json` session file onto the window to open it. When
**auto-save** is enabled in Settings, the active session is saved automatically
at the configured interval while there are unsaved changes (falling back to an
`autosave.json` beside the data file).

## Requirements

Install dependencies with:

```bash
pip install -r requirements.txt
```

PySide6 must be installed in the interpreter you launch with; the headless tests
run without it (the Qt tests skip automatically when PySide6 is absent).

## User settings

Application settings are stored in `config/settings.json`. If an older checkout
still has `settings.json` in the repository root, the app migrates it into the
`config/` folder on startup.

## Tests

All tests are framework-independent and run headless — no visible GUI is
required. They cover the domain models, the service layer, the viewmodels
(statistics, limit margins, maths-channel formulas, plot-data windowing,
raw-data filtering/editing, run comparison, cursor compare, settings, and
session save/restore), and the Qt panels/adapters under the offscreen platform:

```bash
python -m unittest discover -s tests
```

Qt panel/adapter tests (`tests/test_qt_adapters.py`) run under the Qt offscreen
platform and are skipped automatically if PySide6 is not installed.

## Runs / Comparison

The **Runs / Comparison** tab lets you load multiple CSV/XLSX/XLS test runs and
overlay the enabled ones on a single plot. Use **Add Run…** to load each file
(you are prompted for a sheet on multi-sheet workbooks), or **Batch Import…** to
import every matching data file in a folder at once (semicolon-separated globs,
optional subfolder recursion, and an optional regex to derive each run name from
its filename). Then use **Set Active**, **Rename**, **Duplicate**, **Remove**, or
**Toggle Enabled** (double-clicking a row also toggles it). Click **Generate
Comparison Plot** to overlay the selected Y channels for every enabled run on the
shared plot canvas.

**Prefix legend labels with run name** renders legend entries as
`Run Name | Channel`, and **Use common X range only** restricts plotting to the
overlapping X range shared by the enabled runs that contain the selected X
column. A comparison-statistics table summarises each enabled run/channel.

Session save/load stores run references, sheet names, enabled states, colours,
and comparison settings — not full dataframe copies; runs are reloaded from their
original files when the session is opened.

## Editable Raw Data

The **Raw Data** tab supports spreadsheet-style editing of visible cells: select
a cell and type a numeric value directly, or double-click to edit. Press
**Enter** to commit the edit and move to the next row in the same column; press
**Esc** to cancel. Use **Undo Edit** to restore the most recent Raw Data or
dataset edit.

Tick **Edit dataset** to work with the full dataset. In this mode, double-click
a column header to rename it, use the blue **+** header at the far right to add
a column, and use the blue **+** row header below the final row to add a row.
Right-click selected row or column headers to delete them; selecting multiple
column headers and choosing delete removes every selected column in one action.
Column widths expand to fit header titles, while the **+** controls stay compact.

Edits update the in-memory dataframe used by statistics, plotting, raw data
export, and other analysis views. The original CSV/Excel file is not
modified automatically; export the selected data if you need a saved copy.

The Raw Data view also supports power-user workflows. Click a column header to
sort the displayed rows (ascending, then descending, then unsorted; text channels
use natural order), and toggle **Filter** for a per-column filter row that accepts
substrings or numeric expressions (`>n`, `<n`, `>=n`, `<=n`, `a..b`, `=n`). Sort
and filter are display-only and never change the underlying data. Copy, cut, and
paste rectangular cell ranges with **Ctrl+C** / **Ctrl+X** / **Ctrl+V**
(Excel-compatible; paste auto-grows the dataset and coerces values to each
column's type). **Ctrl+F** finds and **Ctrl+H** finds-and-replaces across the
view or the full dataset, and a right-click **Fill Down** copies the top selected
row down a range. Copy works in either mode; cut, paste, and fill require
**Edit dataset** mode and each counts as a single undo step.

## Maths Channels

Maths Channels let you create derived dataframe columns inside the app, then use
them like normal channels for X/Y selection, secondary Y plotting, statistics,
raw data views/exports, and requirement/limit comparisons.

Open **Maths Channels**, enter a channel name, then build a formula with the
column insertion dropdown, the formula-builder buttons (`+`, `-`, `*`, `/`,
`sqrt()`, square, power, reciprocal, and brackets), or direct manual editing.
Column insertion writes safe formula references for channel names with spaces or
symbols. Click **Validate Formula** to check the generated text against the
existing formula engine, then click **Apply / Save Channel**. Example formulas:

```text
`Outlet Pressure` - `Inlet Pressure`
`Voltage` * `Current`
rolling_mean(`Current`, 25)
sqrt(abs(`Signal A`))
clip(`Pressure`, 0, 500)
```

Calculated channel definitions are saved in analysis sessions and recalculated
from the refreshed source data when a session is loaded. Channel lists are
sorted naturally throughout the app, so numbered names such as `TC2` and `TC10`
appear in engineering-friendly order; where channel groups are shown, the group
order is preserved and each group is sorted internally.

## Plot options

The axis panel drives the primary plot canvas. Pick the X column and tick the Y
channels; use the **channel group** filter to narrow long channel lists by
engineering type (temperature, pressure, voltage, and so on). Tick channels in
the **secondary Y-axis** list to plot them against a right-hand axis (drawn on a
Matplotlib `twinx` with an offset colour cycle and a merged legend). Choose the
**plot kind** (Line, Scatter, or Line + Markers), optionally constrain the
**analysis window** (X min/max), and enable the **low-pass filter** (cutoff Hz +
order) to apply a zero-phase Butterworth filter per channel. Channels that recur
across plots keep a stable colour.

The right-side **Legend** panel also edits plotted channel styling directly:
click a legend row to change the display name, colour, plot type, line style,
draw style, line width, marker style, marker size, marker face colour, and
marker edge colour. These per-channel overrides are saved with plot profiles and
analysis sessions, and channel colour overrides carry across matching channels
on other plots.

Use the toolbar's **Figure Options** to fine-tune the plot: edit axis titles and
limits with **auto-label** / **auto-fit** helpers, **Reset Axis** to clear the
active plot's manual title/labels/limits/ticks and re-render with auto defaults,
set per-axis major-tick spacing (and optionally align the secondary-Y grid to the
primary), and switch the legend between the right-side **Legend** panel and an
in-graph Matplotlib legend. Curve styling is handled by the Legend panel channel
editor rather than the Figure Options dialog. Configurable axis padding (Settings
> Axis Padding) keeps a margin around auto-fitted data, and saved figure exports
include the legend.

Use the **Annotations** controls in the plot toolbar to select, add text boxes,
draw arrows, or draw boxes directly on the active plot. Right-click the plot and
choose **Mark Peaks…** to detect peaks (and optionally troughs) for a plotted
channel with a prominence control, which drops a text annotation at each.
Annotations are stored with the plot tab in data coordinates, can be
moved/edited/deleted, and are included in saved PNG exports.

Use the **+** tab beside the plot tabs above the canvas to create additional
plots. New plot tabs inherit the currently selected X-axis when that channel is
still available, falling back to the suggested/default X column only when
needed. Drag a plot tab to reorder it (the trailing **+** tab stays last). Each
plot tab keeps its own X-axis selection, Y-axis selections, plot title, axis
labels, limits, ticks, legend mode, legend channel overrides, notes,
annotations, and requirement overlays.
Right-click a plot tab to duplicate, rename, or delete it; all plot tabs are
saved and restored with analysis sessions. Re-generating a plot preserves manual
axis labels, limits, and tick spacing for plot-kind changes or similar channel
additions, and resets that appearance when the selected data changes
materially.

## Requirements / Limits

The **Requirements / Limits** tab manages requirement limit lines. Add lines
(Upper Limit, Lower Limit, or Reference Line), give each a colour (preset, hex,
or colour-picker), set which channels it applies to, and add X/Y points (two or
more per line). Limit lines are drawn as dashed/dotted overlays on the plot, and
the **margin-to-limit summary** table reports each channel's PASS/WARN/FAIL
status, margin, margin percentage, worst point, first failure point, and detail
message against the active selection. Limit margins are evaluated by
interpolating the limit line over the channel's X data, and a PASS within 5%
margin is highlighted as WARN. The X/Y point table expands vertically when the
Limits tab has spare space, making larger point sets easier to review. Use
**Save Template…** / **Load Template…** to store the current limit lines as a
JSON template and reload them into another session (choosing replace or merge).

## Engineering Notes

The **Engineering Notes** tab captures structured notes across nine fields
(objective, test article, conditions, observations, rationale, anomalies,
comparison, actions, and report summary) and compiles them into a report/email
preview that includes the current file and axis selection. Notes are saved with
the analysis session.

## Point Compare

Enable **Point Compare mode** on the **Point Compare** tab, then click the plot
to lock comparison points. The table lists each locked point and the delta
versus Point 1; press **Esc** on the plot (or **Clear Points**) to remove them.
**Use P1–P2 as Analysis Window** pushes the first two locked X positions back
into the analysis-window fields.

## Analysis sessions

The **File** ribbon's **Save Session** command writes the current file
reference, root file directory, axis selection, plot profiles,
calculated-channel definitions, limit lines, engineering notes, legend channel
overrides, plot annotations, and run/comparison settings to a JSON file.
**Load Session** restores the configuration, reloads the current source
CSV/XLSX/XLS data from disk, reloads comparison runs from their saved paths,
recalculates Maths Channels, and re-applies the selection across every panel.
If a refreshed data file no longer
contains a saved plot channel, the session still loads and reports the missing
reference clearly.
Saved sessions remain compatible with the earlier on-disk format; older session
files without `root_file_directory` are normalised on load.

## Architecture

The application is organised into strict layers; the dependency direction only
ever points downward, and only `qt_app/` imports PySide6:

```
qt_app/      PySide6 UI: main window, panels, theme, Qt adapters
   │
viewmodels/  UI-independent coordinators (return OperationResult)
   │
services/    pure engineering/data logic (no UI toolkit)
   │
domain/      framework-independent dataclasses (no UI toolkit)
   │
core/        shared infrastructure (config, data I/O, filters, settings, focused helpers)
```

| Package / module | Responsibility |
| --- | --- |
| `core/` | Shared infrastructure: `config.py` (Eaton brand colours, version, domain keyword config, theme palettes), `data_io.py` (file/sheet loading, numeric coercion), `filters.py` (sampling-rate estimate, low-pass filter), `settings_manager.py` (persisted settings), focused helper modules for naming, indexing, grouped-column matching, and engineering channel classification, plus `utils.py` as a compatibility facade. |
| `domain/` | Framework-independent dataclasses (plot/profile/session state, requirement limits, engineering notes, runs, calculated channels) with JSON-compatible `from_dict`/`to_dict`. Import directly, e.g. `from test_data_analyser.domain import PlotData`. |
| `services/` | Pure engineering/data logic (statistics, limits, maths channels, plotting data, plot-render colours, raw data, run comparison, cursor compare, settings, session). No UI imports; returns values or `OperationResult`. |
| `viewmodels/` | UI-independent coordinators over `AppState` (data-loading, plot-workspace, raw-data, maths-channels, runs-comparison, limits, engineering-notes, cursor-compare, settings, and the aggregating main-window VM). Return `OperationResult`; never open dialogs or import Qt. |
| `qt_app/` | The only place PySide6 is imported. `main_qt.py` entry point, `main_window.py`, Eaton `theme.py`, `widgets/` (the migrated panels), and `adapters/` (pandas table model, Matplotlib Qt canvas with the legend-aware toolbar, file dialogs, message service, widget/directory helpers). |

### Project structure

```
test_data_analyser/
├─ __init__.py  __main__.py     # package marker + `python -m` entry point
├─ core/        config.py  data_io.py  filters.py  settings_manager.py
│               naming.py  indexing.py  column_matching.py
│               channel_classification.py  utils.py
├─ domain/      conversions.py  models.py  settings.py  engineering_notes.py
│               limits.py  plot_profile.py  run_model.py  session.py
├─ services/    statistics_service.py  limits_service.py  maths_channel_service.py
│               plotting_data_service.py  plot_render_service.py  raw_data_service.py
│               run_comparison_service.py  cursor_service.py
│               settings_service.py  session_service.py  results.py
├─ viewmodels/  app_state.py  main_window_vm.py  data_loading_vm.py
│               plot_workspace_vm.py  raw_data_vm.py  maths_channels_vm.py
│               runs_comparison_vm.py  limits_vm.py  settings_vm.py
│               engineering_notes_vm.py  cursor_compare_vm.py
└─ qt_app/      main_qt.py  main_window.py  theme.py
                widgets/   (data file, axis selection, plot workspace, statistics,
                            raw data, maths channels, limits, engineering notes,
                            runs comparison, cursor compare, settings dialog,
                            no-wheel combo box)
                adapters/  (pandas table model, matplotlib canvas, file dialogs,
                            message service, editable raw-data model, widget helpers)
```

See [ARCHITECTURE.md](ARCHITECTURE.md) for the full layered design and rationale.
