from __future__ import annotations

from pathlib import Path
from typing import Any
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from .config import __version__
from .data_io import get_excel_sheets, load_data
from .models import normalise_plot_profile, plot_profile_to_dict


class ProfileStateMixin:
    """Plot-profile and session persistence behaviour.

    This mixin is intentionally a mostly-direct extraction from the original
    GUI implementation. Keeping the method bodies familiar makes the refactor
    low risk while moving profile/session responsibilities out of gui_base.py.
    """

    def _make_default_plot_profile(self, name: str) -> dict[str, Any]:
        return normalise_plot_profile({
            "name": name,
            "x_column": self.x_col_var.get() if hasattr(self, "x_col_var") else "",
            "y_columns": self.selected_y_columns() if hasattr(self, "y_vars") else [],
            "secondary_y_columns": self.selected_secondary_y_columns() if hasattr(self, "secondary_y_vars") else [],
            "title": self.title_var.get() if hasattr(self, "title_var") else "Engineering Test Data",
            "x_label": self.x_label_var.get() if hasattr(self, "x_label_var") else "",
            "y_label": self.y_label_var.get() if hasattr(self, "y_label_var") else "Selected Signals",
            "secondary_y_label": self.y2_label_var.get() if hasattr(self, "y2_label_var") else "",
            "plot_kind": self.plot_kind_var.get() if hasattr(self, "plot_kind_var") else "Line",
            "grid": self.grid_var.get() if hasattr(self, "grid_var") else True,
            "auto_fit_axes": self.auto_fit_var.get() if hasattr(self, "auto_fit_var") else True,
            "axis_limits": {
                "xmin": self.xmin_var.get() if hasattr(self, "xmin_var") else "",
                "xmax": self.xmax_var.get() if hasattr(self, "xmax_var") else "",
                "ymin": self.ymin_var.get() if hasattr(self, "ymin_var") else "",
                "ymax": self.ymax_var.get() if hasattr(self, "ymax_var") else "",
                "y2min": self.y2min_var.get() if hasattr(self, "y2min_var") else "",
                "y2max": self.y2max_var.get() if hasattr(self, "y2max_var") else "",
            },
            "analysis_window": {
                "start_x": self.analysis_xmin_var.get() if hasattr(self, "analysis_xmin_var") else "",
                "end_x": self.analysis_xmax_var.get() if hasattr(self, "analysis_xmax_var") else "",
            },
            "filter": {
                "enabled": self.use_filter_var.get() if hasattr(self, "use_filter_var") else False,
                "cutoff_hz": self.cutoff_var.get() if hasattr(self, "cutoff_var") else "",
                "order": self.filter_order_var.get() if hasattr(self, "filter_order_var") else "4",
            },
            "legend": {
                "max_inline_entries": self.legend_threshold_var.get() if hasattr(self, "legend_threshold_var") else "10",
                "location": self.legend_location_var.get() if hasattr(self, "legend_location_var") else "best",
            },
            "raw_data": {
                "rows_to_display": self.raw_data_row_limit_var.get(),
                "apply_analysis_window": self.raw_data_apply_window_var.get(),
                "hide_blank_rows": self.raw_data_drop_blank_rows_var.get(),
            },
            "engineering_notes": self._blank_engineering_notes(),
            "limit_lines": [],
            "generated": False,
        })

    def _initialise_plot_profiles(self) -> None:
        if self.plot_profiles:
            return
        self.plot_profiles = [self._make_default_plot_profile("Plot 1")]
        self.active_plot_profile_index = 0
        self._refresh_plot_profile_tabs()
        self._apply_plot_profile(0, regenerate=False)

    def _current_plot_profile(self) -> dict[str, Any]:
        if not self.plot_profiles:
            self._initialise_plot_profiles()
        self.active_plot_profile_index = max(0, min(self.active_plot_profile_index, len(self.plot_profiles)-1))
        return self.plot_profiles[self.active_plot_profile_index]

    def _capture_current_plot_profile(self) -> None:
        if self._profile_switch_in_progress or not self.plot_profiles:
            return
        profile = self._current_plot_profile()
        profile.update({
            "x_column": self.x_col_var.get(),
            "y_columns": self.selected_y_columns(),
            "secondary_y_columns": self.selected_secondary_y_columns(),
            "title": self.title_var.get(),
            "x_label": self.x_label_var.get(),
            "y_label": self.y_label_var.get(),
            "secondary_y_label": self.y2_label_var.get(),
            "plot_kind": self.plot_kind_var.get(),
            "grid": self.grid_var.get(),
            "auto_fit_axes": self.auto_fit_var.get(),
            "axis_limits": {"xmin": self.xmin_var.get(), "xmax": self.xmax_var.get(), "ymin": self.ymin_var.get(), "ymax": self.ymax_var.get(), "y2min": self.y2min_var.get(), "y2max": self.y2max_var.get()},
            "analysis_window": {"start_x": self.analysis_xmin_var.get(), "end_x": self.analysis_xmax_var.get()},
            "filter": {"enabled": self.use_filter_var.get(), "cutoff_hz": self.cutoff_var.get(), "order": self.filter_order_var.get()},
            "legend": {"max_inline_entries": self.legend_threshold_var.get(), "location": self.legend_location_var.get()},
            "raw_data": {"rows_to_display": self.raw_data_row_limit_var.get(), "apply_analysis_window": self.raw_data_apply_window_var.get(), "hide_blank_rows": self.raw_data_drop_blank_rows_var.get()},
            "engineering_notes": self._get_engineering_notes() if hasattr(self, "engineering_note_widgets") else self._blank_engineering_notes(),
            "limit_lines": self._normalised_limit_lines() if hasattr(self, "limit_lines") else [],
        })

    def _apply_plot_profile(self, index: int, regenerate: bool = True) -> None:
        if not self.plot_profiles:
            return
        self._profile_switch_in_progress = True
        try:
            self.active_plot_profile_index = max(0, min(index, len(self.plot_profiles)-1))
            profile = normalise_plot_profile(self.plot_profiles[self.active_plot_profile_index])
            self.plot_profiles[self.active_plot_profile_index] = profile
            x_column = profile.get("x_column", self.x_col_var.get())
            if self.df is not None and x_column and x_column not in self.df.columns:
                available_columns = [str(column) for column in self.df.columns]
                x_column = self.x_col_var.get() if self.x_col_var.get() in available_columns else (available_columns[0] if available_columns else "")
            self.x_col_var.set(x_column)
            selected_y = set(profile.get("y_columns", []))
            selected_secondary_y = set(profile.get("secondary_y_columns", []))
            for col, var in self.y_vars.items():
                var.set(col in selected_y)
            for col, var in self.secondary_y_vars.items():
                var.set(col in selected_secondary_y and col in selected_y)
            self.title_var.set(profile.get("title", "Engineering Test Data"))
            self.x_label_var.set(profile.get("x_label", ""))
            self.y_label_var.set(profile.get("y_label", "Selected Signals"))
            if hasattr(self, "y2_label_var"):
                self.y2_label_var.set(profile.get("secondary_y_label", ""))
            self.plot_kind_var.set(profile.get("plot_kind", "Line"))
            self.grid_var.set(bool(profile.get("grid", True)))
            self.auto_fit_var.set(bool(profile.get("auto_fit_axes", True)))
            limits = profile.get("axis_limits", {})
            self.xmin_var.set(limits.get("xmin", "")); self.xmax_var.set(limits.get("xmax", ""))
            self.ymin_var.set(limits.get("ymin", "")); self.ymax_var.set(limits.get("ymax", ""))
            self.y2min_var.set(limits.get("y2min", "")); self.y2max_var.set(limits.get("y2max", ""))
            window = profile.get("analysis_window", {})
            self.analysis_xmin_var.set(window.get("start_x", "")); self.analysis_xmax_var.set(window.get("end_x", ""))
            filt = profile.get("filter", {})
            self.use_filter_var.set(bool(filt.get("enabled", False)))
            self.cutoff_var.set(filt.get("cutoff_hz", "")); self.filter_order_var.set(filt.get("order", "4"))
            legend = profile.get("legend", {})
            self.legend_threshold_var.set(legend.get("max_inline_entries", self.legend_threshold_var.get()))
            self.legend_location_var.set(legend.get("location", self.legend_location_var.get()))
            raw = profile.get("raw_data", {})
            self.raw_data_row_limit_var.set(raw.get("rows_to_display", "All"))
            self.raw_data_apply_window_var.set(bool(raw.get("apply_analysis_window", True)))
            self.raw_data_drop_blank_rows_var.set(bool(raw.get("hide_blank_rows", True)))
            self._set_engineering_notes(profile.get("engineering_notes", self._blank_engineering_notes()))
            self.limit_lines = profile.get("limit_lines", []) if isinstance(profile.get("limit_lines", []), list) else []
            self.active_limit_line_index = 0
            self._refresh_limit_widgets()
            self._rebuild_y_checkboxes()
            self.toggle_axis_entries()
            self.update_range_preview(); self.update_stats(); self.mark_raw_data_stale()
        finally:
            self._profile_switch_in_progress = False
        if regenerate and profile.get("generated", False) and self.df is not None:
            self.root.after(50, self.generate_plot)

    def _refresh_plot_profile_tabs(self) -> None:
        if not hasattr(self, "plot_profile_notebook"):
            return
        self._profile_switch_in_progress = True
        try:
            for tab in self.plot_profile_notebook.tabs():
                self.plot_profile_notebook.forget(tab)
            for profile in self.plot_profiles:
                frame = ttk.Frame(self.plot_profile_notebook)
                self.plot_profile_notebook.add(frame, text=profile.get("name", "Plot"))
            if self.plot_profiles:
                self.plot_profile_notebook.select(self.active_plot_profile_index)
        finally:
            self._profile_switch_in_progress = False

    def on_plot_profile_tab_changed(self, _event=None) -> None:
        if self._profile_switch_in_progress or not self.plot_profiles:
            return
        self._capture_current_plot_profile()
        selected = self.plot_profile_notebook.index(self.plot_profile_notebook.select())
        self._apply_plot_profile(selected)

    def add_plot_profile(self) -> None:
        self._capture_current_plot_profile()
        profile = self._make_default_plot_profile(f"Plot {len(self.plot_profiles)+1}")
        profile["y_columns"] = []
        profile["secondary_y_columns"] = []
        profile["x_label"] = ""
        profile["y_label"] = "Selected Signals"
        profile["secondary_y_label"] = ""
        profile["engineering_notes"] = ""
        profile["generated"] = False
        self.plot_profiles.append(profile)
        self.active_plot_profile_index = len(self.plot_profiles)-1
        self._refresh_plot_profile_tabs(); self._apply_plot_profile(self.active_plot_profile_index, regenerate=False)

    def duplicate_plot_profile(self) -> None:
        self._capture_current_plot_profile()
        import copy
        profile = copy.deepcopy(self._current_plot_profile())
        profile["name"] = f"{profile.get('name', 'Plot')} Copy"
        profile["generated"] = False
        self.plot_profiles.append(profile)
        self.active_plot_profile_index = len(self.plot_profiles)-1
        self._refresh_plot_profile_tabs(); self._apply_plot_profile(self.active_plot_profile_index, regenerate=False)

    def rename_plot_profile(self) -> None:
        self._capture_current_plot_profile()
        profile = self._current_plot_profile()
        new_name = simpledialog.askstring("Rename Plot", "Plot name:", initialvalue=profile.get("name", "Plot"))
        if not new_name:
            return
        profile["name"] = new_name.strip() or profile.get("name", "Plot")
        self._refresh_plot_profile_tabs()

    def delete_plot_profile(self) -> None:
        if len(self.plot_profiles) <= 1:
            messagebox.showinfo("Delete Plot", "At least one plot tab must remain.")
            return
        confirm = self._setting("general_ui", "confirm_before_delete", True) if hasattr(self, "_setting") else True
        if confirm and not messagebox.askyesno("Delete Plot", "Delete the active plot tab?"):
            return
        del self.plot_profiles[self.active_plot_profile_index]
        self.active_plot_profile_index = min(self.active_plot_profile_index, len(self.plot_profiles)-1)
        self._refresh_plot_profile_tabs(); self._apply_plot_profile(self.active_plot_profile_index, regenerate=False)

    def save_analysis_session(self) -> None:
        try:
            self._capture_current_plot_profile()
            session = {
                "version": __version__,
                "file_path": str(self.filepath) if self.filepath else "",
                "sheet_name": self.sheet_var.get() if hasattr(self, "sheet_var") else "",
                "runs": self._serialisable_runs() if hasattr(self, "_serialisable_runs") else [],
                "active_run_index": getattr(self, "active_run_index", -1),
                "comparison_mode_enabled": self.comparison_mode_enabled.get()
                if hasattr(self, "comparison_mode_enabled")
                else False,
                "comparison_common_x_range": self.comparison_common_x_range_var.get()
                if hasattr(self, "comparison_common_x_range_var")
                else False,
                "comparison_prefix_legend": self.comparison_prefix_legend_var.get()
                if hasattr(self, "comparison_prefix_legend_var")
                else True,
                "active_plot_profile_index": self.active_plot_profile_index,
                "plot_profiles": [plot_profile_to_dict(profile) for profile in self.plot_profiles],
                "calculated_channels": self._serialisable_calculated_channels()
                if hasattr(self, "_serialisable_calculated_channels")
                else getattr(self, "calculated_channels", {}),
            }
            filename = filedialog.asksaveasfilename(title="Save analysis session", defaultextension=".json", filetypes=[("JSON session", "*.json"), ("All files", "*.*")])
            if not filename:
                return
            path = Path(filename)
            if path.suffix == "":
                path = path.with_suffix(".json")
            path.write_text(json.dumps(session, indent=2), encoding="utf-8")
            if not path.exists():
                raise RuntimeError("Session file was not created.")
            messagebox.showinfo("Analysis Session", f"Session saved successfully:\n{path}")
        except Exception as exc:
            messagebox.showerror("Save Session Error", f"Could not save the analysis session:\n\n{exc}")

    def load_analysis_session(self) -> None:
        filename = filedialog.askopenfilename(title="Load analysis session", filetypes=[("JSON session", "*.json"), ("All files", "*.*")])
        if not filename:
            return
        try:
            session = json.loads(Path(filename).read_text(encoding="utf-8"))
            if hasattr(self, "_restore_calculated_channels_from_session"):
                self._restore_calculated_channels_from_session(session.get("calculated_channels", {}))
            calculated_channel_errors: list[str] = []
            missing_run_files: list[str] = []
            restored_runs = False
            if session.get("runs") and hasattr(self, "_restore_runs_from_session"):
                missing_run_files, calculated_channel_errors = self._restore_runs_from_session(session)
                restored_runs = bool(getattr(self, "runs", []))
            if not restored_runs:
                file_path = session.get("file_path", "")
                if file_path and Path(file_path).exists():
                    self.filepath = Path(file_path)
                    self.file_label.configure(text=str(self.filepath))
                    sheets = get_excel_sheets(self.filepath)
                    if sheets:
                        self.sheet_frame.pack(fill="x", pady=(4, 0))
                        self.sheet_combo.configure(values=sheets)
                        sheet_name = session.get("sheet_name") or sheets[0]
                        self.sheet_var.set(sheet_name if sheet_name in sheets else sheets[0])
                        self.df = load_data(self.filepath, self.sheet_var.get() or None, settings_manager=getattr(self, "settings_manager", None))
                    else:
                        self.sheet_frame.pack_forget()
                        self.df = load_data(self.filepath, settings_manager=getattr(self, "settings_manager", None))
                    if hasattr(self, "recalculate_calculated_channels"):
                        calculated_channel_errors = self.recalculate_calculated_channels(
                            show_success=False,
                            show_errors=False,
                            refresh=False,
                        )
                    self.populate_columns()
                    if hasattr(self, "_sync_current_file_to_active_run"):
                        self._sync_current_file_to_active_run()
            profiles = session.get("plot_profiles")
            if not profiles:
                profiles = [self._make_default_plot_profile("Plot 1")]
                profiles[0].update({"engineering_notes": session.get("engineering_notes", self._blank_engineering_notes()), "limit_lines": session.get("limit_lines", [])})
            self.plot_profiles = [normalise_plot_profile(profile) for profile in profiles]
            if not self.plot_profiles:
                self.plot_profiles = [self._make_default_plot_profile("Plot 1")]
            self.active_plot_profile_index = int(session.get("active_plot_profile_index", 0))
            self.active_plot_profile_index = max(0, min(self.active_plot_profile_index, len(self.plot_profiles)-1))
            self._refresh_plot_profile_tabs()
            self._apply_plot_profile(self.active_plot_profile_index, regenerate=False)
            if calculated_channel_errors:
                messagebox.showwarning(
                    "Maths Channels",
                    "Some Maths Channels could not be restored:\n\n"
                    + "\n".join(calculated_channel_errors),
                )
            if missing_run_files:
                messagebox.showwarning(
                    "Runs / Comparison",
                    "Some runs could not be restored because their files were missing or could not be loaded:\n\n"
                    + "\n".join(missing_run_files),
                )
            messagebox.showinfo("Analysis Session", "Session loaded. Generate Plot to refresh the active plot if required.")
        except Exception as exc:
            messagebox.showerror("Load Session Error", str(exc))
