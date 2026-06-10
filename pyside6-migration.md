# Test Data Analyser — PySide6 architecture migration

Staged migration from Tkinter to PySide6 (see Downloads/PySide6_Architecture_Migration_Prompt.md).
Rule: small safe steps, keep Tk app runnable, no UI imports in domain/services.

## Done — Phase 1: domain model extraction
- Created `test_data_analyser/domain/` package (framework-independent, no Tk/Qt):
  - conversions.py (_mapping/_string/_string_list/_float/_int helpers)
  - models.py (PlotData), settings.py (AxisLimits/AnalysisWindow/FilterSettings/
    LegendSettings/RawDataViewSettings/ManualLabelFlags), engineering_notes.py,
    limits.py (LimitPoint/LimitLine), plot_profile.py (PlotProfile + helpers),
    run_model.py (RunMetadata/ComparisonSettings/CalculatedChannelDefinition),
    session.py (SessionState)
- `models.py` is now a thin re-export shim (kept for `from .models import PlotData` etc.).
- `profile_state.py` save/load now normalise through `SessionState`. Legacy top-level
  engineering_notes/limit_lines still read from raw session dict (old-session fallback).
- Tests: `tests/test_domain_models.py` (stdlib unittest, headless). Run:
  `python -m unittest discover -s tests`
- Verified: 18 tests pass; `python run_app.py` launches clean.

## Key compatibility facts
- Session JSON keys (save_analysis_session): version, file_path, sheet_name, runs[],
  active_run_index, comparison_mode_enabled, comparison_common_x_range,
  comparison_prefix_legend, active_plot_profile_index, plot_profiles[], calculated_channels{}.
- Run dict keys: name, filepath, sheet_name, enabled, colour.
- Calc channel keys: name, formula, description, enabled, created_from_columns[].
- Eaton colours/version live in config.py (no Tk import) — reuse as source of truth for Qt theme.

## Done — Phase 2: service layer extraction
- Created `test_data_analyser/services/` (no Tk/Qt; return values or OperationResult):
  - results.py (OperationResult), statistics_service, limits_service (LimitMarginSummary/Row),
    maths_channel_service (MathsChannelEvaluator + normalise_calculated_channel_definitions),
    plotting_data_service (apply_analysis_window), plot_render_service (resolve_plot_colours,
    secondary_colour_cycle; matplotlib OK), fft_service (fft_window/fft_spectrum),
    raw_data_service (parse_row_limit/select_raw_data_frame/coerce_raw_edit_value),
    run_comparison_service (enabled_runs/common_x_range/channel_frame/run_channel_statistics/serialise_runs).
- Mixins are now THIN WRAPPERS: analysis.py, limits.py, calculated_channels.py, plotting.py,
  raw_data.py, raw_data_editor.py, multi_run.py gather Tk state -> call service -> apply to widgets.
- Behavior preserved exactly (margin summary text reproduced via LimitMarginSummary.to_text).
- Tests: tests/test_services.py (31 tests). Total suite 49 tests, all pass. App launches clean.
- NOTE: plotting.py has PRE-EXISTING static-checker "cannot access attribute" noise (mixin pattern;
  PlottingMixin doesn't annotate self:Any like AnalysisMixin does). Not real errors, not from Phase 2.

## Done — Phase 3: viewmodel layer
- Added the 2 deferred services: services/settings_service.py (safe_get/is_dark_theme/theme_name/
  palette_for over a SettingsManager-like reader) and services/session_service.py
  (build_session_dict/normalise_session/save_session_dict/load_session_dict via SessionState + json).
- Created `test_data_analyser/viewmodels/` (no Tk/Qt; return OperationResult):
  - app_state.py (AppState dataclass: df, filepath, sheet_name, plot_profiles, active_plot_profile_index,
    runs, active_run_index, calculated_channels, comparison, settings_manager; has_data/column_names/
    active_plot_profile/active_run).
  - data_loading_vm (load_file/get_sheets/suggested_x_column — Phase 4 integrates this one).
  - settings_vm, plot_workspace_vm (prepare_plot_data pulls numeric via data_io.numeric_series, no Tk cache),
    limits_vm, raw_data_vm, maths_channels_vm (validate/apply/recalculate/delete -> OperationResult,
    mutates AppState.df + calculated_channels in place), runs_comparison_vm, main_window_vm
    (owns AppState + all VMs; build_session/save_session/load_session).
- VMs are ADDITIVE: Tk app unchanged (panel rewiring is Phase 5). VMs are for the Qt shell.
- Tests: tests/test_viewmodels.py (37 tests). Total suite now 86 tests, all pass. App launches clean.
- Test count history: Ph1=18, Ph2=+31 (49), Ph3=+37 (86).

## Done — Phase 4: minimal PySide6 shell
- PySide6 6.11.1 installed in GLOBAL python (C:/Users/E0764939/AppData/Local/Programs/Python/Python312).
  Bare `python` in pwsh = that global interpreter (has pandas+PySide6). NOT the .venv (.venv lacks deps).
- requirements.txt updated by USER (PySide6 + extras: seaborn, pyqtgraph, pyarrow, pydantic, reportlab, etc).
- Created `test_data_analyser/qt_app/`: __init__.py, theme.py (build_stylesheet from config.py Eaton colours,
  light/dark), main_window.py (MainWindow: Eaton header/ribbon, left controls placeholder, central plot
  placeholder, lower QTabWidget w/ columns table, status bar, File>Open via DataLoadingViewModel), main_qt.py
  (QApplication entry). Root: run_qt_app.py.
- Verified: offscreen smoke test loads CSV via VM -> columns table populates; windowed launch clean; Tk app
  still launches; 86 tests still pass.
- Qt launch: `python run_qt_app.py` or `python -m test_data_analyser.qt_app.main_qt`.
- Headless Qt test tip: set QT_QPA_PLATFORM=offscreen. Font-dir warning is harmless.

## Cleanup done (user asked to delete dead files)
- DELETED test_data_analyser/models.py (the top-level backward-compat shim). Repointed 5 importers
  (cursor_tools, gui_base, limits, multi_run, plotting) from `.models import PlotData` -> `.domain import PlotData`.
- domain/models.py is a DIFFERENT file (domain package's PlotData home) — kept.
- HARD RULE: do NOT delete Tkinter modules until Qt reaches parity (Phase 5). Tk is still the only full app.

## Next phases (in progress)
- Phase 5 IN PROGRESS — panel-by-panel Qt migration. See "Phase 5 increment 1" below.

## Done — Phase 5 increment 1 (load→plot→stats slice + settings dialog)
- settings_vm: added options_for(section,key) (pluralises key -> available_* list).
- qt_app/adapters/: pandas_table_model.py (PandasTableModel(QAbstractTableModel), optional index_header col
  for channel-indexed stats), matplotlib_qt_adapter.py (MatplotlibCanvas: FigureCanvasQTAgg+NavigationToolbar2QT,
  from matplotlib.backends.backend_qtagg), qt_file_dialogs.py, qt_message_service.py (info/warning/error/confirm/show_result).
- qt_app/widgets/: data_file_panel.py (DataFilePanel: open+sheet combo via DataLoadingViewModel, signals
  fileLoaded(list)/statusMessage), axis_selection_panel.py (X combo + checkable Y QListWidget + analysis window
  + Generate/FFT signals), plot_workspace.py (PlotWorkspace: renders line plot + FFT from PlotWorkspaceViewModel,
  colours via plot_render_service; returns OperationResult), statistics_panel.py (QTableView+PandasTableModel),
  settings_dialog.py (focused dialog via SettingsViewModel get/set/save, FIELD_SPEC tabs, theme re-applies on save).
- main_window.py REWRITTEN: wires panels (load->axes->plot->stats) + Edit>Settings. Lower tabs: Statistics real,
  others placeholders (Raw Data, Maths, Limits, Notes, Runs).
- Tests: tests/test_qt_adapters.py (9 tests, skip if no PySide6, QT_QPA_PLATFORM=offscreen in setUpModule).
  Total suite now 95 tests, all pass. Both apps launch clean. E2E offscreen: load CSV->2 Y->plot=2 lines->
  stats 2x9->FFT ok.
- Test count history: Ph1=18, Ph2=49, Ph3=86, Ph5inc1=95.

## Done — Phase 5 increment 2 (Raw Data panel)
- raw_data_vm: added apply_edit/undo_last_edit/can_undo (cell edits + undo stack writing back to AppState.df,
  integer-dtype->float when value is NaN, mirrors Tk _commit_raw_cell_edit) and export_selected_frame
  (writes selected/cleaned frame to .csv/.xlsx via select_frame; fails on empty frame).
- qt_app/adapters/editable_raw_data_model.py: EditableRawDataTableModel(PandasTableModel) adds inline edit:
  flags()|ItemIsEditable, data(EditRole) -> str (""for NaN), setData() coerces via injected callback
  (vm.coerce_edit_value), emits cellEdited(df_index,col,value)/editFailed(msg). df_index = display._df.index[row]
  (display copy keeps original index, so positional iat + index label maps back to source df).
- qt_app/widgets/raw_data_panel.py: RawDataPanel(vm) — row-limit QLineEdit("All"), "Apply analysis window"(True),
  "Hide rows with blank cells"(True) checks, Refresh/Undo/Export buttons, status QLabel. Uses a
  selection_provider callable (set by main_window -> _current_axis_selection) to get live (x_col,selected_y,xmin,xmax).
  cellEdited -> vm.apply_edit; editFailed -> error dialog; export via qt_file_dialogs.save_export_file + vm.export_selected_frame.
- main_window: imports RawDataPanel, creates self.raw_data_panel + set_selection_provider(self._current_axis_selection),
  Raw Data tab now real (others still placeholders), refresh() after generate_plot, clear() on file load.
- GOTCHA: select_raw_data_frame includes X col even with no Y -> frame NOT empty; the "no selection" guard is in
  the PANEL (_export/refresh check `not x_col or not selected_y`), VM only fails on genuinely empty frame.
- Qt enum static-checker: use fully-qualified forms in new code (QAbstractItemView.EditTrigger.DoubleClicked,
  QHeaderView.ResizeMode.Interactive). OperationResult.payload is typed `object|None` -> narrow with isinstance before frame.head().
- Tests: +5 viewmodel (apply_edit/undo/export) in test_viewmodels.py, +6 Qt (EditableRawDataTableModelTests) in
  test_qt_adapters.py. Total now 106. Test count history: Ph1=18, Ph2=49, Ph3=86, Ph5inc1=95, Ph5inc2=106.
- Verified: full suite 106 pass; offscreen E2E (load->2 Y->plot->raw 4x3->edit cell->df updated->undo->restored->export csv) OK;
  both apps import clean.

## Done — Phase 5 increment 3 (Maths Channels panel)
- No new VM/service methods needed; MathsChannelsViewModel already had validate_formula/apply_channel
  (selected_name= for rename)/recalculate/delete_channel/normalise_definitions, all -> OperationResult.
- axis_selection_panel.py: added update_columns(columns) — refreshes X combo + checkable Y list while
  PRESERVING current X selection and checked Y (used when maths channels add/remove columns). set_columns
  still used on fresh file load (resets selection).
- qt_app/widgets/maths_channels_panel.py: MathsChannelsPanel(vm). Signals channelsChanged()/statusMessage(str).
  Layout: toolbar (New/Clear, Validate, Apply/Save[PrimaryButton], Delete, Recalculate All) + QSplitter
  [form QFrame#EatonPanel | QTableView]. Form: name QLineEdit, existing-column QComboBox + "Insert into Formula"
  button (inserts `col` backticked at cursor via formula_edit.insertPlainText), formula QPlainTextEdit(minH 90),
  description QLineEdit, examples QLabel#PlaceholderText. Table: read-only PandasTableModel (cols Name/Formula/
  Enabled/Description), SelectRows/SingleSelection/NoEditTriggers, header Stretch, vertical header hidden.
- Selection->form: self._channel_order = list(state.calculated_channels.keys()); selectionModel().selectionChanged
  -> _load_into_form(name). GOTCHA: re-selecting the ALREADY-selected row does NOT refire selectionChanged (same
  as legacy Tk <<TreeviewSelect>>), so form won't reload on same-row click — fine for parity. After _apply, call
  refresh() then _select_channel(name) (selectRow fires load). enabled flag shown read-only ("Yes"/No); apply
  always sets enabled=True (legacy has no toggle either).
- Delete: ALWAYS confirms via qt_message_service.confirm (didn't wire settings confirm_before_delete -> panel
  only takes the maths VM, kept decoupled). Recalculate: builds detailed warning from payload["errors"] list.
- main_window: import MathsChannelsPanel, self.maths_panel=MathsChannelsPanel(self.vm.maths_channels), Maths
  Channels tab now real (Limits/Notes/Runs still placeholders). channelsChanged -> _on_channels_changed:
  axis_panel.update_columns(state.column_names()) + raw_data_panel.refresh(). On file load: maths_panel.clear_form()
  + refresh(). statusMessage -> status bar.
- TEST GOTCHA: panel methods call qt_message_service.info/warning/error/confirm/show_result = MODAL (block headless).
  In tests patch those 5 funcs on the panel module's qt_message_service (confirm->True) in setUp, restore in tearDown.
- Tests: +5 Qt (MathsChannelsPanelTests in test_qt_adapters.py: apply creates channel+row, selection loads form,
  delete removes, insert wraps backticks, clear_form resets). Total now 111.
  Test count history: Ph1=18, Ph2=49, Ph3=86, Ph5inc1=95, Ph5inc2=106, Ph5inc3=111.
- Verified: 111 pass; offscreen E2E (load->create Power=A*B->in df+axis Y list->validate->insert col->select row
  loads form->recalc->delete->gone from df+axis) OK; both apps import clean.

## Done — Phase 5 increment 4 (Requirements/Limits panel)
- AppState: added limit_lines: list[dict] + active_limit_line_index: int (top-level working state for the active
  profile's limits; session sync to plot profiles is increment 7). Line dict = {name,type,applies_to,color,points:[{x,y}]}.
  Types: "Upper Limit","Lower Limit","Reference Line".
- limits_vm REWRITTEN: __init__(state: AppState|None=None) — state OPTIONAL so existing LimitsViewModel() tests/usage
  (stateless margin_summary/margin_text/active_ranges/normalise) still work. Added stateful CRUD on self.state.limit_lines:
  add_line/duplicate_line(deepcopy + " Copy")/delete_line, update_active_metadata(name=,limit_type=,applies_to=,colour=),
  add_point/update_point/delete_point (parse via float, points kept X-sorted, ValueError->OperationResult.failure),
  active_line/active_index(clamped)/select_line/active_points(sorted). Static helpers: limit_types(), colour_presets()
  (config.LIMIT_COLOR_PRESETS), preset_for_colour/colour_for_preset, applies_options(selected_y).
- main_window_vm: LimitsViewModel() -> LimitsViewModel(self.state).
- plot_workspace.generate_plot gained limit_lines param + _draw_limit_lines: linestyle ":" for Reference Line else "--",
  lw 1.6, label "Name [Type]", color fallback EATON_DARK_BLUE. Drawn after data, before legend.
- limits_panel.py: LimitsPanel(limits_vm, plot_vm) — takes BOTH VMs (margins need PlotData via plot_vm.prepare_plot_data).
  selection_provider->(x_col,selected_y,xmin,xmax). Lines QTableView | editor (name/type/applies/colour preset+hex+swatch+
  QColorDialog Pick) + points group (X/Y edits + Add/Update/Delete + points table) + margin summary QPlainTextEdit.
  GOTCHAS: self._loading guards form-load vs store recursion; _refresh_lines_table reselects with _loading=True; colour
  combo uses .activated; QColorDialog.getColor(parent=self).isValid()/.name().
- main_window: limits_panel=LimitsPanel(vm.limits, vm.plot_workspace)+selection_provider; Requirements/Limits tab real
  (only Notes + Runs placeholders left). _on_generate_plot passes limit_lines=vm.limits.normalise(state.limit_lines) +
  limits_panel.refresh_margins(). limitsChanged -> re-generate_plot w/ overlays if x+y selected. File load: refresh().
- TEST GOTCHA (same as maths): patch panel module's qt_message_service 5 dialog funcs in setUp.
- Tests: +8 viewmodel (LimitsViewModelCrudTests) + 6 Qt (LimitsPanelTests). Total now 125.
  Test count history: Ph1=18, Ph2=49, Ph3=86, Ph5inc1=95, Ph5inc2=106, Ph5inc3=111, Ph5inc4=125.
- Verified: 125 pass; offscreen E2E (load->add line Max + 2 pts->plot shows 'Max [Upper Limit]' overlay + margin PASS->
  colour preset Red->duplicate/delete line->update/delete point) OK; both apps import clean.

## Done — Phase 5 increments 5+6 (Engineering Notes + Runs/Comparison, done together)
- AppState: added engineering_notes: dict[str,str] (comparison: ComparisonSettings already existed; runs/active_run_index already existed).
- NEW viewmodels/engineering_notes_vm.py: EngineeringNotesViewModel(state). field_definitions()->[(key,label,hint)]x9
  (objective,test_article,conditions,observations,rationale,anomalies,comparison,actions,report_summary), field_keys(),
  get_notes()->full blank-filled dict via domain EngineeringNotes.from_dict(state.engineering_notes).to_dict(),
  set_notes(dict|str), update_field(key,val), clear()->EngineeringNotes().to_dict(), report_text(file_name=,x_axis=,y_axis=).
  GOTCHA: report_text returns "No engineering notes have been entered yet." when NO body field filled (check `body` empty
  BEFORE building header, else header always non-empty and fallback never fires — a test caught this).
- Exported EngineeringNotesViewModel from viewmodels/__init__.py + instantiated in main_window_vm (self.engineering_notes).
- runs_comparison_vm EXTENDED (was: enabled_runs/next_run_colour/make_run_entry/common_x_range/comparison_statistics/
  serialise_runs). Added: get_sheets(path), add_run(path,sheet)->loads via data_io.load_data + appends + sets active if first
  (OperationResult, payload=index), remove_run/duplicate_run(" Copy", df.copy(deep=False))/rename_run/set_active/toggle_enabled
  (all OperationResult, index-bounds-checked, remove adjusts active_run_index), run_rows()->[{Name,Enabled,Active,File,Sheet,
  Rows,Columns}], get_setting/set_setting(name,bool) over state.comparison (ComparisonSettings attrs: comparison_mode_enabled,
  comparison_common_x_range, comparison_prefix_legend, active_run_index), comparison_plot_items(selected_x,y_cols,use_common_x=,
  xmin=,xmax=,prefix_legend=)->(items,skipped) where item={label,x:np,y:np,colour}; uses run_comparison_service.comparison_channel_frame
  + _matching_x_column_for_y.
- plot_workspace.generate_comparison_plot(items,x_col,title="Run Comparison",limit_lines=None): one line per item (colour from
  item), draws limit overlays too, legend. Returns OperationResult. (generate_plot already had limit_lines param from inc4.)
- engineering_notes_panel.py: EngineeringNotesPanel(vm). QScrollArea of per-field QFrame#EatonPanel(label+hint+QPlainTextEdit),
  + compiled report QPlainTextEdit(readOnly). Toolbar: Refresh Report Text[PrimaryButton], Clear Notes. editor.textChanged->
  vm.update_field (block signals during load_from_state). context_provider->(file_name,x_axis,y_axis) injected by main_window
  (_notes_context: filepath.name + axis x/y). _clear confirms via qt_message_service.
- runs_comparison_panel.py: RunsComparisonPanel(vm). Signals comparisonRequested()/statusMessage(str). Toolbar: Add Run…/Remove/
  Duplicate/Rename/Set Active/Toggle Enabled/Generate Comparison Plot. Options: 2 QCheckBox (prefix_legend, common_x) write-through
  to vm.set_setting. QSplitter[runs QTableView | stats QTableView] both read-only PandasTableModel. Add Run uses qt_file_dialogs.
  open_data_file + QInputDialog.getItem for multi-sheet Excel. Rename uses QInputDialog.getText. doubleClicked->_toggle_via_index(row)
  (extracted helper so testable w/o QModelIndex). selection_provider->(x,y,xmin,xmax) for stats + comparison.
- main_window: both tabs now REAL — ALL 6 lower tabs migrated (Statistics, Raw Data, Maths, Limits, Engineering Notes, Runs/Comparison),
  NO placeholders left. notes_panel.set_context_provider(_notes_context); runs_panel.set_selection_provider(_current_axis_selection);
  comparisonRequested->_on_generate_comparison (builds items via vm.comparison_plot_items w/ settings, draws via generate_comparison_plot
  w/ limit overlays, updates stats + status w/ skipped count). On file load: notes_panel.load_from_state() + runs_panel.refresh().
  _on_generate_plot also calls runs_panel.update_statistics().
- TEST GOTCHA (same as before): patch panel module's qt_message_service dialog funcs in setUp/tearDown.
- Tests: +13 viewmodel (RunsComparisonViewModelCrudTests x7, EngineeringNotesViewModelTests x6) + 9 Qt (EngineeringNotesPanelTests x4,
  RunsComparisonPanelTests x5). Total now 147.
  Test count history: Ph1=18, Ph2=49, Ph3=86, Ph5inc1=95, inc2=106, inc3=111, inc4=125, inc5+6=147.
- Verified: 147 pass; offscreen E2E (notes: edit fields->report includes text+file->clear; runs: add 2 runs->table 2 rows->stats 2->
  comparison plot 'Run 1 | A'+'Run 2 | A'->toggle run2 off->replot 1 line->rename->remove) OK; both apps import clean.

## Done — Phase 5 increments 7+8+9 (plot parity + cursor compare + session save/load)
- PLOT PARITY (inc7): axis_selection_panel.py added secondary_y_list (checkable QListWidget, separate from primary y_list),
  plot_kind_combo (PLOT_KINDS=("Line","Scatter","Line + Markers")), filter row (filter_check + cutoff_edit + order_edit).
  Accessors: selected_secondary_y(), all_selected_y()=primary+secondary deduped (USE THIS for plotting/stats/raw/margins —
  secondary channels are in a SEPARATE list so must be unioned in!), plot_kind(), filter_settings()->(use_filter,cutoff,order).
  Refactored set_columns/update_columns to _populate_checklist helper; added apply_selection(columns,x,y,sec) for session restore.
  Used fully-qualified Qt enums (Qt.CheckState.Checked, Qt.ItemFlag.ItemIsUserCheckable, QListWidget.SelectionMode.NoSelection).
- plot_workspace.generate_plot gained secondary_y/plot_kind/use_filter/cutoff/order params. twinx for secondary (only if
  secondary_set & y_map keys non-empty), secondary_colour_cycle from plot_render_service, lowpass_filter from filters (label
  "X | LP {cutoff}g Hz"), "[Right Y]" suffix. _plot_series(kind): Scatter->scatter(s=14), Line+Markers->plot(marker=o,ms=3),
  else plot. _merge_legends(axes,sec) combines handles from BOTH axes (twinx legends are separate!). Stores _last_plot_data/_last_x_col.
- main_window: _generate_plot() shared helper (used by _on_generate_plot AND _on_limits_changed) builds kwargs from axis panel
  using all_selected_y(). BUG FOUND BY SMOKE: _on_generate_plot referenced undefined y_cols after refactor — fixed to self.axis_panel.
  all_selected_y(). _current_axis_selection also returns all_selected_y() now.
- CURSOR (inc8): services/cursor_service.py — nearest_point(x_series,y_map,xdata)->{index,x,values} (idxmin |x-xdata|),
  cursor_comparison_frame(points,decimals)->DataFrame cols [Type,Point,Index / Ref,X / ΔX]+channels, per-point rows + "Δ vs P1"
  delta rows when >=2 pts. viewmodels/cursor_compare_vm.py — CursorCompareViewModel (standalone, NO AppState): set_data(PlotData|None
  clears pts), lock_at(xdata)->bool, clear(), comparison_frame(), analysis_window_from_points()->sorted(x1,x2) of first 2.
  Exported from viewmodels/__init__; main_window_vm self.cursor_compare=CursorCompareViewModel().
- plot_workspace OWNS the mpl event wiring: cursorPointsChanged=Signal(); __init__ mpl_connect button_press+key_press;
  set_cursor_viewmodel/set_point_compare_enabled/clear_cursor_markers; _on_canvas_click (point_compare & button==1 & inaxes:
  vm.lock_at + axvline + emit), _on_canvas_key (escape->clear+emit); generate_plot->_set_cursor_data(data), comparison/fft->
  _set_cursor_data(None). cursor_compare_panel.py — CursorComparePanel(cursor_vm,plot_workspace): Point Compare QCheckBox->
  plot.set_point_compare_enabled, Clear Points, "Use P1–P2 as Analysis Window"->analysisWindowRequested signal, table. Connects
  plot.cursorPointsChanged->refresh. main_window: 7th tab "Point Compare", analysisWindowRequested->_on_cursor_window (set axis xmin/xmax+replot).
- SESSION (inc9): main_window_vm KEPT save_session/load_session sigs (tests depend). ADDED capture_working_state(x_column=,y_columns=,
  secondary_y_columns=) folds top-level limit_lines+engineering_notes+axis selection into plot_profiles[0] via normalise_plot_profile
  (Qt keeps these top-level; session format is per-profile). ADDED restore_session(path): load_session + pull profile[0] limits/notes
  into state + data_loading.load_file(session.file_path) + maths_channels.recalculate() + reload runs via runs_comparison.add_run(
  run_meta.filepath, override name/enabled/colour) + active_run_index. Returns payload={x_column,y_columns,secondary_y_columns}+warnings[].
  main_window: File menu Save Session(Ctrl+S)/Load Session(Ctrl+L); save_session() captures then vm.save_session; load_session()
  vm.restore_session then _apply_loaded_session refreshes ALL panels + axis_panel.apply_selection. Added qt_file_dialogs import.
- Tests: +4 service (CursorServiceTests)=35, +13 viewmodel (Cursor x4 + session capture/restore/round-trip/missing/warns x5 + runs CRUD)=76,
  +17 Qt (AxisSelectionPanel x6, PlotWorkspaceParity x5, CursorComparePanel x6)=47. Total 147->176.
  Count history: Ph1=18, Ph2=49, Ph3=86, inc1=95, inc2=106, inc3=111, inc4=125, inc5+6=147, inc7+8+9=176.
- Verified: 176 pass; offscreen MainWindow E2E (secondary axis=2 axes + LP label + Line+Markers; cursor lock 2 pts->delta->
  use-as-window sets xmin/xmax; session save->restore fresh window->x/y/secondary/limits/notes/runs restored) OK; both apps import.
- GOTCHA: widget-method tests DON'T exercise main_window._on_generate_plot — the y_cols NameError only showed in MainWindow smoke.
  Always smoke-test MainWindow handler paths, not just widget methods.

## Done — docs rewrite + core/ reorg + GitHub sync
- README.md + ARCHITECTURE.md REWRITTEN for Qt-only architecture (no Tkinter/mixin/run_app references except 1 intentional
  historical pointer to MIGRATION_PROGRESS.md). Layers doc: qt_app->viewmodels->services->domain->core.
- STRUCTURAL CHANGE: moved 5 shared support modules into NEW test_data_analyser/core/ subpackage:
  config.py, data_io.py, filters.py, settings_manager.py, utils.py (via git mv, history preserved). core/__init__.py added.
  __init__.py + __main__.py STAY at package root (Python requires them there; __main__ launches Qt).
- Import paths CHANGED: `from ..config` -> `from ..core.config` (services/, viewmodels/, qt_app/ top-level),
  `from ...config`/`...filters` -> `...core.config`/`...core.filters` (qt_app/widgets/), `from .config` -> `from .core.config`
  (package __init__.py). INTERNAL core/ cross-imports unchanged: core/data_io.py `from .config import NUMERIC_EXTRACT_RE`,
  core/filters.py `from .data_io import numeric_series` (siblings now). 16 external import sites updated. Tests import
  domain/services/viewmodels/qt_app only — NONE needed changes.
- New package root layout: test_data_analyser/{__init__.py, __main__.py, core/, domain/, services/, viewmodels/, qt_app/}.
- Verified: 176 tests pass; `import test_data_analyser` (v1.00) + MainWindow + all 5 core modules import clean.
- GITHUB: origin = github.com/DiegoDagostino01/Test-Data-Analyser.git, branch main. Committed b4d3d54 (94 files,
  +8831/-7250) "Migrate to PySide6 architecture; remove Tkinter UI; reorganise into core/" + pushed. Working tree clean,
  main...origin/main in sync. (Repo previously had only 01d335c "Initial commit" — this commit captures the whole migration.)
- DELETED 18 legacy Tk files (user-approved "Delete the full Tkinter UI"): gui.py, gui_base.py, analysis.py, limits.py,
  plotting.py, calculated_channels.py, raw_data.py, raw_data_editor.py, multi_run.py, cursor_tools.py, engineering_notes.py
  (TOP-LEVEL one; domain/engineering_notes.py KEPT), data_loading.py (TOP-LEVEL; viewmodels/data_loading_vm.py KEPT),
  settings_window.py, widgets.py (TOP-LEVEL; qt_app/widgets/ KEPT), profile_state.py, label_profiles.py, main.py, run_app.py.
- __main__.py REPOINTED: now `from .qt_app.main_qt import main; raise SystemExit(main())` so `python -m test_data_analyser`
  launches Qt. Verified: 176 tests still pass; QT imports OK; `python -m test_data_analyser` enters Qt event loop.
- KEPT shared core: domain/, services/, viewmodels/, qt_app/, config.py, data_io.py, filters.py, utils.py, settings_manager.py,
  __init__.py, __main__.py, run_qt_app.py. Pre-delete due diligence: grepped domain/services/viewmodels/qt_app + tests +
  config/data_io/filters/utils/settings_manager — NONE import the deleted Tk modules (only string matches like dict keys).
- Entry points now: `python run_qt_app.py` OR `python -m test_data_analyser` OR `python -m test_data_analyser.qt_app.main_qt`.
- MIGRATION_PROGRESS.md updated: status=Phases 1-5 complete + Tk removed, architecture diagram single-UI, structure tree
  (no Tk files), how-to-run (no run_app.py), Definition of done all ✅.

## Done — UI cleanup pass (post-migration usability)
- SETTINGS PATH BUG FIXED: after core/ reorg, settings_manager.py resolved settings.json to the PACKAGE dir
  (parent.parent) instead of repo root, orphaning the git-tracked root settings.json (user's font_size_title=11
  was ignored, a stale package copy with =14 was live+untracked). Fix: `repo_root = Path(__file__).resolve().
  parent.parent.parent` (core->test_data_analyser->repo root). Deleted orphan test_data_analyser/settings.json.
  Tests unaffected (they pass explicit temp settings_path).
- NEW test_data_analyser/qt_app/widgets/no_wheel_combo_box.py: NoWheelComboBox(QComboBox) overrides wheelEvent->
  event.ignore() (mouse-wheel can't change selection). Applied to: axis panel x_combo + plot_kind_combo, limits
  panel type/applies/colour combos, settings_dialog combo editor. Removed now-unused QComboBox imports.
- NEW test_data_analyser/qt_app/adapters/qt_widget_helpers.py: last_data_directory(mgr)/remember_data_directory(
  mgr,filename) — defensive (mgr may be None, never raises). Persist parent dir of opened file in settings
  data_import.last_data_directory. Used by data_file_panel + runs_comparison_panel _add_run.
- SETTINGS: added DEFAULT_SETTINGS["data_import"]["last_data_directory"]="" (merge-with-defaults auto-adds to
  existing settings.json on load). qt_file_dialogs.open_data_file gained `initial_dir=""` 2nd param (back-compat).
- AXIS PANEL regrouped: heading "Plot Controls" + QScrollArea(widgetResizable) holding 4 QGroupBox sections
  (Axes & Channels / Plot Options / Analysis Window / Filter / FFT); Generate Plot(primary)+FFT buttons PINNED
  below scroll. All attribute names preserved (x_combo,y_list,secondary_y_list,plot_kind_combo,xmin/xmax_edit,
  filter_check,cutoff/order_edit,generate/fft_button) so existing tests + main_window refs still work. Added
  QGroupBox style to theme.py (Eaton dark-blue titles).
- HEADER LOGO restored: main_window._build_logo_label() decodes EATON_LOGO_PNG_BASE64 (core/config) via base64+
  QPixmap.loadFromData, scaledToHeight(38). Returns Optional[QLabel]; None->text-only fallback. Added to
  _build_header left of title box. QPixmap import only in main_window (qt layer).
- SPLITTER/tab layout: analysis tab controls are a QTabBar above the plot in main_window.right_panel; the lower
  panel is a QStackedWidget (lower_tabs alias) inside an EatonPanel below the plot and is controlled by lower_tab_bar.
  right_splitter (vertical) setChildrenCollapsible(False), plot_workspace.setMinimumHeight(260),
  lower_tabs.setMinimumHeight(150), setSizes([520,260]), stretch 3:2. Stored self.right_splitter.
- Follow-up UI cleanup: Maths Channels and Requirements/Limits dense content are wrapped in QScrollArea with non-collapsible splitters so shrinking the bottom pane scrolls instead of squashing fields. LimitsPanel.summary_panel is shown as its own "Margin to Limit" tab. Header labels explicitly use EATON_HEADER_BLUE background to avoid white text on white label backgrounds.
- Session dialogs now remember their own folder via general_ui.last_session_directory. MainWindow.save_session/load_session pass qt_widget_helpers.last_session_directory into qt_file_dialogs and remember the selected parent with remember_session_directory.
- Plot-controls cleanup: AxisSelectionPanel has equal primary/secondary Y list sizing and channel group filtering via core.utils.classify_channel_name, but plot-label and axis-limit editing were removed from the left panel because Matplotlib Figure Options owns those visual axis edits. MatplotlibCanvas uses LegendAwareNavigationToolbar to append a Figure Options "Legend" tab; PlotWorkspace can switch legend display between the right-side Qt Legend panel (default) and an in-graph Matplotlib legend, persisted as plot_profile.legend.display_mode. Toolbar.save_figure runs an export-preparer context manager (PlotWorkspace._legend_export_context) that, in panel mode, temporarily draws the legend onto the axes so saved PNGs include it, then removes it and redraws.
- Axis padding option (Edit > Settings > "Axis Padding" tab): axis_scaling.{pad_x_axis,pad_x_percent,pad_y_axis,pad_y_percent} (defaults True/5/True/5). PlotWorkspace._apply_axis_padding applies axes.margins(x,y) only when auto_fit_axes (disabled axis => margin 0; matplotlib default was 5%). FIXED latent settings_dialog bug: _value_for used QComboBox but it wasn't imported (NameError on save) — now imported; covered by SettingsDialogTests.
- Session restore now re-renders the plot: capture_working_state takes generated:bool -> profile["generated"] (PlotProfile.generated already round-trips). MainWindow tracks self._plot_generated (True after _on_generate_plot success, False on _on_file_loaded), passes it into save, and _apply_loaded_session calls _restore_generated_plot(profile) which re-runs _generate_plot when profile["generated"]. Maths channels / limit_lines / engineering_notes already persisted via build_session + capture_working_state(state.limit_lines/engineering_notes into profile) and restore_session pulls them back into state; panels refresh in _apply_loaded_session. Covered by MainWindowSessionRestoreTests (UI round trip) + VM generated-flag test.
- Figure Options appearance persists across sessions: PlotWorkspace.current_axis_appearance() reads live axes title/xlabel/ylabel/xlim/ylim (+ twin y2) -> dict (auto_fit_axes=False so exact view restores). MainWindow.save_session captures it (only when _plot_generated) into capture_working_state title/x_label/y_label/secondary_y_label/axis_limits/auto_fit_axes. _restore_generated_plot builds appearance dict from profile and passes to _generate_plot(appearance) -> _appearance_kwargs (parses limit strings via _parse_limit) -> generate_plot kwargs. Covered by test_figure_options_appearance_persists_across_session + PlotWorkspace current_axis_appearance tests.
- Follow-up visible correction: lower analysis panels are back in a real QTabWidget notebook (not detached QTabBar above plot); AxisSelectionPanel shows group header rows inside both Y lists when Channel group=All; PlotWorkspace has a persistent Qt legend table panel to the right of the canvas; AxisSelectionPanel has vertical Expanding size policy and MainWindow left rail stretches it in a QScrollArea.




- Tests: +10 in test_qt_adapters.py (NoWheelComboBoxTests x2, OpenDataFileInitialDirTests x2 [patch module-level
  qt_file_dialogs.QFileDialog with fake], MainWindowLayoutTests x3 [SettingsManager(temp path)], 
  LastDataDirectoryHelperTests x3 [NOT skipped — qt_widget_helpers is PySide6-free]). Total 176->186, all pass.
- GOTCHA: pre-existing static-checker noise in test_qt_adapters (Qt.Horizontal/Qt.DisplayRole short enums,
  self.state.df None) is NOT from this pass. New Optional narrowing: `assert logo is not None`; stub wheel event
  needs `# type: ignore[arg-type]`.
- Verified: 186 pass offscreen; MainWindow shows (7 tabs, logo pixmap 38px non-null, splitter not collapsible);
  settings.json resolves to repo root w/ font_size_title=11 + last_data_directory key merged. NO PySide6 imports
  outside qt_app (29 import sites all under qt_app/). Eaton colours unchanged.
