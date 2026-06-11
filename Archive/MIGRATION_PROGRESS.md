# Test Data Analyser — PySide6 Migration Progress

This document summarises the staged migration of the **Test Data Analyser** from
a Tkinter desktop application toward a **PySide6 / Qt** architecture, what has
been completed so far, and the remaining work.

> **Status at a glance:** Phases 1–5 complete. The PySide6 / Qt app is now the
> only UI — it has full feature parity, and the legacy Tkinter UI has been
> removed. Launch with `python run_qt_app.py` (or `python -m test_data_analyser`).
> **176** headless tests pass.

---

## 1. Why this migration

The original application was a single large Tkinter GUI. The migration goal is a
**framework-independent core** with a thin, swappable UI on top, so the app can
move to PySide6/Qt without rewriting the engineering logic, and so that logic
becomes unit-testable without a GUI.

### Guiding rules (followed throughout)

- No big-bang rewrite — small, reviewable, architecture-safe steps.
- Keep the Tkinter app fully runnable until the Qt path reaches feature parity.
- Preserve all behaviour, engineering calculations, Eaton branding, and existing
  saved-session compatibility.
- **Domain, services, and viewmodels must never import a UI framework**
  (Tkinter or PySide6).
- Services return structured results (`OperationResult`) instead of showing
  message boxes or opening dialogs.

---

## 2. Target architecture (layers)

```
┌──────────────────────────────────┐
│  UI:  qt_app/ (PySide6)              │
│       widgets + adapters             │
└───────────────┬─────────────────┘
                │
                ▼
            viewmodels/  ── coordinate state + services, return OperationResult
                │
                ▼
            services/    ── pure engineering/data logic (no UI)
                │
                ▼
            domain/      ── framework-independent dataclasses (no UI)
```

- **domain/** — plain dataclasses for plot/profile/session state, limits,
  engineering notes, runs, and calculated channels, each with
  `from_dict()`/`to_dict()` that preserve on-disk key names.
- **services/** — reusable statistics, limits, maths-channel, plotting-data,
  raw-data, run-comparison, settings, and session logic. May use
  numpy/pandas/Matplotlib but never a UI toolkit.
- **viewmodels/** — UI-independent coordinators over `AppState` + services;
  return `OperationResult`; never touch Tk/Qt, dialogs, or message boxes.
- **qt_app/** — the only place PySide6 is imported: the main window, Eaton theme,
  migrated panel widgets, and Qt adapters. This is now the entire UI.

---

## 3. What has been completed

### Phase 1 — Domain models ✅

Created the framework-independent **`domain/`** package and routed the Tkinter
session save/load boundaries through it.

- Dataclasses: `PlotData`, `AxisLimits`, `AnalysisWindow`, `FilterSettings`,
  `LegendSettings`, `RawDataViewSettings`, `ManualLabelFlags`, `EngineeringNotes`,
  `LimitPoint`, `LimitLine`, `PlotProfile`, `RunMetadata`, `ComparisonSettings`,
  `CalculatedChannelDefinition`, and the top-level `SessionState`.
- Every model has `from_dict()`/`to_dict()` that tolerate missing keys and keep
  existing session JSON loading.
- `profile_state.py` save/load now normalises through `SessionState` while still
  honouring legacy top-level keys for very old sessions.

### Phase 2 — Pure services ✅

Extracted the engineering/data logic out of the Tkinter mixins into
**`services/`**; the mixins became thin wrappers that gather Tk state, call the
service, and apply the result.

| Service | Extracted from | Responsibility |
| --- | --- | --- |
| `statistics_service.py` | `analysis.py` | count/min/max/mean/median/std/RMS/peak-to-peak, statistics frame, X/Y ranges |
| `limits_service.py` | `limits.py` | limit normalisation, active ranges, margin-to-limit summary (structured + text) |
| `maths_channel_service.py` | `calculated_channels.py` | restricted-AST `MathsChannelEvaluator`, allowed functions, definition normalisation |
| `plotting_data_service.py` | `plotting.py` | analysis-window data preparation (no Matplotlib) |
| `plot_render_service.py` | `plotting.py` | Matplotlib colour-cycle resolution (no Tk/Qt) |
| `raw_data_service.py` | `raw_data*.py` | selected-data framing/filtering, row-limit parsing, edit coercion |
| `run_comparison_service.py` | `multi_run.py` | enabled runs, common-X range, comparison stats, run serialisation |
| `settings_service.py` | (new) | safe settings access + theme resolution |
| `session_service.py` | (new) | session dict build/normalise + JSON save/load |

`results.py` defines the shared `OperationResult` (ok/message/warnings/errors/payload).

### Phase 3 — ViewModels ✅

Created the **`viewmodels/`** package: UI-independent coordinators consumed by
the Qt shell.

- `AppState` — single source of truth (dataframe, file/sheet, plot profiles,
  runs, calculated channels, comparison settings).
- `DataLoadingViewModel`, `PlotWorkspaceViewModel`, `RawDataViewModel`,
  `MathsChannelsViewModel`, `RunsComparisonViewModel`, `LimitsViewModel`,
  `SettingsViewModel`, and the aggregating `MainWindowViewModel`
  (owns `AppState` + all feature VMs + session save/load).
- `MathsChannelsViewModel` returns `OperationResult` for validate/apply/
  recalculate/delete instead of showing message boxes.

### Phase 4 — Minimal PySide6 shell ✅

Created **`qt_app/`** with a minimal, framework-isolated shell.

- `theme.py` — centralised Eaton Qt stylesheet/palette sourced from `config.py`,
  honouring the light/dark theme concept.
- `main_window.py` / `main_qt.py` — `QApplication`/`QMainWindow`, Eaton header,
  File → Open wired through `DataLoadingViewModel`.
- `run_qt_app.py` — root launch script. `PySide6` is in `requirements.txt`.

**Cleanup:** the temporary top-level `models.py` re-export shim was removed and
its importers repointed to `test_data_analyser.domain`.

### Phase 5 — Panel migration ✅ (feature-complete)

First working slice of the real Qt UI: **load → select axes → plot → statistics**,
plus the settings dialog.

- **Adapters** (`qt_app/adapters/`): `pandas_table_model.py` (reusable
  `QAbstractTableModel`), `matplotlib_qt_adapter.py` (owns `FigureCanvasQTAgg` +
  toolbar), `qt_file_dialogs.py`, `qt_message_service.py`.
- **Widgets** (`qt_app/widgets/`): `data_file_panel.py`, `axis_selection_panel.py`,
  `plot_workspace.py` (Matplotlib Qt canvas), `statistics_panel.py`
  (`QTableView` + `PandasTableModel`), `settings_dialog.py`.
- `main_window.py` now wires these panels together; remaining lower tabs are
  labelled placeholders.

**Increment 2 — Raw Data panel.** The Raw Data tab is now a live, editable Qt
view wired through the framework-independent `RawDataViewModel`.

- `RawDataViewModel` gained `apply_edit`/`undo_last_edit`/`can_undo` (cell edits
  with an undo stack, writing back to `AppState.df`) and `export_selected_frame`
  (writes the selected/cleaned frame to `.csv`/`.xlsx`).
- New adapter `editable_raw_data_model.py` (`EditableRawDataTableModel`, a
  `PandasTableModel` subclass) adds inline editing: edits are validated through
  the viewmodel's `coerce_edit_value` and announced via `cellEdited`/`editFailed`
  signals, keeping all logic out of the widget.
- New widget `raw_data_panel.py` (`RawDataPanel`): row-limit entry,
  “apply analysis window” / “hide blank rows” toggles, Refresh/Undo/Export
  actions, and a status line. The main window injects the live axis/window
  selection and refreshes the panel after each plot.

**Increment 3 — Maths Channels panel.** The Maths Channels tab is now a live Qt
view wired through the framework-independent `MathsChannelsViewModel`.

- New widget `maths_channels_panel.py` (`MathsChannelsPanel`): a definition form
  (name, an insertable existing-column combo, a multi-line formula, a
  description, plus formula examples) beside a `QTableView` of the defined
  channels (Name / Formula / Enabled / Description). Toolbar actions — New/Clear,
  Validate, Apply/Save, Delete, Recalculate All — all run through the viewmodel
  and surface `OperationResult`s as dialogs/status.
- `AxisSelectionPanel.update_columns()` was added to refresh the available
  columns while preserving the current X and checked Y; the panel emits
  `channelsChanged` so the main window updates the axis selection and Raw Data
  view when calculated channels add/remove columns.

**Increment 4 — Requirements / Limits panel.** The Requirements/Limits tab is now
a live Qt view wired through the framework-independent `LimitsViewModel`.

- `LimitsViewModel` gained an optional `AppState` plus limit-line CRUD
  (`add_line`/`duplicate_line`/`delete_line`/`update_active_metadata`,
  `add_point`/`update_point`/`delete_point`, selection + colour-preset helpers)
  on top of its existing stateless calculation helpers. The limit-line list and
  the active-line index live on `AppState` (like calculated channels and runs).
- New widget `limits_panel.py` (`LimitsPanel`): a limit-lines table beside a
  definition editor (name, type, applies-to, colour preset/hex/picker/swatch), a
  points editor (X/Y entries + Add/Update/Delete and a points table), and the
  margin-to-limit summary. It emits `limitsChanged` so the main window redraws
  the canvas overlays.
- `PlotWorkspace.generate_plot()` now accepts normalised `limit_lines` and draws
  them as dashed (“--”) / dotted (“:”, Reference Line) overlays; the main window
  passes the current limits on every plot and re-plots when limits change.

**Increment 5 — Engineering Notes panel.** The Engineering Notes tab is now a live
Qt view wired through the new framework-independent `EngineeringNotesViewModel`.

- New `EngineeringNotesViewModel` owns the nine structured note fields (key,
  label, hint), reads/writes the notes on `AppState.engineering_notes` via the
  domain `EngineeringNotes` model, and compiles the report/email text.
- New widget `engineering_notes_panel.py` (`EngineeringNotesPanel`): a scrollable
  set of per-field editors plus a compiled report preview, with Refresh and
  Clear actions. The main window injects a context provider (file + X/Y axes)
  for the report header.

**Increment 6 — Runs / Comparison panel.** The Runs/Comparison tab is now a live
Qt view wired through the framework-independent `RunsComparisonViewModel`.

- `RunsComparisonViewModel` gained run CRUD (`add_run` with file loading,
  `remove_run`/`duplicate_run`/`rename_run`/`set_active`/`toggle_enabled`),
  `run_rows()` for the table, comparison-settings access on
  `AppState.comparison`, and `comparison_plot_items()` which prepares drawable
  `{label, x, y, colour}` items for the enabled runs.
- New widget `runs_comparison_panel.py` (`RunsComparisonPanel`): a runs table
  (with Add/Remove/Duplicate/Rename/Set-Active/Toggle and double-click toggle),
  the comparison options, a comparison-statistics table, and a Generate
  Comparison Plot action. It emits `comparisonRequested`; the main window draws
  the overlay through `PlotWorkspace.generate_comparison_plot()`.

**Increment 7 — Plot parity.** The primary plot now matches the Tkinter plot
options. `AxisSelectionPanel` gained a secondary-Y checklist, a plot-kind combo
(Line / Scatter / Line + Markers), and low-pass filter controls (cutoff +
order). `PlotWorkspace.generate_plot()` draws secondary-Y channels on a `twinx`
axis with an offset colour cycle, applies the SciPy low-pass filter per channel,
honours the plot kind, and merges both axes' legends.

**Increment 8 — Cursor point comparison.** New `cursor_service.py` (nearest
plotted sample + the locked-point/delta comparison table) and
`CursorCompareViewModel` (locked-point state, table data, analysis-window from
the first two points). `PlotWorkspace` owns the Matplotlib click/key wiring
(click to lock when compare mode is on, ESC to clear) and emits
`cursorPointsChanged`; the new `cursor_compare_panel.py` (`CursorComparePanel`)
renders the table and can push P1–P2 back as the analysis window.

**Increment 9 — Session save/load.** `MainWindowViewModel.capture_working_state()`
folds the top-level limit lines / engineering notes / axis selection into a
single plot profile, and `restore_session()` reloads the source file,
recalculates maths channels, reloads the comparison runs from their saved paths,
and pulls the working state back out — returning warnings for anything missing.
The Qt **File ▸ Save Session / Load Session** actions wire these through the Qt
file dialogs and re-apply the restored selection across every panel.

---

## 4. Current project structure

```
Test Data Analysis/
├─ run_qt_app.py                  # PySide6 entry point (the app)
├─ requirements.txt
├─ README.md
├─ ARCHITECTURE.md
├─ MIGRATION_PROGRESS.md          # (this document)
│
├─ test_data_analyser/
│  ├─ domain/                     # framework-independent models
│  │  ├─ conversions.py  engineering_notes.py  limits.py  models.py
│  │  ├─ plot_profile.py  run_model.py  session.py  settings.py
│  ├─ services/                   # framework-independent logic
│  │  ├─ statistics_service.py  limits_service.py  maths_channel_service.py
│  │  ├─ plotting_data_service.py  plot_render_service.py  raw_data_service.py
│  │  ├─ run_comparison_service.py  cursor_service.py
│  │  ├─ settings_service.py  session_service.py  results.py
│  ├─ viewmodels/                 # UI-independent coordinators
│  │  ├─ app_state.py  main_window_vm.py  data_loading_vm.py
│  │  ├─ plot_workspace_vm.py  raw_data_vm.py  maths_channels_vm.py
│  │  ├─ runs_comparison_vm.py  limits_vm.py  settings_vm.py
│  │  ├─ engineering_notes_vm.py  cursor_compare_vm.py
│  ├─ qt_app/                     # PySide6 UI (only place Qt is imported)
│  │  ├─ main_qt.py  main_window.py  theme.py
│  │  ├─ widgets/   data_file_panel.py  axis_selection_panel.py
│  │  │            plot_workspace.py  statistics_panel.py  settings_dialog.py
│  │  │            raw_data_panel.py  maths_channels_panel.py  limits_panel.py
│  │  │            engineering_notes_panel.py  runs_comparison_panel.py
│  │  │            cursor_compare_panel.py
│  │  ├─ adapters/  pandas_table_model.py  matplotlib_qt_adapter.py
│  │  │            qt_file_dialogs.py  qt_message_service.py
│  │  │            editable_raw_data_model.py
│  │
│  ├─ config.py  data_io.py  filters.py  utils.py  settings_manager.py
│  └─ __init__.py  __main__.py   # __main__ launches the Qt app
│
└─ tests/                         # headless, no GUI required
   ├─ test_domain_models.py  test_services.py
   ├─ test_viewmodels.py      test_qt_adapters.py
```

---

## 5. How to run

```bash
# PySide6 app
python run_qt_app.py
#   or
python -m test_data_analyser
#   or
python -m test_data_analyser.qt_app.main_qt

# Tests (headless; Qt tests auto-skip if PySide6 is absent)
python -m unittest discover -s tests
```

> **Interpreter note:** PySide6 + the data stack must be installed in the
> interpreter VS Code/`python` resolves to. Selecting an environment that lacks
> PySide6 causes `ModuleNotFoundError: No module named 'PySide6'` when launching
> the Qt shell.

---

## 6. Test coverage

All tests are framework-independent and run without a visible GUI.

| Suite | Focus | Count |
| --- | --- | --- |
| `test_domain_models.py` | `from_dict`/`to_dict` round-trips, session normalisation | 18 |
| `test_services.py` | statistics, limits, maths formulas, raw-data, run comparison, cursor | 35 |
| `test_viewmodels.py` | data loading, plot workspace, maths channels, runs (+ CRUD), raw-data edit/undo/export, limits CRUD, engineering notes, cursor compare, session save/restore | 76 |
| `test_qt_adapters.py` | table models, every migrated panel, axis controls, plot parity, cursor wiring (offscreen) | 47 |
| **Total** | | **176** |

---

## 7. Next steps

### Remaining Phase 5 increments (panel-by-panel)

1. **Raw Data panel** ✅ (increment 2) — `QTableView` + editable
   `EditableRawDataTableModel`, inline editing/undo via `RawDataViewModel`,
   row-limit/window/blank-row controls, and selected-data export.
2. **Maths Channels panel** ✅ (increment 3) — create/validate/recalculate/delete
   via `MathsChannelsViewModel`, with an insertable column combo and a live
   definitions table.
3. **Requirements / Limits panel** ✅ (increment 4) — limit-line + points editor,
   colour presets, margin-to-limit summary via `LimitsViewModel`, and dashed
   limit overlays drawn on the Qt canvas.
4. **Engineering Notes panel** ✅ (increment 5) — structured notes editor and
   compiled report preview via the new `EngineeringNotesViewModel`.
5. **Runs / Comparison panel** ✅ (increment 6) — multi-run management + comparison
   plotting via `RunsComparisonViewModel`.
6. **Cursor point comparison** ✅ (increment 8) — `cursor_service` +
   `CursorCompareViewModel` + `CursorComparePanel` with Matplotlib click/ESC
   wiring on the canvas.
7. **Session save/load** ✅ (increment 9) — `MainWindowViewModel.capture_working_state`
   / `restore_session` wired to **File ▸ Save/Load Session**, with file + run
   restoration.
8. **Plot parity** ✅ (increment 7) — secondary Y-axis, low-pass filter, plot
   kinds, and merged legends on the Qt canvas (limit overlays landed in
   increment 4).

### Final cleanup (done)

- The PySide6 UI reached feature parity, so the legacy Tkinter UI was **deleted**:
  `gui.py`, `gui_base.py`, the UI mixin modules (`analysis.py`, `limits.py`,
  `plotting.py`, `calculated_channels.py`, `raw_data.py`, `raw_data_editor.py`,
  `multi_run.py`, `cursor_tools.py`, `engineering_notes.py`, `data_loading.py`),
  `settings_window.py`, `widgets.py`, `profile_state.py`, `label_profiles.py`,
  and the Tk entry points (`run_app.py`, `main.py`). `__main__.py` now launches
  the Qt app, so `python -m test_data_analyser` still works.
- The domain/services/viewmodels layers are unchanged — they were already the
  shared core, and every one of the 176 tests still passes after the deletion.

### Ongoing testing expectations

- Add headless tests alongside each migrated panel's viewmodel interactions.
- Keep Qt widget tests under the offscreen platform and guarded so the suite
  stays green without a display.

---

## 8. Definition of done (architecture migration)

- ✅ Framework-independent logic is testable without a GUI.
- ✅ Domain models and services import no UI framework.
- ✅ PySide6 code is isolated to `qt_app/`.
- ✅ Plot rendering logic is reusable by either Tk or Qt.
- ✅ Existing sessions still load.
- ✅ The PySide6 UI reaches feature parity (Phase 5 complete).
- ✅ Legacy Tkinter UI is retired (deleted; `qt_app/` is the only UI).
