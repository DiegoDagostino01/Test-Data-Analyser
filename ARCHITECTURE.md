# Test Data Analyser — Architecture

The Test Data Analyser is a **PySide6 / Qt** desktop application built on a
framework-independent core. The engineering and data logic lives in layers that
import no UI toolkit, with a thin Qt UI on top. This makes the logic
unit-testable without a GUI and keeps the UI swappable.

> The application was migrated from an original Tkinter implementation. That
> staged migration is recorded in [MIGRATION_PROGRESS.md](MIGRATION_PROGRESS.md);
> this document describes only the **current** architecture.

## Layers

```
┌──────────────────────────────────────────────────────────────┐
│  qt_app/    PySide6 UI — main window, panels, theme, adapters │
└───────────────────────────┬──────────────────────────────────┘
                            ▼
   viewmodels/  UI-independent coordinators over AppState + services
                            ▼
   services/    pure engineering / data logic (numpy/pandas/Matplotlib OK)
                            ▼
   domain/      framework-independent dataclasses (no UI, no logic)
                            ▼
   core/        shared infrastructure (config, data I/O, filters, settings, utils)
```

The dependency direction only ever points downward. **Only `qt_app/` imports
PySide6.** `domain/`, `services/`, and `viewmodels/` must never import a UI
toolkit, open a dialog, or show a message box; they return values or a structured
`OperationResult`.

## Packages

### `core/` — shared infrastructure

Low-level, cross-cutting modules every other layer can use:

- `config.py` — Eaton brand colours, the app `__version__`, the domain keyword
  config (`DOMAIN_CONFIG`), limit-colour presets, the embedded header logo, and
  the light/dark theme palettes. The palettes now expose a fuller token set
  (workspace/card surfaces, muted/soft borders, an accent family, status
  success/warning/danger colours, and dedicated plot container/surface colours)
  so the Qt stylesheet and the Matplotlib canvas stay in sync.
- `data_io.py` — file/sheet discovery and loading (`get_excel_sheets`,
  `load_data`) and numeric coercion (`numeric_series`, `NUMERIC_EXTRACT_RE`).
- `filters.py` — sampling-rate estimation and the zero-phase low-pass
  (Butterworth) filter used by the plot canvas.
- `settings_manager.py` — `SettingsManager`, the persisted user-settings store
  (now also carrying axis-padding defaults and the remembered data/session
  import directories), resolved against the repository root.
- `utils.py` — column-name helpers (natural sort, grouped-column matching,
  keyword inference) plus `classify_channel_name`/`channel_group_options`, the
  deterministic engineering channel grouping used by the axis panel's channel
  filter.

### `domain/` — framework-independent models

Plain dataclasses that mirror the on-disk JSON shapes, each with
`from_dict()`/`to_dict()` helpers that tolerate missing keys so previously saved
sessions keep loading:

- `models.py` — the runtime `PlotData` container.
- `settings.py` — per-plot view/setting structures (`AxisLimits`,
  `AxisTickSettings`, `AnalysisWindow`, `FilterSettings`, `LegendSettings`,
  `RawDataViewSettings`, `ManualLabelFlags`). `AxisTickSettings` holds the
  per-axis major-tick spacing and the align-secondary-Y-grid flag, and
  `LegendSettings` carries a `display_mode` (right-side Qt legend panel vs an
  in-graph Matplotlib legend).
- `engineering_notes.py` — `EngineeringNotes` (accepts the structured dict form
  and the historical free-text string form).
- `limits.py` — `LimitPoint`, `LimitLine`.
- `plot_profile.py` — `PlotProfile` (now including `axis_ticks` and the
  `generated` flag) plus `plot_profile_from_dict`, `plot_profile_to_dict`, and
  `normalise_plot_profile`.
- `run_model.py` — `RunMetadata`, `ComparisonSettings`,
  `CalculatedChannelDefinition`.
- `session.py` — `SessionState`, the top-level analysis-session model.
- `conversions.py` — shared, defensive value-coercion helpers.

Import these directly, e.g. `from test_data_analyser.domain import PlotData`.

### `services/` — pure engineering/data logic

Reusable logic with no UI imports. Services may use numpy/pandas/Matplotlib but
must not embed in a canvas or show dialogs; they return values or an
`OperationResult` (`services/results.py`, fields: `ok`, `message`, `warnings`,
`errors`, `payload`).

- `statistics_service.py` — count/min/max/mean/median/std/RMS/peak-to-peak, the
  statistics DataFrame, and selected-data X/Y ranges.
- `limits_service.py` — limit-line normalisation, active limit ranges,
  applies-to resolution, and the margin-to-limit summary (`LimitMarginSummary`
  rows plus display text).
- `maths_channel_service.py` — the restricted-AST `MathsChannelEvaluator`, the
  allowed-function set, and calculated-channel definition normalisation.
- `plotting_data_service.py` — analysis-window data preparation plus cleaned,
  drawable plot/comparison series preparation (NaN dropping, low-pass
  filtering, and secondary-axis labelling), returned as plain arrays so Qt
  widgets only render — no Matplotlib canvas work.
- `plot_render_service.py` — Matplotlib-aware colour-cycle resolution, the
  secondary-axis cycle, and persistent per-channel colour mapping
  (`normalise_channel_name`, `y_axis_channel_set`,
  `persistent_channel_colour_map`) so a channel that recurs across plots keeps
  a stable colour (no Qt).
- `raw_data_service.py` — selected-data framing/filtering, blank-row removal,
  row-limit parsing, and edit coercion.
- `run_comparison_service.py` — enabled-run filtering, common-X range,
  per-channel comparison framing, comparison statistics, and run serialisation.
- `cursor_service.py` — nearest plotted sample and the locked-point/delta
  comparison table.
- `settings_service.py` — defensive settings access and theme resolution.
- `session_service.py` — session dict assembly/normalisation through
  `SessionState` plus JSON save/load.

### `viewmodels/` — UI-independent coordinators

ViewModels coordinate domain state and services, expose plain Python data, and
return `OperationResult`. They hold no Qt objects, open no dialogs, and show no
message boxes.

- `app_state.py` — `AppState`: the single source of truth (dataframe, source
  file/sheet, plot profiles, runs + active index, calculated channels, limit
  lines + active index, engineering notes, comparison settings, settings
  manager).
- `data_loading_vm.py` — file/sheet loading into the state.
- `plot_workspace_vm.py` — plot-data preparation, selected ranges, statistics,
  and prepared plot/comparison series (pulls numeric series from the state
  directly).
- `raw_data_vm.py` — Raw Data selection/filtering, row-limit parsing, display
  frame preparation, edit coercion, cell edits with undo, and selected-data
  export.
- `maths_channels_vm.py` — validate/apply/recalculate/delete calculated
  channels plus table-display data for the Qt panel, mutating the state's
  dataframe/definitions in place.
- `limits_vm.py` — limit-line + point CRUD, colour-preset helpers, active
  ranges, table-display data, and the margin-to-limit summary.
- `runs_comparison_vm.py` — run CRUD (load/remove/duplicate/rename/set-active/
  toggle), comparison settings, comparison-item preparation, table-display data,
  and statistics.
- `engineering_notes_vm.py` — the structured note fields, get/set/clear, and the
  compiled report text.
- `cursor_compare_vm.py` — locked comparison points, the comparison table, and
  the analysis window derived from the first two points.
- `settings_vm.py` — settings get/set/save, theme info, and option lists.
- `main_window_vm.py` — the top-level coordinator owning `AppState` and every
  feature viewmodel, multiple plot-profile management
  (`add`/`duplicate`/`rename`/`delete`/`select_plot_profile`, plus
  `ensure`/`reset_plot_profiles` and `persistent_plot_channel_colours`), and
  session build/save/load and full restore (`capture_working_state`,
  `restore_session`).

### `qt_app/` — the PySide6 UI

The only package that imports PySide6.

- `main_qt.py` — the `QApplication` entry point.
- `main_window.py` — `MainWindow`: the Eaton-branded header and logo, the
  grouped ribbon command bar, the axis/data controls, the Matplotlib plot
  canvas, multiple plot-profile tabs (new/duplicate/rename/delete), the lower
  analysis tabs, the File/Edit menus (Open, Save/Load Session, Settings),
  Help/About dialogs, and the wiring between every panel and the viewmodels.
- `theme.py` — the centralised Eaton Qt stylesheet/palette, sourced from
  `core/config.py` and honouring light/dark.
- `widgets/` — one thin panel per feature: `data_file_panel`,
  `axis_selection_panel`, `plot_workspace`, `statistics_panel`, `raw_data_panel`,
  `maths_channels_panel`, `limits_panel`, `engineering_notes_panel`,
  `runs_comparison_panel`, `cursor_compare_panel`, `settings_dialog`, and the
  shared `no_wheel_combo_box` (a `QComboBox` that ignores the mouse wheel so
  scrolling a panel never changes a selection). `axis_selection_panel` groups
  channels by engineering type and keeps primary/secondary Y selections in
  separate equal-sized lists; `plot_workspace` owns the canvas plus the
  right-side Qt legend panel and the legend display-mode switch.
- `adapters/` — the Qt/Matplotlib boundary objects (no business logic):
  `pandas_table_model` (reusable `QAbstractTableModel`),
  `editable_raw_data_model` (inline-editing subclass),
  `matplotlib_qt_adapter` (owns the `FigureCanvasQTAgg` + the
  `LegendAwareNavigationToolbar`, which extends Figure Options with legend,
  axis-tick, and auto-label/auto-fit controls, applies the active theme to the
  canvas, and prepares the figure so exported PNGs include the legend),
  `qt_file_dialogs`, `qt_message_service`, and `qt_widget_helpers` (remembers
  the last data/session directories in settings).

## Key flows

- **Plotting.** `MainWindow._generate_plot()` reads the axis panel (X, primary &
  secondary Y, plot kind, analysis window, filter), asks `PlotWorkspace` to
  render prepared series from `PlotWorkspaceViewModel`, applies persistent
  per-channel colours, axis padding, and major-tick spacing, draws limit
  overlays, and refreshes statistics, raw data, margins, and the cursor state.
- **Plot profiles.** The plot-tab bar maps to `MainWindow`'s active plot
  profile; switching tabs captures the current profile and applies the selected
  one. `MainWindowViewModel` owns the add/duplicate/rename/delete/select
  operations, and each profile round-trips its channels, labels, axis limits,
  ticks, legend mode, and `generated` flag.
- **Figure Options.** `LegendAwareNavigationToolbar` augments the Matplotlib
  Figure Options dialog with legend, axis-tick, and auto-label/auto-fit
  controls; the legend can be shown in the right-side Qt panel or in-graph, and
  the export path temporarily draws the panel legend onto the axes so saved
  PNGs match the on-screen plot.
- **Signals.** Panels communicate with the main window via Qt signals
  (`fileLoaded`, `channelsChanged`, `limitsChanged`, `comparisonRequested`,
  `cursorPointsChanged`, `analysisWindowRequested`, `statusMessage`); the main
  window owns cross-panel refreshes.
- **Cursor.** `PlotWorkspace` owns the Matplotlib click/key wiring and the
  locked-point markers; `CursorCompareViewModel` owns the point list and table
  data, so the logic stays GUI-free.
- **Sessions.** `capture_working_state()` folds the top-level limit lines,
  engineering notes, axis selection, the `generated` flag, and the live plot
  appearance into a plot profile; `restore_session()` reloads the file and runs,
  recalculates maths channels, and returns the saved selection (plus warnings)
  for the UI to re-apply and re-render. File and session dialogs reopen at the
  last-used directory remembered in settings.

## Branding

Axis/title labels are treated as per-plot-profile state: a manually edited label
is preserved across subsequent X/Y channel changes for that plot, and auto-label
behaviour can return label fields to automatic generation. Eaton brand colours,
the version string, the header logo, and the light/dark theme palettes all live
in `core/config.py` and are the single source of truth for the Qt stylesheet,
the Matplotlib canvas surfaces, and the plot colour cycles.

## Recent enhancements

A post-migration usability and feature-refinement pass built on the Qt-only
architecture above; the detailed step-by-step log lives in
[pyside6-migration.md](pyside6-migration.md). Highlights:

- **Multiple plot profiles.** Each plot is a named, switchable tab whose full
  state (channels, labels, axis limits/ticks, legend mode, generated flag)
  round-trips through `PlotProfile`, managed by `MainWindowViewModel`.
- **Figure Options & legends.** A `LegendAwareNavigationToolbar` adds legend,
  axis-tick, and auto-label/auto-fit controls to Matplotlib Figure Options, with
  a Qt-panel vs in-graph legend switch (`LegendSettings.display_mode`) and
  legend-aware PNG export.
- **Axis ticks & padding.** New `AxisTickSettings` (per-axis major-tick spacing
  and secondary-grid alignment) plus configurable axis padding applied during
  rendering.
- **Channel grouping & persistent colours.** Deterministic engineering channel
  classification (`core/utils`) drives the axis panel's channel filter, and
  `plot_render_service` keeps recurring channels on stable colours across plots.
- **Service-side plot prep.** `plotting_data_service.prepare_plot_series` /
  `prepare_comparison_series` move NaN dropping, filtering, and secondary-axis
  labelling out of the widgets.
- **Theme & branding.** Expanded light/dark palettes and theme-aware canvas
  surfaces sourced from `core/config.py`, plus the restored header logo.
- **Usability.** Wheel-safe combo boxes, remembered data/session directories,
  and session restore that re-renders the plot and its Figure Options
  appearance.

## Testing

All tests are framework-independent and run headless via
`python -m unittest discover -s tests`:

- `tests/test_domain_models.py` — `from_dict`/`to_dict` round-trips and session
  normalisation.
- `tests/test_services.py` — statistics, limits, maths formulas, raw data,
  run comparison, and cursor logic.
- `tests/test_viewmodels.py` — every viewmodel, plus session save/restore.
- `tests/test_qt_adapters.py` — the table models, every migrated panel, the axis
  controls, plot parity, and the cursor wiring, under the Qt **offscreen**
  platform (skipped automatically when PySide6 is absent).
