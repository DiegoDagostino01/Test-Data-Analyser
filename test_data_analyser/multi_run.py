from __future__ import annotations

from pathlib import Path
from typing import Any, Optional
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from cycler import cycler
import matplotlib.ticker as ticker
import pandas as pd

from .config import EATON_DARK_BLUE, EATON_DARK_GREY, EATON_MID_GREY, EATON_PLOT_COLORS
from .data_io import get_excel_sheets, load_data, numeric_series
from .filters import estimate_sampling_rate, lowpass_filter
from .models import PlotData
from .utils import _matching_x_column_for_y


class MultiRunMixin:
    """Multi-file / multi-run comparison state, UI, plotting, and session helpers."""

    RUN_COLUMNS = ("Name", "Enabled", "Active", "File", "Sheet", "Rows", "Columns")
    COMPARISON_STAT_COLUMNS = ("Run", "Channel", "Count", "Min", "Max", "Mean", "Std Dev")

    def __init__(self, *args, **kwargs):
        master = args[0] if args else kwargs.get("root")
        self.runs: list[dict[str, Any]] = []
        self.active_run_index: int = -1
        self.comparison_mode_enabled = tk.BooleanVar(master=master, value=False)
        self.comparison_common_x_range_var = tk.BooleanVar(master=master, value=False)
        self.comparison_prefix_legend_var = tk.BooleanVar(master=master, value=True)
        super().__init__(*args, **kwargs)

    # ------------------------------------------------------------------
    # Tab UI
    # ------------------------------------------------------------------
    def _build_runs_comparison_tab(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(2, weight=1)
        parent.columnconfigure(0, weight=1)

        toolbar = ttk.Frame(parent)
        toolbar.grid(row=0, column=0, sticky="ew", padx=6, pady=(4, 2))
        ttk.Button(toolbar, text="Add Run", command=self.add_run).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Remove Run", command=self.remove_selected_run).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Duplicate Run", command=self.duplicate_selected_run).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Rename Run", command=self.rename_selected_run).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Set Active Run", command=self.set_selected_run_active).pack(side="left", padx=(0, 6))
        ttk.Button(toolbar, text="Refresh Runs", command=self.refresh_runs_view).pack(side="left")

        controls = ttk.Frame(parent)
        controls.grid(row=1, column=0, sticky="ew", padx=6, pady=(0, 4))
        ttk.Checkbutton(
            controls,
            text="Overlay enabled runs",
            variable=self.comparison_mode_enabled,
            command=self._on_comparison_control_changed,
        ).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(
            controls,
            text="Prefix legend labels with run name",
            variable=self.comparison_prefix_legend_var,
            command=self._on_comparison_control_changed,
        ).pack(side="left", padx=(0, 12))
        ttk.Checkbutton(
            controls,
            text="Use common X range only",
            variable=self.comparison_common_x_range_var,
            command=self._on_comparison_control_changed,
        ).pack(side="left", padx=(0, 12))
        ttk.Label(controls, text="Double-click a run to toggle Enabled.").pack(side="left")

        body = ttk.PanedWindow(parent, orient="horizontal")
        body.grid(row=2, column=0, sticky="nsew", padx=6, pady=(0, 4))

        run_frame = ttk.LabelFrame(body, text="Loaded Runs", style="Card.TLabelframe")
        stat_frame = ttk.LabelFrame(body, text="Comparison Statistics", style="Card.TLabelframe")
        body.add(run_frame, weight=3)
        body.add(stat_frame, weight=2)

        run_frame.rowconfigure(0, weight=1)
        run_frame.columnconfigure(0, weight=1)
        self.runs_tree = ttk.Treeview(
            run_frame,
            columns=self.RUN_COLUMNS,
            show="headings",
            height=8,
            style="Bordered.Treeview",
        )
        for column in self.RUN_COLUMNS:
            self.runs_tree.heading(column, text=column)
            width = 90
            if column == "Name":
                width = 160
            elif column == "File":
                width = 280
            elif column == "Sheet":
                width = 130
            self.runs_tree.column(column, width=width, anchor="center" if column != "File" else "w")
        self._configure_treeview_tags(self.runs_tree)
        run_y_scroll = ttk.Scrollbar(run_frame, orient="vertical", command=self.runs_tree.yview)
        run_x_scroll = ttk.Scrollbar(run_frame, orient="horizontal", command=self.runs_tree.xview)
        self.runs_tree.configure(yscrollcommand=run_y_scroll.set, xscrollcommand=run_x_scroll.set)
        self.runs_tree.grid(row=0, column=0, sticky="nsew")
        run_y_scroll.grid(row=0, column=1, sticky="ns")
        run_x_scroll.grid(row=1, column=0, sticky="ew")
        self.runs_tree.bind("<Double-1>", self._on_run_tree_double_click)

        stat_frame.rowconfigure(0, weight=1)
        stat_frame.columnconfigure(0, weight=1)
        self.comparison_stats_tree = ttk.Treeview(
            stat_frame,
            columns=self.COMPARISON_STAT_COLUMNS,
            show="headings",
            height=8,
            style="Bordered.Treeview",
        )
        for column in self.COMPARISON_STAT_COLUMNS:
            self.comparison_stats_tree.heading(column, text=column)
            self.comparison_stats_tree.column(
                column,
                width=150 if column in {"Run", "Channel"} else 90,
                anchor="center" if column not in {"Run", "Channel"} else "w",
            )
        self._configure_treeview_tags(self.comparison_stats_tree)
        stat_y_scroll = ttk.Scrollbar(stat_frame, orient="vertical", command=self.comparison_stats_tree.yview)
        stat_x_scroll = ttk.Scrollbar(stat_frame, orient="horizontal", command=self.comparison_stats_tree.xview)
        self.comparison_stats_tree.configure(yscrollcommand=stat_y_scroll.set, xscrollcommand=stat_x_scroll.set)
        self.comparison_stats_tree.grid(row=0, column=0, sticky="nsew")
        stat_y_scroll.grid(row=0, column=1, sticky="ns")
        stat_x_scroll.grid(row=1, column=0, sticky="ew")

        self.runs_status_var = tk.StringVar(value="No runs loaded.")
        ttk.Label(parent, textvariable=self.runs_status_var).grid(row=3, column=0, sticky="ew", padx=6, pady=(0, 4))

    # ------------------------------------------------------------------
    # Run loading and management
    # ------------------------------------------------------------------
    def add_run(self) -> None:
        filename = filedialog.askopenfilename(
            title="Add test run",
            filetypes=[
                ("Data files", "*.csv *.xlsx *.xls"),
                ("CSV", "*.csv"),
                ("Excel", "*.xlsx *.xls"),
                ("All files", "*.*"),
            ],
        )
        if not filename:
            return
        path = Path(filename)
        try:
            sheets = get_excel_sheets(path)
            sheet_name = self._choose_sheet_for_run(path, sheets) if sheets else ""
            df = load_data(path, sheet_name or None, settings_manager=getattr(self, "settings_manager", None))
        except Exception as exc:
            messagebox.showerror("Add Run", f"Could not load the selected run:\n\n{exc}")
            return

        run = self._make_run_entry(
            name=f"Run {len(self.runs) + 1}",
            filepath=path,
            sheet_name=sheet_name,
            df=df,
            enabled=True,
        )
        self.runs.append(run)
        if len(self.runs) == 1:
            self._set_active_run_index(0, preserve_selection=False, capture_profile=False)
        else:
            self.refresh_runs_view()
            self._set_run_status(f"Added {run['name']}.")

    def remove_selected_run(self) -> None:
        index = self._selected_run_index()
        if index is None:
            messagebox.showwarning("Runs / Comparison", "Select a run to remove.")
            return
        run_name = self.runs[index].get("name", f"Run {index + 1}")
        confirm = self._setting("general_ui", "confirm_before_delete", True) if hasattr(self, "_setting") else True
        if confirm and not messagebox.askyesno("Remove Run", f"Remove '{run_name}' from this comparison?"):
            return
        was_active = index == self.active_run_index
        del self.runs[index]
        if not self.runs:
            self._clear_active_run_state()
            self.refresh_runs_view()
            return
        if was_active:
            self._set_active_run_index(min(index, len(self.runs) - 1), preserve_selection=True)
            return
        if index < self.active_run_index:
            self.active_run_index -= 1
        self.refresh_runs_view()

    def duplicate_selected_run(self) -> None:
        index = self._selected_run_index()
        if index is None:
            messagebox.showwarning("Runs / Comparison", "Select a run to duplicate.")
            return
        source = self.runs[index]
        df = source["df"].copy(deep=False) if isinstance(source.get("df"), pd.DataFrame) else source.get("df")
        duplicate = {
            "name": f"{source.get('name', f'Run {index + 1}')} Copy",
            "filepath": str(source.get("filepath", "")),
            "sheet_name": source.get("sheet_name", ""),
            "df": df,
            "enabled": bool(source.get("enabled", True)),
            "colour": self._next_run_colour(),
        }
        self.runs.append(duplicate)
        self.refresh_runs_view()

    def rename_selected_run(self) -> None:
        index = self._selected_run_index()
        if index is None:
            messagebox.showwarning("Runs / Comparison", "Select a run to rename.")
            return
        current_name = str(self.runs[index].get("name", f"Run {index + 1}"))
        new_name = simpledialog.askstring("Rename Run", "Run name:", initialvalue=current_name)
        if not new_name:
            return
        self.runs[index]["name"] = new_name.strip() or current_name
        self.refresh_runs_view()

    def set_selected_run_active(self) -> None:
        index = self._selected_run_index()
        if index is None:
            messagebox.showwarning("Runs / Comparison", "Select a run to make active.")
            return
        self._set_active_run_index(index, preserve_selection=True)

    def refresh_runs_view(self) -> None:
        if hasattr(self, "runs_tree"):
            children = self.runs_tree.get_children()
            if children:
                self.runs_tree.delete(*children)
            for index, run in enumerate(self.runs):
                df = run.get("df")
                rows = len(df) if isinstance(df, pd.DataFrame) else 0
                columns = len(df.columns) if isinstance(df, pd.DataFrame) else 0
                self.runs_tree.insert(
                    "",
                    "end",
                    iid=str(index),
                    values=(
                        run.get("name", f"Run {index + 1}"),
                        "Yes" if run.get("enabled", True) else "No",
                        "Yes" if index == self.active_run_index else "",
                        str(run.get("filepath", "")),
                        run.get("sheet_name", ""),
                        f"{rows:,}",
                        f"{columns:,}",
                    ),
                    tags=(self._tree_row_tag(index),),
                )
            if 0 <= self.active_run_index < len(self.runs):
                self.runs_tree.selection_set(str(self.active_run_index))
                self.runs_tree.focus(str(self.active_run_index))
        self.update_comparison_stats()
        self._update_runs_status_label()

    def _choose_sheet_for_run(self, path: Path, sheets: list[str]) -> str:
        if not sheets:
            return ""
        if len(sheets) == 1:
            return sheets[0]
        preview = "\n".join(f"- {sheet}" for sheet in sheets[:20])
        if len(sheets) > 20:
            preview += f"\n... plus {len(sheets) - 20} more"
        chosen = simpledialog.askstring(
            "Select Excel Sheet",
            f"{path.name} contains multiple sheets. Enter the sheet name to load:\n\n{preview}",
            initialvalue=sheets[0],
        )
        if chosen is None or not chosen.strip():
            return sheets[0]
        chosen = chosen.strip()
        if chosen in sheets:
            return chosen
        messagebox.showwarning("Select Excel Sheet", f"Sheet '{chosen}' was not found. Loading '{sheets[0]}' instead.")
        return sheets[0]

    def _make_run_entry(
        self,
        name: str,
        filepath: Path,
        sheet_name: str,
        df: pd.DataFrame,
        enabled: bool,
        colour: Optional[str] = None,
    ) -> dict[str, Any]:
        return {
            "name": name,
            "filepath": str(filepath),
            "sheet_name": sheet_name or "",
            "df": df,
            "enabled": bool(enabled),
            "colour": colour or self._next_run_colour(),
        }

    def _next_run_colour(self) -> str:
        return EATON_PLOT_COLORS[len(self.runs) % len(EATON_PLOT_COLORS)]

    def _selected_run_index(self) -> Optional[int]:
        if not hasattr(self, "runs_tree"):
            return None
        selection = self.runs_tree.selection()
        if not selection:
            return None
        try:
            index = int(selection[0])
        except ValueError:
            return None
        return index if 0 <= index < len(self.runs) else None

    def _on_run_tree_double_click(self, event=None) -> None:
        if not hasattr(self, "runs_tree"):
            return
        item = self.runs_tree.identify_row(event.y) if event is not None else ""
        if not item:
            item = self.runs_tree.focus()
        try:
            index = int(item)
        except ValueError:
            return
        if 0 <= index < len(self.runs):
            self.runs[index]["enabled"] = not bool(self.runs[index].get("enabled", True))
            self.refresh_runs_view()

    # ------------------------------------------------------------------
    # Active run state
    # ------------------------------------------------------------------
    def _set_active_run_index(
        self,
        index: int,
        preserve_selection: bool = True,
        capture_profile: bool = True,
    ) -> list[str]:
        if not (0 <= index < len(self.runs)):
            return []
        if capture_profile and hasattr(self, "_capture_current_plot_profile"):
            self._capture_current_plot_profile()

        previous_x = self.x_col_var.get() if preserve_selection and hasattr(self, "x_col_var") else ""
        previous_y = set(self.selected_y_columns()) if preserve_selection and hasattr(self, "y_vars") else set()
        previous_secondary = (
            set(self.selected_secondary_y_columns())
            if preserve_selection and hasattr(self, "secondary_y_vars")
            else set()
        )

        self.active_run_index = index
        active_run = self.runs[index]
        self.df = active_run.get("df")
        filepath_value = active_run.get("filepath", "")
        self.filepath = Path(filepath_value) if filepath_value else None
        self._update_active_file_widgets(active_run)
        calculation_errors = self._recalculate_calculated_channels_for_run(active_run)

        original_profile_switch = getattr(self, "_profile_switch_in_progress", False)
        if not capture_profile:
            self._profile_switch_in_progress = True
        try:
            self.populate_columns()
        finally:
            if not capture_profile:
                self._profile_switch_in_progress = original_profile_switch

        if preserve_selection:
            self._restore_column_selection(previous_x, previous_y, previous_secondary)
        self._refresh_active_run_dependent_views()
        if capture_profile and hasattr(self, "_capture_current_plot_profile"):
            self._capture_current_plot_profile()
        self.refresh_runs_view()
        active_name = active_run.get("name", f"Run {index + 1}")
        if calculation_errors:
            self._set_run_status(f"Active run set to {active_name}. Some Maths Channels could not be recalculated.")
        else:
            self._set_run_status(f"Active run set to {active_name}.")
        return calculation_errors

    def _restore_column_selection(self, previous_x: str, previous_y: set[str], previous_secondary: set[str]) -> None:
        if self.df is None:
            return
        columns = {str(column) for column in self.df.columns}
        if previous_x in columns:
            self.x_col_var.set(previous_x)
        current_x = self.x_col_var.get()
        for column, var in self.y_vars.items():
            var.set(column in previous_y and column in columns and column != current_x)
        for column, var in self.secondary_y_vars.items():
            var.set(column in previous_secondary and column in previous_y and column in columns and column != current_x)
        self._rebuild_y_checkboxes()

    def _refresh_active_run_dependent_views(self) -> None:
        if hasattr(self, "auto_labels_from_selection"):
            self.auto_labels_from_selection()
        self.update_range_preview()
        self.update_stats()
        self.update_raw_data_view()
        if hasattr(self, "_refresh_limit_applies_options"):
            self._refresh_limit_applies_options()
        self.update_comparison_stats()

    def _update_active_file_widgets(self, run: dict[str, Any]) -> None:
        if hasattr(self, "file_label"):
            self.file_label.configure(text=str(run.get("filepath", "")) or "No file selected")
        if not hasattr(self, "sheet_frame"):
            return
        path_text = str(run.get("filepath", ""))
        path = Path(path_text) if path_text else None
        sheet_name = str(run.get("sheet_name", "") or "")
        sheets: list[str] = []
        if path is not None:
            try:
                sheets = get_excel_sheets(path)
            except Exception:
                sheets = [sheet_name] if sheet_name else []
        if sheets:
            self.sheet_frame.pack(fill="x", pady=(4, 0))
            self.sheet_combo.configure(values=sheets)
            self.sheet_var.set(sheet_name if sheet_name in sheets else sheets[0])
        else:
            self.sheet_frame.pack_forget()
            if hasattr(self, "sheet_var"):
                self.sheet_var.set("")

    def _clear_active_run_state(self) -> None:
        self.active_run_index = -1
        self.df = None
        self.filepath = None
        if hasattr(self, "file_label"):
            self.file_label.configure(text="No file selected")
        if hasattr(self, "sheet_frame"):
            self.sheet_frame.pack_forget()
        if hasattr(self, "sheet_var"):
            self.sheet_var.set("")
        if hasattr(self, "x_combo"):
            self.x_combo.configure(values=[])
        if hasattr(self, "x_col_var"):
            self.x_col_var.set("")
        self.y_vars = {}
        self.secondary_y_vars = {}
        self._visible_y_columns = []
        if hasattr(self, "_reset_data_caches"):
            self._reset_data_caches()
        if hasattr(self, "_rebuild_y_checkboxes"):
            self._rebuild_y_checkboxes()
        self.update_range_preview()
        self.update_stats()
        self.update_raw_data_view()

    def _sync_current_file_to_active_run(self) -> None:
        if self.df is None or self.filepath is None:
            return
        sheet_name = self.sheet_var.get() if hasattr(self, "sheet_var") else ""
        if not self.runs or not (0 <= self.active_run_index < len(self.runs)):
            # The legacy Data File panel remains a single-file workflow: first load
            # creates Run 1, while later Data File loads replace the active run.
            self.runs = [
                self._make_run_entry(
                    name="Run 1",
                    filepath=self.filepath,
                    sheet_name=sheet_name,
                    df=self.df,
                    enabled=True,
                )
            ]
            self.active_run_index = 0
        else:
            active_run = self.runs[self.active_run_index]
            active_run["filepath"] = str(self.filepath)
            active_run["sheet_name"] = sheet_name or ""
            active_run["df"] = self.df
        self.refresh_runs_view()

    def _update_runs_status_label(self) -> None:
        if not hasattr(self, "runs_status_var"):
            return
        loaded = len(self.runs)
        enabled = sum(1 for run in self.runs if run.get("enabled", True))
        active = "None"
        if 0 <= self.active_run_index < len(self.runs):
            active = str(self.runs[self.active_run_index].get("name", f"Run {self.active_run_index + 1}"))
        self.runs_status_var.set(f"Loaded runs: {loaded} | Enabled: {enabled} | Active run: {active}")

    def _set_run_status(self, message: str) -> None:
        self._update_runs_status_label()
        if hasattr(self, "status_var"):
            self.status_var.set(message)

    # ------------------------------------------------------------------
    # Existing single-file loading integration
    # ------------------------------------------------------------------
    def select_file(self) -> None:
        previous_df = self.df
        super().select_file()
        if self.df is not None and self.df is not previous_df:
            self._sync_current_file_to_active_run()

    def load_selected_sheet(self) -> None:
        previous_df = self.df
        super().load_selected_sheet()
        if self.df is not None and self.df is not previous_df:
            self._sync_current_file_to_active_run()

    def on_axis_selection_changed(self) -> None:
        super().on_axis_selection_changed()
        self.update_comparison_stats()

    def _on_comparison_control_changed(self) -> None:
        self.update_comparison_stats()
        state = "enabled" if self.comparison_mode_enabled.get() else "disabled"
        self._set_run_status(f"Comparison overlay {state}.")

    # ------------------------------------------------------------------
    # Comparison statistics
    # ------------------------------------------------------------------
    def update_comparison_stats(self) -> None:
        if not hasattr(self, "comparison_stats_tree"):
            return
        children = self.comparison_stats_tree.get_children()
        if children:
            self.comparison_stats_tree.delete(*children)
        y_columns = self.selected_y_columns() if hasattr(self, "y_vars") else []
        if not y_columns:
            return
        row_index = 0
        for run in self._enabled_runs():
            df = run.get("df")
            if not isinstance(df, pd.DataFrame):
                continue
            for channel in y_columns:
                if channel not in df.columns:
                    self._ensure_run_has_calculated_channel(run, channel)
                if channel not in df.columns:
                    continue
                series = numeric_series(df[channel]).dropna()
                if series.empty:
                    continue
                values = (
                    run.get("name", "Run"),
                    channel,
                    int(series.count()),
                    self._format_number(series.min()),
                    self._format_number(series.max()),
                    self._format_number(series.mean()),
                    self._format_number(series.std(ddof=1) if series.count() > 1 else 0.0),
                )
                self.comparison_stats_tree.insert(
                    "", "end", values=values, tags=(self._tree_row_tag(row_index),)
                )
                row_index += 1

    def _format_number(self, value: Any) -> str:
        try:
            return f"{float(value):.6g}"
        except Exception:
            return ""

    # ------------------------------------------------------------------
    # Calculated channel compatibility
    # ------------------------------------------------------------------
    def _recalculate_calculated_channels_for_run(self, run: dict[str, Any]) -> list[str]:
        if not getattr(self, "calculated_channels", None):
            return []
        if not isinstance(run.get("df"), pd.DataFrame):
            return ["No dataframe is loaded for the run."]
        if hasattr(self, "_ensure_calculated_channels_state"):
            self._ensure_calculated_channels_state()

        original_df = self.df
        original_numeric_cache = getattr(self, "_numeric_cache", None)
        self.df = run["df"]
        if original_numeric_cache is not None:
            self._numeric_cache = {}
        errors: list[str] = []
        try:
            for channel_name, definition in list(self.calculated_channels.items()):
                if not bool(definition.get("enabled", True)):
                    if channel_name in self.df.columns:
                        del self.df[channel_name]
                    continue
                formula = str(definition.get("formula") or "").strip()
                if not formula:
                    errors.append(f"{run.get('name', 'Run')} | {channel_name}: missing formula")
                    continue
                try:
                    series, referenced_columns = self._evaluate_calculated_channel_formula_with_metadata(
                        formula,
                        blocked_names={channel_name},
                    )
                except Exception as exc:
                    errors.append(f"{run.get('name', 'Run')} | {channel_name}: {exc}")
                    if channel_name in self.df.columns:
                        del self.df[channel_name]
                    continue
                self.df[channel_name] = series
                definition["created_from_columns"] = referenced_columns
        finally:
            self.df = original_df
            if original_numeric_cache is not None:
                self._numeric_cache = original_numeric_cache
        return errors

    def _ensure_run_has_calculated_channel(self, run: dict[str, Any], channel: str) -> None:
        if channel not in getattr(self, "calculated_channels", {}):
            return
        self._recalculate_calculated_channels_for_run(run)

    # ------------------------------------------------------------------
    # Comparison plotting
    # ------------------------------------------------------------------
    def generate_comparison_plot(self) -> None:
        try:
            enabled_runs = self._enabled_runs()
            if not enabled_runs:
                raise ValueError("Enable at least one run in Runs / Comparison.")
            selected_x = self.x_col_var.get()
            y_columns = self.selected_y_columns()
            if not selected_x:
                raise ValueError("Please select an X-axis column.")
            if not y_columns:
                raise ValueError("Please select at least one Y-axis column.")

            common_range = None
            if self.comparison_common_x_range_var.get():
                common_range = self._comparison_common_x_range(enabled_runs, selected_x)
                if common_range is None:
                    messagebox.showwarning(
                        "Runs / Comparison",
                        "No overlapping X range exists across enabled runs. Disable 'Use common X range only' or choose a different X column.",
                    )
                    return

            plot_items, skipped = self._comparison_plot_items(enabled_runs, selected_x, y_columns, common_range)
            if not plot_items:
                detail = "\n".join(skipped[:12])
                if len(skipped) > 12:
                    detail += f"\n... plus {len(skipped) - 12} more skipped channel(s)."
                raise ValueError("No numeric comparison data was available for the enabled runs." + (f"\n\n{detail}" if detail else ""))

            limits = self.manual_limits()
            y2_limits = self.secondary_manual_limits()
            if not self.auto_fit_var.get() and not self._comparison_limits_have_visible_data(plot_items, limits, y2_limits):
                if not messagebox.askyesno(
                    "Axis limit warning",
                    "The current manual axis limits appear to hide all selected comparison data. Continue anyway?",
                ):
                    return

            self._ensure_figure_canvas()
            assert self.axes is not None
            assert self.figure is not None

            if any(item["secondary"] for item in plot_items):
                self.secondary_axes = self.axes.twinx()
                self.secondary_axes.set_facecolor("none")
                secondary_palette = self._theme_palette()
                self.secondary_axes.tick_params(colors=secondary_palette["plot_axis"], which="both")
                self.secondary_axes.yaxis.label.set_color(secondary_palette["plot_axis"])
                self.secondary_axes.spines["right"].set_color(secondary_palette["plot_spine"])
                colours = self._plot_colours() if hasattr(self, "_plot_colours") else EATON_PLOT_COLORS
                secondary_cycle = colours[5:] + colours[:5] if len(colours) > 5 else colours
                self.secondary_axes.set_prop_cycle(cycler(color=secondary_cycle))
            else:
                self.secondary_axes = None

            self._draw_comparison_items(plot_items)
            if not self.current_lines:
                raise ValueError("No numeric data was available for the selected comparison channels.")

            self.axes.set_title(self.title_var.get() or "Engineering Test Data")
            self.axes.set_xlabel(self.x_label_var.get() or selected_x)
            self.axes.set_ylabel(self.y_label_var.get() or "Primary Axis Signals")
            if self.secondary_axes is not None:
                self.secondary_axes.set_ylabel(self.y2_label_var.get() or "Secondary Axis Signals")
                self.secondary_axes.yaxis.set_major_locator(ticker.MaxNLocator(nbins=10))
            if hasattr(self, "_apply_plot_text_settings"):
                self._apply_plot_text_settings()
            self.axes.grid(self.grid_var.get(), which="both", alpha=0.35, color=self._theme_palette()["plot_grid"])
            self.axes.xaxis.set_major_locator(ticker.MaxNLocator(nbins=10))
            self.axes.yaxis.set_major_locator(ticker.MaxNLocator(nbins=10))

            if self.auto_fit_var.get():
                self._fill_axis_limits_from_comparison_items(plot_items)
                self._apply_current_axis_limits()
            else:
                self._apply_manual_axis_limits(limits, y2_limits)

            self._plot_limit_lines()
            self._apply_legend_or_panel()
            self.figure.tight_layout()
            self._draw_figure()
            self._disconnect_cursor_readout_for_comparison()
            self.update_stats()
            self.update_comparison_stats()
            self.update_raw_data_view()
            if hasattr(self, "limit_summary_text"):
                self._set_text_widget(self.limit_summary_text, self._calculate_limit_margins())
            self._current_plot_profile()["generated"] = True
            self._capture_current_plot_profile()
            if skipped:
                self._set_run_status(f"Comparison plot generated. Skipped {len(skipped)} missing/non-numeric channel(s).")
            else:
                self._set_run_status("Comparison plot generated.")
        except Exception as exc:
            messagebox.showerror("Comparison Plot", str(exc))

    def _enabled_runs(self) -> list[dict[str, Any]]:
        return [
            run
            for run in self.runs
            if run.get("enabled", True) and isinstance(run.get("df"), pd.DataFrame)
        ]

    def _comparison_common_x_range(self, runs: list[dict[str, Any]], selected_x: str) -> Optional[tuple[float, float]]:
        mins: list[float] = []
        maxes: list[float] = []
        for run in runs:
            df = run.get("df")
            if not isinstance(df, pd.DataFrame) or selected_x not in df.columns:
                continue
            x = numeric_series(df[selected_x]).dropna()
            if x.empty:
                continue
            mins.append(float(x.min()))
            maxes.append(float(x.max()))
        if not mins or not maxes:
            return None
        common_min = max(mins)
        common_max = min(maxes)
        if common_min >= common_max:
            return None
        return common_min, common_max

    def _comparison_plot_items(
        self,
        runs: list[dict[str, Any]],
        selected_x: str,
        y_columns: list[str],
        common_range: Optional[tuple[float, float]],
    ) -> tuple[list[dict[str, Any]], list[str]]:
        plot_items: list[dict[str, Any]] = []
        skipped: list[str] = []
        secondary_y = set(self.selected_secondary_y_columns())
        for run in runs:
            df = run.get("df")
            if not isinstance(df, pd.DataFrame):
                skipped.append(f"{run.get('name', 'Run')}: no dataframe")
                continue
            for channel in y_columns:
                if channel not in df.columns:
                    self._ensure_run_has_calculated_channel(run, channel)
                if channel not in df.columns:
                    skipped.append(f"{run.get('name', 'Run')}: missing '{channel}'")
                    continue
                x_column = _matching_x_column_for_y(selected_x, channel, df.columns)
                if x_column not in df.columns:
                    skipped.append(f"{run.get('name', 'Run')}: missing X column '{selected_x}' for '{channel}'")
                    continue
                frame = self._comparison_channel_frame(df, x_column, channel, common_range)
                if frame.empty:
                    skipped.append(f"{run.get('name', 'Run')}: no numeric data for '{channel}'")
                    continue
                plot_items.append(
                    {
                        "run": run,
                        "channel": channel,
                        "x_column": x_column,
                        "frame": frame,
                        "secondary": channel in secondary_y,
                    }
                )
        return plot_items, skipped

    def _comparison_channel_frame(
        self,
        df: pd.DataFrame,
        x_column: str,
        y_column: str,
        common_range: Optional[tuple[float, float]],
    ) -> pd.DataFrame:
        x = numeric_series(df[x_column])
        y = numeric_series(df[y_column])
        mask = x.notna() & y.notna()
        xmin = self.parse_limit(self.analysis_xmin_var.get()) if hasattr(self, "analysis_xmin_var") else None
        xmax = self.parse_limit(self.analysis_xmax_var.get()) if hasattr(self, "analysis_xmax_var") else None
        if xmin is not None:
            mask &= x >= xmin
        if xmax is not None:
            mask &= x <= xmax
        if common_range is not None:
            mask &= x >= common_range[0]
            mask &= x <= common_range[1]
        return pd.DataFrame({"x": x[mask], "y": y[mask]}).dropna()

    def _draw_comparison_items(self, plot_items: list[dict[str, Any]]) -> None:
        plot_kind = self.plot_kind_var.get()
        use_filter = self.use_filter_var.get()
        cutoff = float(self.cutoff_var.get()) if self.cutoff_var.get().strip() else None
        order = int(float(self.filter_order_var.get())) if self.filter_order_var.get().strip() else 4
        line_width = self._default_line_width() if hasattr(self, "_default_line_width") else 1.5
        marker_style = self._default_marker_style() if hasattr(self, "_default_marker_style") else None

        for item in plot_items:
            run = item["run"]
            frame = item["frame"]
            target_axes = self.secondary_axes if item["secondary"] and self.secondary_axes is not None else self.axes
            label = self._comparison_line_label(run, item["channel"])
            y_values = frame["y"].to_numpy(dtype=float)
            if use_filter:
                fs = estimate_sampling_rate(frame["x"])
                if fs is None:
                    raise ValueError("Cannot estimate sampling frequency from the selected X-axis data.")
                if cutoff is None:
                    raise ValueError("Please enter a low-pass filter cutoff frequency.")
                y_values = lowpass_filter(y_values, cutoff_hz=cutoff, fs_hz=fs, order=order)
                label = f"{label} | LP {cutoff:g} Hz"
            if item["secondary"]:
                label = f"{label} [Right Y]"
            colour = run.get("colour") or None
            if plot_kind == "Scatter":
                artist = target_axes.scatter(frame["x"], y_values, s=14, label=label, color=colour)
            elif plot_kind == "Line + Markers":
                (artist,) = target_axes.plot(frame["x"], y_values, marker=marker_style or "o", markersize=3, linewidth=line_width, label=label, color=colour)
            else:
                (artist,) = target_axes.plot(frame["x"], y_values, marker=marker_style, linewidth=line_width, label=label, color=colour)
            self.current_lines.append(artist)

    def _comparison_line_label(self, run: dict[str, Any], channel: str) -> str:
        if self.comparison_prefix_legend_var.get():
            return f"{run.get('name', 'Run')} | {channel}"
        return channel

    def _comparison_limits_have_visible_data(
        self,
        plot_items: list[dict[str, Any]],
        limits,
        y2_limits,
    ) -> bool:
        xmin, xmax, ymin, ymax = limits
        y2min, y2max = y2_limits
        for item in plot_items:
            frame = item["frame"]
            mask = pd.Series(True, index=frame.index)
            if xmin is not None:
                mask &= frame["x"] >= xmin
            if xmax is not None:
                mask &= frame["x"] <= xmax
            if item["secondary"]:
                if y2min is not None:
                    mask &= frame["y"] >= y2min
                if y2max is not None:
                    mask &= frame["y"] <= y2max
            else:
                if ymin is not None:
                    mask &= frame["y"] >= ymin
                if ymax is not None:
                    mask &= frame["y"] <= ymax
            if mask.any():
                return True
        return False

    def _fill_axis_limits_from_comparison_items(self, plot_items: list[dict[str, Any]]) -> None:
        x_values: list[float] = []
        primary_values: list[float] = []
        secondary_values: list[float] = []
        for item in plot_items:
            frame = item["frame"]
            x_values.extend(float(value) for value in frame["x"].dropna())
            target = secondary_values if item["secondary"] else primary_values
            target.extend(float(value) for value in frame["y"].dropna())

        limit_x_range, limit_y_range = self._get_active_limit_ranges()
        if limit_x_range is not None:
            x_values.extend([limit_x_range[0], limit_x_range[1]])
        if limit_y_range is not None:
            primary_values.extend([limit_y_range[0], limit_y_range[1]])

        if x_values:
            self.xmin_var.set(f"{min(x_values):.6g}")
            self.xmax_var.set(f"{max(x_values):.6g}")
        if primary_values:
            self.ymin_var.set(f"{min(primary_values):.6g}")
            self.ymax_var.set(f"{self._axis_upper_margin(max(primary_values), min(primary_values)):.6g}")
        if secondary_values:
            self.y2min_var.set(f"{min(secondary_values):.6g}")
            self.y2max_var.set(f"{self._axis_upper_margin(max(secondary_values), min(secondary_values)):.6g}")

    def _apply_current_axis_limits(self) -> None:
        self._apply_manual_axis_limits(self.manual_limits(), self.secondary_manual_limits())

    def _apply_manual_axis_limits(self, limits, y2_limits) -> None:
        xmin, xmax, ymin, ymax = limits
        y2min, y2max = y2_limits
        if xmin is not None or xmax is not None:
            self.axes.set_xlim(left=xmin, right=xmax)
            if self.secondary_axes is not None:
                self.secondary_axes.set_xlim(left=xmin, right=xmax)
        if ymin is not None or ymax is not None:
            self.axes.set_ylim(bottom=ymin, top=ymax)
        if self.secondary_axes is not None and (y2min is not None or y2max is not None):
            self.secondary_axes.set_ylim(bottom=y2min, top=y2max)

    def _disconnect_cursor_readout_for_comparison(self) -> None:
        if self.canvas is not None:
            for cid_name in ("_cursor_cid", "_cursor_click_cid", "_cursor_key_cid"):
                cid = getattr(self, cid_name, None)
                if cid is not None:
                    try:
                        self.canvas.mpl_disconnect(cid)
                    except Exception:
                        pass
                    setattr(self, cid_name, None)
        if hasattr(self, "_clear_cursor_points"):
            self._clear_cursor_points()
        if hasattr(self, "_set_cursor_text"):
            self._set_cursor_text("Comparison plot generated. Cursor readout is available for single-run plots.")

    # ------------------------------------------------------------------
    # Session persistence helpers
    # ------------------------------------------------------------------
    def _serialisable_runs(self) -> list[dict[str, Any]]:
        return [
            {
                "name": run.get("name", f"Run {index + 1}"),
                "filepath": str(run.get("filepath", "")),
                "sheet_name": run.get("sheet_name", ""),
                "enabled": bool(run.get("enabled", True)),
                "colour": run.get("colour", EATON_PLOT_COLORS[index % len(EATON_PLOT_COLORS)]),
            }
            for index, run in enumerate(self.runs)
        ]

    def _restore_runs_from_session(self, session: dict[str, Any]) -> tuple[list[str], list[str]]:
        raw_runs = session.get("runs", [])
        self.comparison_mode_enabled.set(bool(session.get("comparison_mode_enabled", False)))
        self.comparison_common_x_range_var.set(bool(session.get("comparison_common_x_range", False)))
        self.comparison_prefix_legend_var.set(bool(session.get("comparison_prefix_legend", True)))
        self.runs = []

        missing: list[str] = []
        restored_original_indexes: list[int] = []
        if not isinstance(raw_runs, list):
            raw_runs = []
        for original_index, raw_run in enumerate(raw_runs):
            if not isinstance(raw_run, dict):
                continue
            path = Path(str(raw_run.get("filepath", "")))
            if not path.exists():
                missing.append(str(path))
                continue
            sheet_name = str(raw_run.get("sheet_name", "") or "")
            try:
                df = load_data(path, sheet_name or None, settings_manager=getattr(self, "settings_manager", None))
            except Exception as exc:
                missing.append(f"{path}: {exc}")
                continue
            self.runs.append(
                self._make_run_entry(
                    name=str(raw_run.get("name", f"Run {len(self.runs) + 1}")),
                    filepath=path,
                    sheet_name=sheet_name,
                    df=df,
                    enabled=bool(raw_run.get("enabled", True)),
                    colour=str(raw_run.get("colour", self._next_run_colour())),
                )
            )
            restored_original_indexes.append(original_index)

        if not self.runs:
            self._clear_active_run_state()
            self.refresh_runs_view()
            return missing, []

        requested_active = int(session.get("active_run_index", 0))
        if requested_active in restored_original_indexes:
            active_index = restored_original_indexes.index(requested_active)
        else:
            active_index = 0
        calculation_errors = self._set_active_run_index(active_index, preserve_selection=False, capture_profile=False)
        return missing, calculation_errors

    def comparison_plot_data_for_active_run(self) -> PlotData:
        return self.prepare_plot_data()
