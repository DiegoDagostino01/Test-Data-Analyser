# Test Data Analyser

A Tkinter desktop application for loading engineering test data (CSV/XLSX/XLS),
plotting it, and analysing it (statistics, requirement/limit margins, FFT,
cursor point comparison, and structured engineering notes).

## Running the app

From the project root, run the entry-point script:

```bash
python run_app.py
```

You can also run the package directly:

```bash
python -m test_data_analyser
```

> **Note:** Do **not** run `test_data_analyser/gui.py` (or any other module
> inside the package) directly. The package uses relative imports
> (`from .gui_base import ...`), which only resolve when the code is imported as
> part of the `test_data_analyser` package. Running an inner module on its own
> raises `ImportError: attempted relative import with no known parent package`.
> Always launch via `run_app.py` or `python -m test_data_analyser`.

## Requirements

Install dependencies with:

```bash
pip install -r requirements.txt
```

- pandas, numpy, matplotlib, scipy, openpyxl, xlrd

## Runs / Comparison

The **Runs / Comparison** tab lets you load multiple CSV/XLSX/XLS test runs and
overlay enabled runs on one plot. Use **Add Run** to load each file, **Set Active
Run** to choose which run drives the normal X/Y channel controls, and tick
**Overlay enabled runs** before generating a plot.

When overlay mode is on, selected Y channels are plotted for every enabled run.
Legend labels can be prefixed as `Run Name | Channel Name`, and **Use common X
range only** restricts plotting to the overlapping X range shared by enabled
runs that contain the selected X column.

Session save/load stores run references, sheet names, enabled states, colours,
and comparison settings. It does not store full dataframe copies; runs are
reloaded from their original files when the session is opened.

## Editable Raw Data

The **Raw Data** tab supports direct editing of visible cells. Double-click a
cell, type the replacement value, then press **Enter** or move focus away to
apply it. Press **Esc** to cancel the edit. Use **Undo Edit** to restore the
most recent Raw Data edit.

Edits update the in-memory dataframe used by statistics, plotting, raw data
export, and other analysis views. The original CSV/Excel file is not
modified automatically; export the selected data if you need a saved copy.

## Maths Channels

Maths Channels let you create derived dataframe columns inside the app, then use
them like normal channels for X/Y selection, secondary Y plotting, statistics,
raw data views/exports, and requirement/limit comparisons.

Open **Maths Channels**, enter a channel name, build a formula using backticked
column names, quoted exact column names, or the column insertion dropdown, then
click **Apply / Save Channel**. Example formulas:

```text
`Outlet Pressure` - `Inlet Pressure`
`Voltage` * `Current`
rolling_mean(`Current`, 25)
sqrt(abs(`Signal A`))
clip(`Pressure`, 0, 500)
```

Calculated channel definitions are saved in analysis sessions and recalculated
when a session is loaded before plot profiles are applied.

## Refactor status

The original monolithic GUI has been progressively broken out into focused
mixin modules. The public `TestDataAnalyserGUI` class in `gui.py` composes these
mixins (listed **before** `TestDataAnalyserGUIBase` in the method-resolution
order, so each extracted module is the source of truth for its behaviour).

`gui_base.py` (`TestDataAnalyserGUIBase`) is now the stable **foundation** and is
no longer a target for further extraction. It owns the shared scaffolding every
mixin builds on (window lifecycle, Eaton styling, the widget tree, cached
numeric conversion, shared axis-limit helpers, and generic table/text helpers).

All earlier dead duplicate methods left behind by previous extraction passes
have been removed from `gui_base.py`.

### Module layout

| Module | Responsibility |
| --- | --- |
| `gui.py` | Public `TestDataAnalyserGUI` class; composes all mixins over the base. |
| `gui_base.py` | Foundation: app lifecycle, Eaton styling, widget tree, shared helpers, axis-limit helpers. |
| `data_loading.py` | File/sheet loading, column population/classification, dataframe caches, Y-channel selection, debounced axis-selection handler, column-derived axis labels. |
| `plotting.py` | Figure/canvas management, plot data preparation, plot & FFT generation (incl. secondary Y-axis), legend handling, figure/output saving. |
| `cursor_tools.py` | Live cursor readout, locked Point Compare, cursor table/text rendering, using locked points as the analysis window. |
| `limits.py` | Requirement/limit line CRUD, limit point editing, limit plotting, active limit ranges, margin-to-limit reporting. |
| `analysis.py` | Statistics, selected-data ranges, range preview, axis-limit fill from data. |
| `raw_data.py` | Raw Data tab refresh, selected-data framing/filtering, row display limits, blank-row removal, selected-data export. |
| `raw_data_editor.py` | Inline Raw Data cell editing and dataframe refresh after edits. |
| `calculated_channels.py` | Maths Channel tab, safe formula evaluation, calculated channel CRUD, recalculation, and dataframe refresh integration. |
| `multi_run.py` | Runs / Comparison tab, multi-run loading/activation, comparison plotting, comparison statistics, and run metadata session integration. |
| `engineering_notes.py` | Structured Engineering Notes tab, note capture/restore, report formatting, clipboard copy, clearing. |
| `profile_state.py` | Plot profile creation/switching/duplication/rename/delete and JSON session save/load. |
| `label_profiles.py` | Per-plot label ownership and auto-label behaviour. |
| `config.py`, `data_io.py`, `filters.py`, `models.py`, `utils.py`, `widgets.py` | Supporting constants, data I/O, signal filtering, framework-independent plot/profile/session models, helpers, and reusable widgets. |
| `main.py` / `__main__.py` | Application entry points. |

### Status

- All major behaviour clusters have been extracted into focused mixins.
- `gui_base.py` has shrunk from the original monolith to ~850 lines of shared
  foundation code.
- The app launches and runs via `run_app.py`; loading, column selection,
  plotting (including secondary Y-axis), FFT, cursor compare, limits, raw data
  export, and engineering notes all function.

See `ARCHITECTURE.md` for the full staged refactor plan and rationale.
