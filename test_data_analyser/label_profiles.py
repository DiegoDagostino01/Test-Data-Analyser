from __future__ import annotations

from typing import Any


class LabelProfileMixin:
    """Per-plot label state management.

    This mixin keeps plot labels independent per plot profile and prevents
    automatic label regeneration from overwriting labels that the user has
    manually edited.
    """

    _LABEL_FLAG_KEYS = ("title", "x_label", "y_label", "secondary_y_label")

    def _default_manual_label_flags(self) -> dict[str, bool]:
        return {key: False for key in self._LABEL_FLAG_KEYS}

    def _normalise_manual_label_flags(self, value: Any) -> dict[str, bool]:
        flags = self._default_manual_label_flags()
        if isinstance(value, dict):
            for key in flags:
                flags[key] = bool(value.get(key, False))
        return flags

    def _initialise_label_tracking(self) -> None:
        """Initialise manual-label tracking after the UI has been built."""
        self._manual_label_flags = self._default_manual_label_flags()
        self._label_trace_enabled = True
        self._auto_label_update_in_progress = False
        self._patch_auto_label_button_command()
        self._bind_label_change_tracking()

    def _bind_label_change_tracking(self) -> None:
        """Detect user edits to label fields through their Tk variables."""
        bindings = [
            ("title", getattr(self, "title_var", None)),
            ("x_label", getattr(self, "x_label_var", None)),
            ("y_label", getattr(self, "y_label_var", None)),
            ("secondary_y_label", getattr(self, "y2_label_var", None)),
        ]
        self._label_trace_ids = []
        for key, var in bindings:
            if var is None:
                continue
            trace_id = var.trace_add("write", lambda *_args, k=key: self._mark_label_as_manual(k))
            self._label_trace_ids.append((var, trace_id))

    def _mark_label_as_manual(self, key: str) -> None:
        """Mark a label as user-controlled unless the change is internal."""
        if not getattr(self, "_label_trace_enabled", False):
            return
        if getattr(self, "_auto_label_update_in_progress", False):
            return
        if getattr(self, "_profile_switch_in_progress", False):
            return
        if key not in self._LABEL_FLAG_KEYS:
            return
        if not hasattr(self, "_manual_label_flags"):
            self._manual_label_flags = self._default_manual_label_flags()
        self._manual_label_flags[key] = True
        if getattr(self, "plot_profiles", None):
            try:
                self._current_plot_profile()["manual_labels"] = dict(self._manual_label_flags)
            except Exception:
                pass

    def _patch_auto_label_button_command(self) -> None:
        """Make the existing Auto Labels button force-regenerate labels."""
        try:
            widgets = list(self.root.winfo_children())
            while widgets:
                widget = widgets.pop()
                try:
                    widgets.extend(widget.winfo_children())
                except Exception:
                    pass
                try:
                    if widget.cget("text") == "Auto Labels":
                        widget.configure(command=lambda: self.auto_labels_from_selection(force=True))
                except Exception:
                    pass
        except Exception:
            pass

    def _make_default_plot_profile(self, name: str) -> dict[str, Any]:
        profile = super()._make_default_plot_profile(name)
        profile["manual_labels"] = self._default_manual_label_flags()
        return profile

    def _capture_current_plot_profile(self) -> None:
        if getattr(self, "_profile_switch_in_progress", False) or not getattr(self, "plot_profiles", None):
            return
        super()._capture_current_plot_profile()
        try:
            self._current_plot_profile()["manual_labels"] = dict(
                getattr(self, "_manual_label_flags", self._default_manual_label_flags())
            )
        except Exception:
            pass

    def _apply_plot_profile(self, index: int, regenerate: bool = True) -> None:
        if getattr(self, "plot_profiles", None):
            safe_index = max(0, min(index, len(self.plot_profiles) - 1))
            profile = self.plot_profiles[safe_index]
            self._manual_label_flags = self._normalise_manual_label_flags(profile.get("manual_labels"))
        super()._apply_plot_profile(index, regenerate=regenerate)
        if getattr(self, "plot_profiles", None):
            safe_index = max(0, min(self.active_plot_profile_index, len(self.plot_profiles) - 1))
            profile = self.plot_profiles[safe_index]
            self._manual_label_flags = self._normalise_manual_label_flags(profile.get("manual_labels"))

    def add_plot_profile(self) -> None:
        """Create a clean independent plot profile."""
        self._capture_current_plot_profile()
        profile = self._make_default_plot_profile(f"Plot {len(self.plot_profiles)+1}")
        profile["y_columns"] = []
        profile["secondary_y_columns"] = []
        profile["x_label"] = ""
        profile["y_label"] = "Selected Signals"
        profile["secondary_y_label"] = ""
        profile["manual_labels"] = self._default_manual_label_flags()
        profile["engineering_notes"] = self._blank_engineering_notes()
        profile["limit_lines"] = []
        profile["generated"] = False
        self.plot_profiles.append(profile)
        self.active_plot_profile_index = len(self.plot_profiles) - 1
        self._manual_label_flags = self._default_manual_label_flags()
        self._refresh_plot_profile_tabs()
        self._apply_plot_profile(self.active_plot_profile_index, regenerate=False)

    def auto_labels_from_selection(self, force: bool = False) -> None:
        """Generate engineering axis labels without overwriting manual edits.

        When force=True, all label fields are regenerated and returned to
        automatic mode. This is used by the Auto Labels button.
        """
        if not hasattr(self, "x_col_var"):
            return

        if not hasattr(self, "_manual_label_flags"):
            self._manual_label_flags = self._default_manual_label_flags()

        if force:
            self._manual_label_flags = self._default_manual_label_flags()

        x_col = self.x_col_var.get()
        y_cols = self.selected_y_columns()
        secondary_y = set(self.selected_secondary_y_columns()) if hasattr(self, "secondary_y_vars") else set()
        primary_y = [col for col in y_cols if col not in secondary_y]
        secondary_cols = [col for col in y_cols if col in secondary_y]

        self._auto_label_update_in_progress = True
        try:
            if x_col and (force or not self._manual_label_flags.get("x_label", False)):
                self.x_label_var.set(x_col)
            if force or not self._manual_label_flags.get("y_label", False):
                self.y_label_var.set(self._axis_label_from_columns(primary_y, "Primary Axis Signals"))
            if hasattr(self, "y2_label_var") and (force or not self._manual_label_flags.get("secondary_y_label", False)):
                if secondary_cols:
                    self.y2_label_var.set(self._axis_label_from_columns(secondary_cols, "Secondary Axis Signals"))
                else:
                    self.y2_label_var.set("")
        finally:
            self._auto_label_update_in_progress = False

        self._capture_current_plot_profile()
