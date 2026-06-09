"""Structured engineering-notes domain model.

Framework-independent representation of the structured engineering notes that
are attached to each plot profile. ``from_dict`` accepts both the structured
dictionary form and the historical free-text string form so older sessions keep
loading.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .conversions import _mapping, _string


@dataclass
class EngineeringNotes:
    schema: str = "structured_engineering_notes_v1"
    objective: str = ""
    test_article: str = ""
    conditions: str = ""
    observations: str = ""
    rationale: str = ""
    anomalies: str = ""
    comparison: str = ""
    actions: str = ""
    report_summary: str = ""

    @classmethod
    def from_dict(cls, value: object) -> "EngineeringNotes":
        if isinstance(value, str):
            return cls(observations=value)
        data = _mapping(value)
        return cls(
            schema=_string(data.get("schema", "structured_engineering_notes_v1"), "structured_engineering_notes_v1"),
            objective=_string(data.get("objective")),
            test_article=_string(data.get("test_article")),
            conditions=_string(data.get("conditions")),
            observations=_string(data.get("observations")),
            rationale=_string(data.get("rationale")),
            anomalies=_string(data.get("anomalies")),
            comparison=_string(data.get("comparison")),
            actions=_string(data.get("actions")),
            report_summary=_string(data.get("report_summary")),
        )

    def to_dict(self) -> dict[str, str]:
        return asdict(self)
