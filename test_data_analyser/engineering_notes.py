from __future__ import annotations

from typing import Any
import tkinter as tk
from tkinter import ttk, messagebox

from .config import EATON_CARD_BG, EATON_DARK_TEXT, EATON_SECONDARY_TEXT
from .widgets import ScrollableFrame


class EngineeringNotesMixin:
    """Structured engineering notes UI and report-text behaviour.

    This module owns the Engineering Notes tab, note capture/restoration, report
    formatting, clipboard copy, and note clearing actions.
    """

    def _engineering_note_field_definitions(self) -> list[tuple[str, str, int, str]]:
        return [
            ("objective", "Test Objective / Purpose", 3, "What question is this plot or analysis intended to answer?"),
            ("test_article", "Test Article / Configuration", 3, "Unit, serial number, build standard, configuration, rig, instrumentation, or setup state."),
            ("conditions", "Test Conditions / Setup", 3, "Operating conditions, command state, fluid, temperature, pressure, flow, voltage, speed, or relevant boundaries."),
            ("observations", "Key Observations", 5, "What is visible in the data? Capture trends, peaks, dips, offsets, instability, repeatability, and notable behaviour."),
            ("rationale", "Engineering Rationale / Interpretation", 5, "Why do the observations matter? Link evidence to likely engineering causes, acceptance logic, or physical behaviour."),
            ("anomalies", "Anomalies / Deviations / Data Quality", 4, "Unexpected behaviour, invalid runs, rig limitations, measurement concerns, missing data, or reasons to exclude data."),
            ("comparison", "Comparison / Acceptance Position", 4, "Comparison against requirement, previous run, reference data, acceptance limit, or expected performance."),
            ("actions", "Actions / Follow-up", 4, "Open actions, retest needs, report updates, review questions, or recommended next steps."),
            ("report_summary", "Report / Email Summary", 4, "Short conclusion written in a form that can be pasted directly into a report or email."),
        ]

    def _blank_engineering_notes(self) -> dict[str, str]:
        notes = {"schema": "structured_engineering_notes_v1"}
        for key, _label, _height, _hint in self._engineering_note_field_definitions():
            notes[key] = ""
        return notes

    def _build_structured_engineering_notes_tab(self, parent: ttk.Frame) -> None:
        parent.rowconfigure(1, weight=1)
        parent.columnconfigure(0, weight=1)
        controls = ttk.Frame(parent)
        controls.grid(row=0, column=0, sticky="ew", padx=6, pady=(4, 2))
        ttk.Button(controls, text="Refresh Report Text", command=self._refresh_engineering_notes_report).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Copy Notes for Report/Email", command=self._copy_engineering_notes_to_clipboard).pack(side="left", padx=(0, 6))
        ttk.Button(controls, text="Clear Notes", command=self._clear_engineering_notes).pack(side="left")
        notes_scroll = ScrollableFrame(parent, width=900)
        notes_scroll.grid(row=1, column=0, sticky="nsew", padx=6, pady=(0, 6))
        self.engineering_note_widgets = {}
        for key, label, height, hint in self._engineering_note_field_definitions():
            frame = ttk.LabelFrame(notes_scroll.inner, text=label, style="Card.TLabelframe")
            frame.pack(fill="x", expand=True, padx=4, pady=8)
            ttk.Label(frame, text=hint, foreground=EATON_SECONDARY_TEXT, wraplength=900).pack(anchor="w", padx=6, pady=(4, 2))
            text_box = tk.Text(frame, height=height, wrap="word", bg=EATON_CARD_BG, fg=EATON_DARK_TEXT, relief="solid", bd=1)
            text_box.pack(fill="x", expand=True, padx=6, pady=(0, 6))
            text_box.bind("<FocusOut>", lambda _event: self._capture_current_plot_profile())
            self.engineering_note_widgets[key] = text_box
        preview_frame = ttk.LabelFrame(notes_scroll.inner, text="Compiled Notes Preview", style="Card.TLabelframe")
        preview_frame.pack(fill="both", expand=True, padx=4, pady=8)
        ttk.Label(preview_frame, text="Use this generated text for reports, emails, design reviews, or test summaries.", foreground=EATON_SECONDARY_TEXT, wraplength=900).pack(anchor="w", padx=6, pady=(4, 2))
        self.engineering_notes_report_text = tk.Text(preview_frame, height=10, wrap="word", bg=EATON_CARD_BG, fg=EATON_DARK_TEXT, relief="solid", bd=1)
        self.engineering_notes_report_text.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self._set_text_widget(self.engineering_notes_report_text, "Structured engineering notes will appear here after clicking Refresh Report Text.")

    def _get_engineering_notes(self) -> dict[str, str]:
        notes = self._blank_engineering_notes()
        for key, widget in getattr(self, "engineering_note_widgets", {}).items():
            notes[key] = widget.get("1.0", "end-1c")
        return notes

    def _set_engineering_notes(self, notes: Any) -> None:
        if not getattr(self, "engineering_note_widgets", None):
            return
        structured = self._blank_engineering_notes()
        if isinstance(notes, dict):
            for key in structured:
                if key in notes:
                    structured[key] = str(notes.get(key, ""))
        elif isinstance(notes, str):
            structured["observations"] = notes
        for key, widget in self.engineering_note_widgets.items():
            widget.delete("1.0", "end")
            widget.insert("1.0", structured.get(key, ""))
        self._refresh_engineering_notes_report()

    def _format_engineering_notes_for_report(self) -> str:
        notes = self._get_engineering_notes()
        profile_name = self._current_plot_profile().get("name", "Plot") if self.plot_profiles else "Plot"
        lines = ["ENGINEERING ANALYSIS NOTES", f"Plot/Profile: {profile_name}", f"File: {self.filepath.name if self.filepath else 'Not loaded'}", f"Title: {self.title_var.get() if hasattr(self, 'title_var') else ''}", f"X-axis: {self.x_col_var.get() if hasattr(self, 'x_col_var') else ''}", f"Y-axis: {', '.join(self.selected_y_columns()) if hasattr(self, 'y_vars') else ''}", ""]
        for key, label, _height, _hint in self._engineering_note_field_definitions():
            value = notes.get(key, "").strip()
            if value:
                lines += [label.upper(), value, ""]
        return "\n".join(lines).strip() or "No engineering notes have been entered yet."

    def _refresh_engineering_notes_report(self) -> None:
        if self.engineering_notes_report_text is None:
            return
        self._set_text_widget(self.engineering_notes_report_text, self._format_engineering_notes_for_report())
        self._capture_current_plot_profile()

    def _copy_engineering_notes_to_clipboard(self) -> None:
        report_text = self._format_engineering_notes_for_report()
        self.root.clipboard_clear(); self.root.clipboard_append(report_text); self.root.update()
        self._capture_current_plot_profile()
        messagebox.showinfo("Engineering Notes", "Structured engineering notes copied to clipboard.")

    def _clear_engineering_notes(self) -> None:
        confirm = self._setting("general_ui", "confirm_before_delete", True) if hasattr(self, "_setting") else True
        if confirm and not messagebox.askyesno("Clear Engineering Notes", "Clear all structured engineering note fields for this plot profile?"):
            return
        for widget in getattr(self, "engineering_note_widgets", {}).values():
            widget.delete("1.0", "end")
        self._refresh_engineering_notes_report(); self._capture_current_plot_profile()

    # ------------------------------------------------------------------
    # Requirement / limit lines
    # ------------------------------------------------------------------
