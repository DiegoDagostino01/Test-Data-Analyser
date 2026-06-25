# Test Data Analyser — Update 1.02.02 Implementation Plan

> **Target version:** V1.02.01
> **Predecessor:** V1.02.01 (Raw Data table editing, row/column actions, undo, resizing)
> **Theme:** *Power user editing + bulk workflows + polish*
> **Out of scope for this update:** Tier 3 features (report generation, region selection, FFT view, multi-cursor compare) — deferred to V1.02.03 or V1.03.00

---

## 1. Overview & Goals

V1.02.02 builds directly on the Raw Data editing foundation from V1.02.01. It introduces Excel-style productivity features, makes the dataset editor genuinely usable for hand-entered manual sessions, and adds bulk workflow features that match how Eaton Aerospace test campaigns actually run.

**Headline features:**

- 📋 **Copy / Paste / Cut** cell ranges in the Raw Data table (Excel-compatible TSV)
- 🔍 **Find & Replace** (`Ctrl+F` / `Ctrl+H`) with regex and scope toggles
- ↕️ **Sort & Filter** rows in the Raw Data view
- 🖱️ **Drag-to-fill** and "Fill down" context actions
- 📁 **Recent Files / Sessions** menus and **drag-and-drop** file open
- 💾 **Auto-save** wired up (the setting already exists)
- 🔁 **Batch Run Import** from a folder with regex run-name extraction
- 📏 **Limit Templates** save/load JSON per test spec
- 🎯 **Peak Detection** as a right-click plot action that adds annotations
- 🎨 Polish: keyboard shortcut cheat sheet in Help, plot tab drag-to-reorder, reset axis appearance button

---

## 2. Architecture Compliance — Non-Negotiable

Every step in every phase **must** respect these rules. They come straight from `ARCHITECTURE.md`:

### Dependency direction (only ever downward)

```
qt_app/      PySide6 UI — main window, panels, theme, adapters
    │
viewmodels/  UI-independent coordinators over AppState + services
    │
services/    pure engineering / data logic (numpy/pandas/Matplotlib OK)
    │
domain/      framework-independent dataclasses (no UI, no logic)
    │
core/        shared infrastructure (config, data I/O, filters, settings, utils)
```

### Hard rules

- ✅ **Only `qt_app/` imports PySide6.** Everything else stays UI-free.
- ✅ `domain/`, `services/`, and `viewmodels/` **must never** import a UI toolkit, open a dialog, or show a message box.
- ✅ Services and viewmodels return values or a structured `OperationResult` (`services/results.py`).
- ✅ `plot_render_service` may import Matplotlib, but **canvas embedding stays in adapters**.
- ✅ Architecture boundary tests in `tests/test_architecture_boundaries.py` must keep passing.
- ✅ Headless tests must all keep passing: `python -m unittest discover -s tests`.

---

## 3. User Preferences (from memory)

These are locked-in for the whole update:

- 🔪 **Aggressive duplicate removal** — if existing helpers cover it, reuse rather than re-implement.
- 📐 **Follow `ARCHITECTURE.md` order** — each step lands in the correct layer.
- 🧱 **Extracted mixins are the source of truth** — don't reintroduce monolithic classes.
- ⚡ **Efficiency improvements welcome** — refactor for clarity while implementing.
- 🎨 **Pure plotting logic stays separate** from canvas / UI wiring.
- 🏷️ **Eaton branding unchanged** — colours, header, logo, version string handling.
- 📦 **Packaging deferred** — focus on the Python source / tests.

---

## 4. Phase Map

| Phase | Theme | Complexity | Depends On |
|------|------|------|------|
| 1 | Foundation Polish | Small | — |
| 2 | Raw Data Sorting & Filtering | Small-Medium | Phase 1 |
| 3 | Raw Data Copy / Paste / Cut | Medium | Phase 2 |
| 4 | Find & Replace | Medium | Phase 3 |
| 5 | Drag-to-Fill & Bulk Fill | Medium | Phase 3 |
| 6 | Bulk Workflows (Batch import, Limit templates, Peak detection) | Medium-Large | Phase 1 |
| 7 | Final Polish | Small | Phase 6 |

Each phase ends with a green test suite and an updated `ARCHITECTURE.md` + `VERSION_HISTORY.md`.

---

# Phase 1 — Foundation Polish

**Goal:** Small wins that improve discoverability and daily ergonomics. None require new viewmodel surface area beyond minor settings reads.

## 1.1 Recent Files / Recent Sessions menus

### Files affected

- `test_data_analyser/core/settings_manager.py`
  - Add `recent_files: list[str]` and `recent_sessions: list[str]` under a new `recent` section in `DEFAULT_SETTINGS`. Cap at 10 entries each.
- `test_data_analyser/viewmodels/main_window_vm.py`
  - Add helpers: `recent_files()`, `recent_sessions()`, `register_recent_file(path)`, `register_recent_session(path)`. Trim duplicates, keep most-recent-first.
- `test_data_analyser/qt_app/main_window.py`
  - Rebuild the File ribbon group to include a "Recent" dropdown button (or split-button) — populated from the viewmodel.
  - Hook `_on_file_loaded` and `save_session` / `load_session` success paths to call `register_recent_*`.

### Implementation steps

- [ ] **Step 1.1.1** — Extend `DEFAULT_SETTINGS` in `core/settings_manager.py` with a `recent` section. No `available_*` list needed.
- [ ] **Step 1.1.2** — Add `recent_files()` / `recent_sessions()` / `register_recent_file()` / `register_recent_session()` to `MainWindowViewModel`. Each `register_*` reads the current list, removes the path if present, prepends it, trims to 10, then saves through `SettingsManager`.
- [ ] **Step 1.1.3** — Wire the calls into `_on_file_loaded` and `save_session` / `load_session` (only on success). Use the resolved absolute path.
- [ ] **Step 1.1.4** — Add a "Recent" `QPushButton` with a `QMenu` to the FILE ribbon group. Populate the menu on `aboutToShow` so it always reflects the latest list. Skip entries whose file no longer exists (don't remove yet — just disable).
- [ ] **Step 1.1.5** — Selecting a recent file triggers `data_panel.load_file(path, None)` (Excel/CSV path), or `_load_session_path(path)` for sessions.

### Tests to add

- `tests/test_viewmodels.py`
  - `RecentItemsTests` — register 12 files, verify cap at 10 and order. Register an existing entry and verify it moves to the front. Confirm `SettingsManager.save` was called.
- `tests/test_qt_adapters.py`
  - In `MainWindowLayoutTests` add `test_recent_files_menu_populates_from_viewmodel` — register entries via the VM, open the recent menu, assert action labels match.

### Acceptance criteria

- ✅ Opening or saving a file updates the corresponding recent list.
- ✅ The "Recent" menu shows up to 10 entries, most recent first.
- ✅ Missing files are visually disabled but not removed automatically.
- ✅ All existing tests still pass.

---

## 1.2 Drag-and-drop file open

### Files affected

- `test_data_analyser/qt_app/main_window.py`
  - Override `dragEnterEvent` and `dropEvent` on `MainWindow`. Accept `text/uri-list` drops with a `.csv` / `.xlsx` / `.xls` / `.json` (session) extension.

### Implementation steps

- [ ] **Step 1.2.1** — `MainWindow.__init__` calls `self.setAcceptDrops(True)`.
- [ ] **Step 1.2.2** — Add `dragEnterEvent`: accept when `event.mimeData().hasUrls()` and at least one URL is a local file with a supported extension.
- [ ] **Step 1.2.3** — Add `dropEvent`: for the first matching URL, call `data_panel.load_file(path, None)` for data files, or `_load_session_path(path)` for `.json` sessions. Multi-file drops only process the first file (and the others can become runs in Phase 6's Batch Import — note this in the docstring as a future hook).
- [ ] **Step 1.2.4** — Update the status bar with `"Opened via drag-and-drop: <path>"`.

### Tests to add

- `tests/test_qt_adapters.py`
  - `test_drag_and_drop_data_file_calls_data_panel` — construct `MainWindow`, build a fake `QDropEvent` (or call `dropEvent` with a stubbed `QMimeData`), assert `data_panel.load_file` is called.

### Acceptance criteria

- ✅ Dragging a `.csv` / `.xlsx` onto the window opens it as the main data file.
- ✅ Dragging a `.json` session opens it as a session.
- ✅ Unsupported extensions are ignored without exceptions.

---

## 1.3 Keyboard shortcut cheat sheet in Help

### Files affected

- `test_data_analyser/qt_app/widgets/help_dialog.py`
  - Add a new topic `"Keyboard Shortcuts"` between `"Typical Workflow"` and `"File Ribbon"`.

### Implementation steps

- [ ] **Step 1.3.1** — Add the topic body to `HELP_PAGE_BODIES`. Cover existing shortcuts (`Ctrl+O`, `Ctrl+N`, `Ctrl+S`, `Ctrl+L`), Raw Data shortcuts (`Enter`, `Esc`), and reserve a section "Coming in this release" listing the Phase 3-5 shortcuts (`Ctrl+C`, `Ctrl+V`, `Ctrl+X`, `Ctrl+F`, `Ctrl+H`).
- [ ] **Step 1.3.2** — Update the topic-count assertion in `tests/test_qt_adapters.py::HelpDialogTests::test_initial_page_selected` (currently expects 14 — bump to 15).

### Tests to add

- `tests/test_qt_adapters.py`
  - `test_keyboard_shortcuts_topic_lists_known_shortcuts` — select the Keyboard Shortcuts topic and assert `"Ctrl+O"`, `"Ctrl+S"`, `"Enter"`, `"Esc"` appear in the rendered text.

### Acceptance criteria

- ✅ Help dialog has a Keyboard Shortcuts topic, searchable from the search box.
- ✅ All known shortcuts are listed.
- ✅ Existing Help tests pass with the updated topic count.

---

## 1.4 Auto-save wiring

The `auto_save_enabled` and `auto_save_interval_minutes` settings exist in `DEFAULT_SETTINGS` but nothing reads them. Wire them up properly.

### Files affected

- `test_data_analyser/viewmodels/main_window_vm.py`
  - Add `auto_save_due()` (returns bool given a last-save timestamp), `auto_save_target_path()` (uses current session path if set, else falls back to `<root_file_directory>/autosave.json`).
- `test_data_analyser/qt_app/main_window.py`
  - Start a `QTimer` based on `auto_save_interval_minutes`. On timeout call the VM helpers and `save_session(path)` silently. Show a brief status bar message on success; log to status bar on failure (no modal dialogs).

### Implementation steps

- [ ] **Step 1.4.1** — Add the VM helpers. `auto_save_due` is a pure function (time-in / time-out, integer minutes).
- [ ] **Step 1.4.2** — In `MainWindow.__init__` create `self._autosave_timer = QTimer(self)` and connect to `_on_autosave_tick`.
- [ ] **Step 1.4.3** — Read the settings at startup and after the Settings dialog is dismissed; restart the timer.
- [ ] **Step 1.4.4** — Skip autosave when there is no `df` loaded, when nothing is dirty (`self.vm.state.is_dirty is False`), or when the user is currently editing a cell.
- [ ] **Step 1.4.5** — On a successful autosave, set the status bar to `"Auto-saved at HH:MM:SS"`. On failure, set `"Auto-save failed: <message>"`.

### Tests to add

- `tests/test_viewmodels.py`
  - `AutoSaveSchedulingTests` — `auto_save_due` returns False before the interval elapses, True after.
- `tests/test_qt_adapters.py`
  - `test_autosave_timer_skips_when_no_data` — construct `MainWindow`, trigger `_on_autosave_tick`, assert no `save_session` call.
  - `test_autosave_timer_writes_when_dirty` — load data, set dirty, trigger tick, assert file appears at the expected autosave path.

### Acceptance criteria

- ✅ Auto-save runs at the configured interval when there is dirty data.
- ✅ Auto-save does nothing when there is no data or no unsaved changes.
- ✅ Settings dialog changes take effect without restarting the app.

---

## Phase 1 wrap-up

- [ ] Update `ARCHITECTURE.md` "Recent enhancements" with bullets for recent menus, drag-and-drop, help shortcuts topic, auto-save.
- [ ] Add an entry to `VERSION_HISTORY.md` for `V1.02.02 – Phase 1`.
- [ ] Run `python -m unittest discover -s tests`. **Must be green.**

---

# Phase 2 — Raw Data Sorting & Filtering

**Goal:** Make the Raw Data table navigable for the large datasets you actually work with (think: 3,600 data points across 44 serial numbers). Sort and per-column filtering, while keeping edits aligned with the source dataframe.

> ⚠️ **Important:** Sorting is a *display* feature. The underlying dataframe order must not change. Edits must still map back to the correct dataframe row.

## 2.1 Sorting in the displayed Raw Data view

### Files affected

- `test_data_analyser/core/naming.py`
  - Reuse `natural_sort_key`.
- `test_data_analyser/services/raw_data_service.py`
  - Add `sort_display_frame(frame, column, ascending)` — returns a new dataframe sorted by the given column using natural sort for non-numeric columns and numeric sort otherwise. Preserves the original dataframe index as a hidden column so edits can map back.
- `test_data_analyser/viewmodels/raw_data_vm.py`
  - Extend `display_frame()` to accept `sort_column` and `sort_ascending`. Update the returned payload to include the sort state.
- `test_data_analyser/qt_app/adapters/editable_raw_data_model.py`
  - When rows are sorted, the row index passed to `cellEdited.emit` must remain the *dataframe* index, not the displayed row. The model already keeps a `_df`; ensure mapping goes through `self._df.index[row]`.
- `test_data_analyser/qt_app/widgets/raw_data_panel.py`
  - Click a column header → sort by it (toggle asc/desc/none on repeated clicks). Update the visible header indicator (`▲` / `▼`).

### Implementation steps

- [ ] **Step 2.1.1** — Add `sort_display_frame` to `raw_data_service`. Numeric columns sort numerically; text columns sort via `natural_sort_key`. NaN values sink to the bottom regardless of direction.
- [ ] **Step 2.1.2** — Add `_sort_state: tuple[str, bool] | None` to `RawDataPanel`. Connect `horizontalHeader().sectionClicked` (only when **not** in edit mode) to a cycler: `None → asc → desc → None`.
- [ ] **Step 2.1.3** — Update `RawDataViewModel.display_frame()` signature: add `sort_column: str | None = None`, `sort_ascending: bool = True`. Apply via `sort_display_frame` after filtering, before truncation.
- [ ] **Step 2.1.4** — In `RawDataPanel.refresh()`, pass the sort state through.
- [ ] **Step 2.1.5** — Update the header text to append `" ▲"` / `" ▼"` to the sorted column.

### Tests to add

- `tests/test_services.py`
  - `RawDataSortTests` — sort a numeric column ascending/descending; sort a text column with natural order (`TC2`, `TC10`); NaN sinks; original dataframe index preserved in the result.
- `tests/test_viewmodels.py`
  - `test_display_frame_applies_sort` — feed a state with a known df, request a sort, confirm the returned frame order.
- `tests/test_qt_adapters.py`
  - `test_clicking_column_header_cycles_sort` — three clicks → asc, desc, cleared; header shows the correct indicator.

### Acceptance criteria

- ✅ Sort works in display mode but is disabled in `Edit dataset` mode.
- ✅ Editing a sorted cell writes back to the correct dataframe row.
- ✅ Natural sort for `TC1`, `TC2`, `TC10`.

---

## 2.2 Per-column quick filter row

### Files affected

- `test_data_analyser/services/raw_data_service.py`
  - Add `filter_display_frame(frame, filters: dict[str, str])` — case-insensitive substring match for text, numeric range parser `>10`, `<5`, `1..5`, `=3`.
- `test_data_analyser/viewmodels/raw_data_vm.py`
  - Extend `display_frame()` again with `column_filters: dict[str, str] | None = None`.
- `test_data_analyser/qt_app/widgets/raw_data_panel.py`
  - Add a "Filter" toggle button next to the existing controls. When on, show a row of `QLineEdit`s above the table header, one per visible column. Updating any field triggers `refresh()`.

### Implementation steps

- [ ] **Step 2.2.1** — Implement `filter_display_frame` with a small parser:
  - `">N"` / `"<N"` / `">=N"` / `"<=N"` / `"=N"` → numeric comparison
  - `"a..b"` → numeric range inclusive
  - Otherwise treat as case-insensitive substring on the stringified value
  - Empty filter → ignore the column
- [ ] **Step 2.2.2** — Wire `column_filters` into the VM and panel. Persist the active filter dict on the panel so it survives a refresh.
- [ ] **Step 2.2.3** — A clear-all button next to the toggle resets every filter.

### Tests to add

- `tests/test_services.py`
  - `RawDataFilterTests` — substring filter, numeric `>`, `<`, range, equality; empty filter is a no-op.
- `tests/test_qt_adapters.py`
  - `test_filter_row_visible_only_when_enabled`
  - `test_filter_row_updates_table_rows`

### Acceptance criteria

- ✅ Filtering reduces visible rows but does not delete data.
- ✅ Filter + sort + analysis window + blank-row drop compose correctly (apply in this order: blank drop → analysis window → column filter → sort → row limit).

---

## Phase 2 wrap-up

- [ ] Update `ARCHITECTURE.md` — mention sort and filter under "Recent enhancements" → Raw Data.
- [ ] Update `VERSION_HISTORY.md`.
- [ ] Run the full test suite.

---

# Phase 3 — Raw Data Copy / Paste / Cut

**Goal:** Cells, rows, columns, and rectangular blocks can be copied to / pasted from the system clipboard in Excel-compatible TSV. Cut clears the source cells. All operations integrate with the existing dataset undo stack.

> ⚠️ This is the highest-impact feature in V1.02.02. Edit-mode and view-mode have different semantics — get edit-mode right first.

## 3.1 Clipboard service

### Files affected

- New: `test_data_analyser/services/clipboard_service.py`
  - Pure functions:
    - `selection_to_tsv(values: list[list[object]]) -> str`
    - `tsv_to_values(text: str) -> list[list[str]]`
    - `coerce_pasted_block(values, column_specs) -> tuple[list[list[object]], list[str]]` — applies `dataset_service.coerce_cell_value` per target column; returns coerced values + warnings.

### Implementation steps

- [ ] **Step 3.1.1** — Implement `selection_to_tsv`. Use `\t` between columns and `\n` between rows. Handle `None` / `NaN` as empty strings.
- [ ] **Step 3.1.2** — Implement `tsv_to_values`. Split on `\r\n` / `\n`, then on `\t`. Strip a trailing empty row.
- [ ] **Step 3.1.3** — Implement `coerce_pasted_block`. For each cell, apply the matching column's `ColumnSpec` coercion. Collect non-fatal warnings (e.g., "B3: 'abc' kept as text in numeric column").

### Tests to add

- `tests/test_services.py`
  - `ClipboardServiceTests` — round-trip TSV; mixed shapes; coercion of numeric vs text columns; warnings collected.

---

## 3.2 Dataset viewmodel — block edit method

### Files affected

- `test_data_analyser/viewmodels/dataset_vm.py`
  - New methods:
    - `copy_block(row_indices, channel_ids) -> str` — returns TSV.
    - `cut_block(row_indices, channel_ids) -> OperationResult` (payload = TSV). Replaces source cells with NaN (numeric) or blank (text). Pushes one undo snapshot.
    - `paste_block(top_row, left_channel_id, text) -> OperationResult`. Parses TSV, walks down/right starting at the anchor, expands the dataframe (extra rows/columns) when needed using existing `add_row` / `add_column` helpers, applies coerced values, pushes one undo snapshot.

### Implementation steps

- [ ] **Step 3.2.1** — `copy_block` reads through the channel registry → display names → df values. Use `clipboard_service.selection_to_tsv`.
- [ ] **Step 3.2.2** — `cut_block` calls `copy_block`, then sets each cell to the blank value via existing `set_cell`. Wrap the whole operation in a single undo snapshot (extend the controller to support a manual snapshot scope).
- [ ] **Step 3.2.3** — `paste_block`:
  - Parse TSV via `clipboard_service.tsv_to_values`.
  - Compute target shape, expand df if needed (new rows: `add_row`; new columns: `add_column` named `"Column N"` with auto-detected numeric/text type from the pasted values).
  - Coerce + write through `set_cell`.
  - Push **one** undo snapshot for the whole paste.

### Tests to add

- `tests/test_viewmodels.py`
  - `DatasetClipboardTests`:
    - `test_copy_block_returns_tsv`
    - `test_cut_block_clears_cells_and_returns_tsv`
    - `test_paste_block_expands_df_when_needed`
    - `test_paste_block_single_undo_step`
    - `test_paste_block_warns_on_invalid_numeric_text`

---

## 3.3 Qt panel — keyboard wiring

### Files affected

- `test_data_analyser/qt_app/widgets/raw_data_panel.py`
  - Install `QShortcut`s on `self.table` for `QKeySequence.Copy`, `QKeySequence.Cut`, `QKeySequence.Paste`.
  - Routes:
    - **Edit dataset mode** → call `dataset_vm.copy_block` / `cut_block` / `paste_block`.
    - **View mode** → copy only (cut and paste disabled with a status bar message).
  - After cut/paste, call `refresh_dataset()` and emit `datasetChanged`.

### Implementation steps

- [ ] **Step 3.3.1** — Helper `_current_selection_block() -> tuple[list[int], list[str]]` — returns (sorted row indices, sorted channel ids) of the current rectangular selection. If non-rectangular, fall back to the bounding rectangle of the selection.
- [ ] **Step 3.3.2** — Helper `_anchor_cell() -> tuple[int, str] | None` — top-left of the current selection.
- [ ] **Step 3.3.3** — Wire `Ctrl+C`, `Ctrl+X`, `Ctrl+V` through to the VM. Use `QGuiApplication.clipboard().setText(tsv)` for copy/cut, `clipboard().text()` for paste.
- [ ] **Step 3.3.4** — Update the status bar with the operation summary.

### Tests to add

- `tests/test_qt_adapters.py`
  - `RawDataClipboardTests`:
    - `test_copy_selection_writes_tsv_to_clipboard`
    - `test_cut_selection_clears_and_pushes_undo`
    - `test_paste_at_anchor_expands_table`
    - `test_copy_works_in_view_mode_but_paste_does_not`

### Acceptance criteria

- ✅ `Ctrl+C` / `Ctrl+V` / `Ctrl+X` work between Eaton's Test Data Analyser and Excel in both directions.
- ✅ Paste auto-expands the dataset when the pasted block exceeds the current shape.
- ✅ One paste = one undo step.
- ✅ View mode copy works; cut/paste does not.

---

## Phase 3 wrap-up

- [ ] Update `ARCHITECTURE.md`: add `services/clipboard_service.py` to the `services/` list and mention paste/cut under Raw Data.
- [ ] Update Help dialog "Keyboard Shortcuts" topic — un-stub the Phase 3 shortcuts.
- [ ] Update `VERSION_HISTORY.md`.
- [ ] Run the full test suite.

---

# Phase 4 — Find & Replace

**Goal:** `Ctrl+F` finds, `Ctrl+H` finds and replaces. Scoped to the Raw Data tab. Optional regex. Optional "search displayed view only" vs "search full dataset". Integrates with the dataset undo stack.

## 4.1 Service: search engine

### Files affected

- New: `test_data_analyser/services/find_replace_service.py`
  - Pure helpers:
    - `find_matches(df, query, *, regex, case_sensitive, columns) -> list[Match]` — `Match` is `(row, column_name, value_str)`.
    - `apply_replacements(df, matches, replacement, *, regex) -> ReplacementSummary` — returns counts + per-column warnings.

### Implementation steps

- [ ] **Step 4.1.1** — Compile the query once (string or regex). For numeric columns, search the *string* representation so users can match "1.5" without worrying about dtypes.
- [ ] **Step 4.1.2** — `apply_replacements` writes through a coercion function (callable injected by the VM) so numeric columns get coerced and warnings are collected for invalid replacements.

### Tests to add

- `tests/test_services.py`
  - `FindReplaceServiceTests`:
    - substring, regex, case-sensitive
    - column scoping
    - replacement coercion + warnings

---

## 4.2 Viewmodel

### Files affected

- `test_data_analyser/viewmodels/raw_data_vm.py`
  - Add `find(query, *, regex, case_sensitive, columns, search_full_dataset)`. When `search_full_dataset` is False, use the currently displayed frame; otherwise use `state.df`.
  - Add `replace_all(query, replacement, ...)`. Push one undo snapshot.

### Implementation steps

- [ ] **Step 4.2.1** — Reuse `find_replace_service`. Translate display frame ↔ dataframe row indices the same way Phase 2 sort does (via the original index preserved on the display frame).
- [ ] **Step 4.2.2** — `replace_all` integrates with the dataset undo stack — one snapshot for the entire replacement run.

### Tests to add

- `tests/test_viewmodels.py`
  - `FindReplaceVMTests`:
    - find on full dataset vs displayed view
    - replace_all single undo step
    - regex round-trip

---

## 4.3 Qt panel — dialog

### Files affected

- New: `test_data_analyser/qt_app/widgets/find_replace_dialog.py`
  - Non-modal `QDialog` parented to `MainWindow`. Fields: query, replacement, regex check, case-sensitive check, "Search full dataset" check, "Find Next" / "Replace" / "Replace All" / "Close" buttons.
- `test_data_analyser/qt_app/widgets/raw_data_panel.py`
  - `Ctrl+F` opens the dialog in find-only mode (replacement disabled).
  - `Ctrl+H` opens it with replacement enabled.
- Dialog talks to the panel's `RawDataViewModel` directly. Highlight the current match using `table.setCurrentIndex`.

### Implementation steps

- [ ] **Step 4.3.1** — Dialog skeleton + theme application via existing `theme.build_stylesheet` palette.
- [ ] **Step 4.3.2** — "Find Next" cycles through matches, wrapping at the end.
- [ ] **Step 4.3.3** — "Replace" replaces the current match and advances. "Replace All" replaces all + shows summary in the status bar.
- [ ] **Step 4.3.4** — Closing the dialog clears any temporary highlighting.

### Tests to add

- `tests/test_qt_adapters.py`
  - `FindReplaceDialogTests`:
    - `test_find_next_navigates_matches`
    - `test_replace_all_shows_summary`
    - `test_dialog_opens_in_find_only_for_ctrl_f`
    - `test_dialog_opens_with_replace_for_ctrl_h`

### Acceptance criteria

- ✅ `Ctrl+F` / `Ctrl+H` open the dialog with correct mode.
- ✅ Replace All on a numeric column with non-numeric input keeps the cell editable as text and reports a warning.
- ✅ One Replace All run = one undo step.

---

## Phase 4 wrap-up

- [ ] Update `ARCHITECTURE.md` and `VERSION_HISTORY.md`.
- [ ] Update Help "Keyboard Shortcuts" topic.
- [ ] Run the full test suite.

---

# Phase 5 — Drag-to-Fill & Bulk Fill

**Goal:** Excel-style fill handle (a small square at the bottom-right of the active selection) lets the user drag to extend a constant or linear series. A right-click context menu adds "Fill down from selection" and "Fill across from selection".

## 5.1 Service: series generation

### Files affected

- New: `test_data_analyser/services/fill_series_service.py`
  - `infer_fill_pattern(values: list[object]) -> FillPattern` — detects:
    - all-equal → `Constant`
    - arithmetic progression → `Linear(slope)`
    - otherwise → `Repeat`
  - `generate_fill(pattern: FillPattern, count: int) -> list[object]`.

### Implementation steps

- [ ] **Step 5.1.1** — Coerce input values to floats where possible; fall back to repeating the original list otherwise.
- [ ] **Step 5.1.2** — Detect linear progression with tolerance `1e-9`.

### Tests to add

- `tests/test_services.py`
  - `FillSeriesServiceTests`:
    - constant fill
    - linear fill `[1, 2, 3] → [4, 5, 6, 7]`
    - repeat fill for non-linear input
    - text values repeat verbatim

---

## 5.2 Viewmodel: fill operations

### Files affected

- `test_data_analyser/viewmodels/dataset_vm.py`
  - `fill_down(row_indices: list[int], channel_ids: list[str]) -> OperationResult` — uses the values of the first row of the selection as the seed and fills down the rest.
  - `fill_drag(seed_indices, seed_channel_ids, target_rows, target_channel_ids) -> OperationResult` — used by the drag handle.

### Implementation steps

- [ ] **Step 5.2.1** — For each affected column, compute the seed values, infer the pattern, generate the fill, write through `set_cell`.
- [ ] **Step 5.2.2** — Push one undo snapshot per fill operation.

### Tests to add

- `tests/test_viewmodels.py`
  - `FillVMTests`:
    - fill_down constant + linear
    - fill_drag across a rectangle
    - undo restores prior values

---

## 5.3 Qt panel: drag handle + context menu

### Files affected

- `test_data_analyser/qt_app/widgets/raw_data_panel.py`
  - Custom delegate or paint event that draws a small square at the bottom-right corner of the active selection's bounding box.
  - Mouse press on the handle → start a fill-drag; mouse move → preview target rect; mouse release → call `dataset_vm.fill_drag`.
  - Right-click menu in edit mode: add "Fill down from selection" and "Fill across from selection" entries.

### Implementation steps

- [ ] **Step 5.3.1** — Implement handle painting via `QPainter` over the viewport — only when in edit mode and the selection is rectangular.
- [ ] **Step 5.3.2** — Drag state machine. While dragging, draw a translucent target rect.
- [ ] **Step 5.3.3** — Context menu entries wire to `dataset_vm.fill_down`.

### Tests to add

- `tests/test_qt_adapters.py`
  - `FillHandleTests`:
    - `test_fill_handle_visible_in_edit_mode`
    - `test_context_menu_fill_down_invokes_viewmodel`

### Acceptance criteria

- ✅ Dragging the handle fills a constant or linear series.
- ✅ Right-click "Fill down" works on any selected row range.
- ✅ One fill = one undo step.

---

## Phase 5 wrap-up

- [ ] Update `ARCHITECTURE.md` and `VERSION_HISTORY.md`.
- [ ] Run the full test suite.

---

# Phase 6 — Bulk Workflows

**Goal:** Three independent bulk-workflow features. Each is self-contained and can be implemented in any order within the phase.

## 6.1 Batch Run Import

### Files affected

- New: `test_data_analyser/services/batch_import_service.py`
  - `discover_data_files(folder: Path, *, glob: str, recursive: bool) -> list[Path]`
  - `extract_run_name(path: Path, *, regex: str | None) -> str` — defaults to filename stem.
- `test_data_analyser/viewmodels/runs_comparison_vm.py`
  - `add_runs_from_folder(folder, *, glob, recursive, name_regex, sheet_strategy)` — `sheet_strategy` is `"first"` / `"prompt"` / a specific sheet name.
- New: `test_data_analyser/qt_app/widgets/batch_import_dialog.py`
  - Folder picker, glob entry, recursive check, name-regex entry, sheet strategy combo.

### Implementation steps

- [ ] **Step 6.1.1** — Service discovery + regex extraction.
- [ ] **Step 6.1.2** — VM loops the files. For each, call `add_run`. Skip files that fail to load; collect failures into the result warnings.
- [ ] **Step 6.1.3** — Dialog with sane defaults (`*.csv;*.xlsx`, non-recursive, no regex, "first" sheet).
- [ ] **Step 6.1.4** — Hook into `RunsComparisonPanel` as a new "Batch Import…" button.

### Tests to add

- `tests/test_services.py`
  - `BatchImportServiceTests`:
    - discover with glob
    - regex name extraction (`r"SN(\d+)"` against `Run_SN13260599.csv` → `"13260599"`)
- `tests/test_viewmodels.py`
  - `RunsComparisonBatchTests`:
    - imports 3 files
    - skips a corrupt file with a warning
- `tests/test_qt_adapters.py`
  - `BatchImportDialogTests`:
    - settings round-trip
    - cancel does nothing

### Acceptance criteria

- ✅ A folder of 44 CSV files imports as 44 runs in one action.
- ✅ Regex naming sets the run name from the filename.

---

## 6.2 Limit Templates

### Files affected

- New: `test_data_analyser/services/limit_templates_service.py`
  - `save_limit_template(path, lines: list[dict])` / `load_limit_template(path) -> list[dict]`. Round-trip JSON shape matches the existing `LimitLine` domain model.
- `test_data_analyser/viewmodels/limits_vm.py`
  - `export_template(path)` / `import_template(path, *, replace: bool)`. Replace mode wipes existing limits before importing; merge mode appends.
- `test_data_analyser/qt_app/widgets/limits_panel.py`
  - Add "Save Template…" / "Load Template…" buttons to the limits toolbar.

### Implementation steps

- [ ] **Step 6.2.1** — Service round-trip via `LimitLine.from_dict` / `to_dict`.
- [ ] **Step 6.2.2** — VM helpers route through the service. On import, prompt the panel (via signal) for replace/merge.
- [ ] **Step 6.2.3** — Panel buttons + file dialogs (extend `qt_file_dialogs.py` with a `LIMIT_TEMPLATE_FILTER`).

### Tests to add

- `tests/test_services.py`
  - `LimitTemplatesServiceTests`:
    - round-trip preserves names, types, applies-to, colours, points
- `tests/test_viewmodels.py`
  - `LimitTemplateImportTests`:
    - replace clears + imports
    - merge appends

### Acceptance criteria

- ✅ A saved template re-imports identically.
- ✅ Merge mode preserves existing limit lines.

---

## 6.3 Peak Detection

### Files affected

- New: `test_data_analyser/services/peak_detection_service.py`
  - `find_peaks(x, y, *, prominence, distance, find_troughs) -> list[Peak]` (wraps `scipy.signal.find_peaks`).
- `test_data_analyser/viewmodels/plot_workspace_vm.py`
  - `detect_peaks(channel, *, prominence, distance, find_troughs) -> OperationResult` (payload: list of `(x, y)` tuples).
- `test_data_analyser/qt_app/widgets/plot_workspace.py`
  - Right-click on a plotted channel → context menu "Mark peaks…". Opens a small dialog with prominence + distance + "Include troughs" inputs. On accept, generates text annotations at each peak.

### Implementation steps

- [ ] **Step 6.3.1** — Service wrapper. Guard scipy import (already imported lazily in `core/filters.py` — follow the same pattern).
- [ ] **Step 6.3.2** — VM helper composes annotations: one text annotation per peak with `text=f"{y:.3g}"`.
- [ ] **Step 6.3.3** — Inline dialog in `plot_workspace.py` (small `QDialog`).
- [ ] **Step 6.3.4** — Generated annotations integrate with the existing annotation persistence in plot profiles — no extra plumbing required.

### Tests to add

- `tests/test_services.py`
  - `PeakDetectionServiceTests`:
    - simple sine — expected peaks
    - prominence filter excludes small bumps
    - troughs flag
- `tests/test_viewmodels.py`
  - `PeakDetectionVMTests`:
    - returns peak count and locations
    - annotation payload is well-formed

### Acceptance criteria

- ✅ Right-click a channel → "Mark peaks…" produces visible annotations.
- ✅ Annotations are saved with the session (already handled by existing annotation pipeline).

---

## Phase 6 wrap-up

- [ ] Update `ARCHITECTURE.md`: list the three new services. Add a short "Bulk workflows" subsection under "Recent enhancements".
- [ ] Update `VERSION_HISTORY.md`.
- [ ] Run the full test suite.

---

# Phase 7 — Final Polish

**Goal:** Small UI niceties that round off V1.02.02 before release.

## 7.1 Plot tab drag-to-reorder

### Files affected

- `test_data_analyser/qt_app/main_window.py`
  - `self.plot_tab_bar.setMovable(True)`.
  - Connect `plot_tab_bar.tabMoved(from, to)` to a new `_on_plot_tab_moved` slot.
- `test_data_analyser/viewmodels/main_window_vm.py`
  - `reorder_plot_profile(from_index, to_index) -> OperationResult`. Updates `state.plot_profiles` and re-clamps `active_plot_profile_index`.

### Implementation steps

- [ ] **Step 7.1.1** — VM helper — pure list manipulation, no UI.
- [ ] **Step 7.1.2** — Wire `tabMoved` → VM helper, then re-sync tabs without recreating them all (avoid flicker).
- [ ] **Step 7.1.3** — Guard the "+" tab so it cannot be moved out of last position.

### Tests to add

- `tests/test_viewmodels.py`
  - `test_reorder_plot_profile_moves_active_index`
- `tests/test_qt_adapters.py`
  - `test_plot_tab_bar_is_movable`

---

## 7.2 Reset axis appearance button

### Files affected

- `test_data_analyser/qt_app/adapters/matplotlib_qt_adapter.py`
  - Add a "Reset Axis" `QPushButton` to the Figure Options dialog (alongside the auto-label/auto-fit helpers).
  - Click → clear manual title/labels/limits/ticks for the active profile and re-render.
- `test_data_analyser/viewmodels/main_window_vm.py`
  - `reset_active_axis_appearance() -> OperationResult` — clears `manual_labels`, `axis_limits`, `axis_ticks`, regenerates labels from current selection.

### Implementation steps

- [ ] **Step 7.2.1** — VM helper.
- [ ] **Step 7.2.2** — Hook into the Figure Options dialog. Mirror the existing "Auto Label" wiring.

### Tests to add

- `tests/test_viewmodels.py`
  - `test_reset_active_axis_appearance_clears_manual_state`

### Acceptance criteria

- ✅ Clicking Reset Axis clears manual edits but keeps the plotted data and best-fit settings.

---

## Phase 7 wrap-up

- [ ] Update `ARCHITECTURE.md` — bullet for plot tab reordering and reset axis.
- [ ] Update `VERSION_HISTORY.md` with the V1.02.02 release entry summarising all phases.
- [ ] Run the full test suite.
- [ ] Bump `__version__` in `core/config.py` to `"1.02.02"`.

---

# 5. Cross-Phase Engineering Notes

## 5.1 Undo integration

Every dataset-mutating action introduced in Phases 3-5 must:

1. Capture exactly **one** undo snapshot before applying the mutation.
2. Use the existing `AppStateController.capture_dataset_snapshot` / `restore_dataset_snapshot` helpers.
3. Surface "Undid <description>" via the existing status bar pipeline.

Don't add a parallel undo stack.

## 5.2 Status bar messages

Pattern: short, past-tense, no full stop except for multi-clause messages.

```
"Pasted 12 rows × 3 columns."
"Replaced 47 occurrences."
"Imported 44 runs from C:/data/PAT_SN/."
"Auto-saved at 14:32:08."
```

## 5.3 Avoiding duplicates (per user preference)

Before adding anything new, check:

- ✅ `core/utils.py` — compatibility facade for older helpers.
- ✅ `core/naming.py` — natural sort key.
- ✅ `core/column_matching.py` — grouped column / keyword matching.
- ✅ `services/dataset_service.py` — already covers add/rename/delete column, add/delete row, set cell, coerce edit value.
- ✅ `services/raw_data_service.py` — already covers parsing row limit, selecting frame, blank-row removal.
- ✅ `services/results.py` — `OperationResult` for all return values.
- ✅ `services/plot_render_service.py` — colour cycles, normalise channel name.
- ✅ `domain/annotations.py` — annotation normalisation for Phase 6.3.

If your new code looks similar to one of these, route through it instead.

## 5.4 Tests

- Domain / service tests stay headless. **Do not** import PySide6 from them.
- Qt panel/adapter tests already use the offscreen platform — follow the existing pattern.
- Architecture boundary tests (`tests/test_architecture_boundaries.py`) must keep passing — they enforce the layer rules above.

---

# 6. VSC Copilot Prompt Guidance

For each phase:

1. **Read this document's phase section first.** Acknowledge the goal and the files touched.
2. **Within a phase, work one step at a time.** Implement the step → write its tests → run the test suite. Do not move to the next step until the suite is green.
3. **Mention the user's preferences at the start of each phase:**
   > "Aggressive duplicate removal. Follow ARCHITECTURE.md order. Extracted mixins are the source of truth. No backward compatibility required. Separate pure plotting logic from canvas wiring. Keep Eaton branding unchanged."
4. **End each phase with three actions:**
   - Update `ARCHITECTURE.md` with the new files / behaviours.
   - Add a `VERSION_HISTORY.md` entry.
   - Run `python -m unittest discover -s tests` and paste the summary.

## 6.1 Suggested per-phase prompt template

> "We are implementing **Phase N — <name>** of Test Data Analyser V1.02.02. Read the corresponding section of `Update_1_02_02_Implementation_Plan.md`. Confirm the files affected, then implement Step N.M only. Add the matching tests. Run the full test suite. If green, propose the next step. If red, fix before continuing. Respect the architecture rules: only `qt_app/` imports PySide6, services and viewmodels return `OperationResult`, no UI work in services or viewmodels."

## 6.2 What to do if you hit a design ambiguity

- Prefer adding a service helper to extending a viewmodel.
- Prefer extending an existing viewmodel method to adding a new one when the contract is similar.
- Never add UI code (QMessageBox, QFileDialog, etc.) outside `qt_app/`.
- If unsure where a behaviour belongs, place it in the lowest layer that already handles a similar concern (per the ARCHITECTURE.md layer order).

---

# 7. Release Checklist

Before tagging V1.02.02:

- [ ] All seven phases completed.
- [ ] `__version__` bumped to `"1.02.02"` in `core/config.py`.
- [ ] `ARCHITECTURE.md` "Recent enhancements" mentions every headline feature.
- [ ] `VERSION_HISTORY.md` has a V1.02.02 entry covering all phases.
- [ ] `README.md` Editable Raw Data / Plot options / Limits / Runs sections reflect the new behaviour.
- [ ] Full test suite green:
  ```
  python -m unittest discover -s tests
  ```
- [ ] Architecture boundary tests green.
- [ ] Help dialog Keyboard Shortcuts topic reflects every shortcut added.
- [ ] Smoke test on a real PAT dataset: open, batch import, filter, copy/paste, find/replace, mark peaks, save session, reload session.

---

*End of plan. Each phase is independent enough that any of them can slip to V1.02.03 if scope tightens — Phases 1, 2 and 6 are the highest leverage and should land first.*
