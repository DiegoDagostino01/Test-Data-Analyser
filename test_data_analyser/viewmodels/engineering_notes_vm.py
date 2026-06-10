"""Engineering-notes viewmodel.

Coordinates the structured engineering notes attached to the analysis through the
framework-independent :class:`EngineeringNotes` domain model. Owns the field
definitions (key, label, hint) the UI renders, reads/writes the notes on
:class:`AppState`, and formats the compiled report text. Holds no UI objects.
"""
from __future__ import annotations

from typing import Optional

from ..domain import EngineeringNotes
from .app_state import AppState

# (key, label, hint) for each structured note field, in display order.
_FIELD_DEFINITIONS: list[tuple[str, str, str]] = [
    ("objective", "Test Objective / Purpose", "What question is this plot or analysis intended to answer?"),
    ("test_article", "Test Article / Configuration", "Unit, serial number, build standard, configuration, rig, instrumentation, or setup state."),
    ("conditions", "Test Conditions / Setup", "Operating conditions, command state, fluid, temperature, pressure, flow, voltage, speed, or relevant boundaries."),
    ("observations", "Key Observations", "What is visible in the data? Capture trends, peaks, dips, offsets, instability, repeatability, and notable behaviour."),
    ("rationale", "Engineering Rationale / Interpretation", "Why do the observations matter? Link evidence to likely engineering causes, acceptance logic, or physical behaviour."),
    ("anomalies", "Anomalies / Deviations / Data Quality", "Unexpected behaviour, invalid runs, rig limitations, measurement concerns, missing data, or reasons to exclude data."),
    ("comparison", "Comparison / Acceptance Position", "Comparison against requirement, previous run, reference data, acceptance limit, or expected performance."),
    ("actions", "Actions / Follow-up", "Open actions, retest needs, report updates, review questions, or recommended next steps."),
    ("report_summary", "Report / Email Summary", "Short conclusion written in a form that can be pasted directly into a report or email."),
]


class EngineeringNotesViewModel:
    def __init__(self, state: AppState) -> None:
        self.state = state

    @staticmethod
    def field_definitions() -> list[tuple[str, str, str]]:
        return list(_FIELD_DEFINITIONS)

    @staticmethod
    def field_keys() -> list[str]:
        return [key for key, _label, _hint in _FIELD_DEFINITIONS]

    def get_notes(self) -> dict[str, str]:
        """Return the current notes as a complete structured dict (blank-filled)."""
        notes = EngineeringNotes.from_dict(self.state.engineering_notes or {})
        return notes.to_dict()

    def set_notes(self, notes: object) -> None:
        """Replace the stored notes from a dict or legacy free-text string."""
        self.state.engineering_notes = EngineeringNotes.from_dict(notes).to_dict()

    def update_field(self, key: str, value: str) -> None:
        """Update a single note field in place."""
        notes = self.get_notes()
        if key in notes:
            notes[key] = value
            self.state.engineering_notes = notes

    def clear(self) -> None:
        """Reset every note field to blank."""
        self.state.engineering_notes = EngineeringNotes().to_dict()

    def report_text(
        self,
        *,
        file_name: Optional[str] = None,
        x_axis: Optional[str] = None,
        y_axis: Optional[str] = None,
    ) -> str:
        """Return the compiled report/email text for the current notes.

        The optional context (file, X/Y axes) is included in the header, matching
        the structured engineering report layout. Empty fields are omitted.
        """
        notes = self.get_notes()
        body: list[str] = []
        for key, label, _hint in _FIELD_DEFINITIONS:
            value = (notes.get(key, "") or "").strip()
            if value:
                body += [label.upper(), value, ""]
        if not body:
            return "No engineering notes have been entered yet."
        header = [
            "ENGINEERING ANALYSIS NOTES",
            f"File: {file_name or 'Not loaded'}",
            f"X-axis: {x_axis or ''}",
            f"Y-axis: {y_axis or ''}",
            "",
        ]
        return "\n".join(header + body).strip()
