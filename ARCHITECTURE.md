# Test Data Analyser Architecture Notes

This revision continues the staged refactor away from a single monolithic `gui.py` file.

## Current layout

- `gui.py` exposes the public `TestDataAnalyserGUI` class used by `main.py`.
- `gui_base.py` contains the previously monolithic GUI implementation, renamed to `TestDataAnalyserGUIBase` for compatibility.
- `label_profiles.py` owns per-plot label state and auto-label behaviour.
- `profile_state.py` owns plot profile creation, switching, capture/apply, duplication, rename/delete, and JSON session save/load.
- `engineering_notes.py` owns the structured Engineering Notes tab, note capture/restoration, report text formatting, clipboard copy, and note clearing.
- `raw_data.py` owns Raw Data tab state refresh, selected-data framing/filtering, row display limits, blank-row removal, and selected-data export.
- `analysis.py` owns statistics, selected-data ranges, range preview, and axis-limit fill from data.
- `limits.py` owns requirement/limit line CRUD, limit point editing, limit plotting, active limit ranges, and margin-to-limit reporting.
- `cursor_tools.py` owns the live cursor readout, locked point comparison (Point Compare), cursor table/text rendering, and using locked points as the analysis window.
- `plotting.py` owns figure/canvas management, plot data preparation, plot and FFT generation (including secondary Y-axis handling), legend/panel handling, and figure/output saving.
- `calculated_channels.py` owns Maths Channel creation, safe formula evaluation, calculated channel CRUD, recalculation, and dataframe/UI refresh after derived columns change.
- `multi_run.py` owns the Runs / Comparison tab, multi-file/multi-run loading, run activation, comparison plotting, comparison statistics, and run metadata session integration.
- `raw_data_editor.py` owns inline Raw Data cell editing and refresh of dataframe-dependent analysis views after edits.
- `data_loading.py` owns file/sheet loading, column population/classification, the dataframe caches, Y-channel checkbox rebuild, Y/secondary-Y selection, the debounced axis-selection handler, and column-derived axis labels.
- `models.py` owns framework-independent dataclasses for plot data and plot profile/session state normalisation.

## Why this is safe

The extracted mixins are placed before `TestDataAnalyserGUIBase` in the method-resolution order, so the app uses extracted modules as the source of truth. `gui_base.py` remains only for behaviour that has not yet been extracted.

## Included behaviour improvement

Axis/title labels are treated as per-plot-profile state. If the user manually edits an axis label, subsequent X/Y channel changes will not overwrite that label for that plot. Pressing **Auto Labels** intentionally returns label fields to automatic generation.

## Domain model extraction

`models.py` now contains framework-independent dataclasses for plot profile and session state, including axis limits, analysis windows, filters, legend settings, raw-data view settings, manual label flags, engineering notes, and requirement/limit lines.

The Tkinter mixins still store active plot profiles as dictionaries for compatibility with the current UI and saved session JSON, but profile data is normalised through model helpers at creation, apply, save, and load boundaries. This keeps current behaviour stable while establishing a domain boundary that can be reused by a future PySide6 or other UI implementation.

## Recommended next extraction passes

The major behaviour clusters have now been extracted into focused mixins, and
the dead duplicate copies left behind by earlier passes have been removed from
`gui_base.py`.

`gui_base.py` (`TestDataAnalyserGUIBase`) is now considered the stable
**foundation** and is *not* a target for further extraction. It retains only
shared infrastructure that every mixin builds on:

- window/app lifecycle and Eaton styling (`__init__`, `_apply_eaton_style`);
- the app chrome and master widget tree (`_build_modern_*`, `_build_ui`,
  `_build_left_controls`, `_build_right_panel`);
- shared helpers reached across mixins via `self`: cached numeric conversion
  (`_get_numeric`), generic table/text helpers (`_set_text_widget`,
  `_clear_treeview`), and the axis-limit helper cluster (`parse_limit`,
  `_axis_upper_margin`, `manual_limits`, `secondary_manual_limits`,
  `limits_have_visible_data`, `toggle_axis_entries`, `apply_auto_axis_limits`);
- the analysis-window helpers (`copy_axis_limits_to_analysis_window`,
  `clear_analysis_window`).

Future passes, if desired, could separate the pure plotting/data-preparation
logic in `plotting.py` further from Tkinter event handling, or split the
widget-construction code in `gui_base.py` into a dedicated UI-builder module.

The staged approach keeps the app runnable while steadily reducing the size and risk of future edits.
