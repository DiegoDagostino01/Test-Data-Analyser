"""Qt-only Basic and Advanced experience-mode policy."""
from __future__ import annotations

from enum import Enum


class UserExperienceMode(str, Enum):
    BASIC = "basic"
    ADVANCED = "advanced"

    @classmethod
    def from_value(cls, value: object) -> "UserExperienceMode":
        if isinstance(value, cls):
            return value
        try:
            return cls(str(value).strip().lower())
        except ValueError:
            return cls.ADVANCED


BASIC_HIDDEN_PANEL_IDS = frozenset(
    {
        "maths.channels",
        "compare.points",
        "requirements.limits",
        "notes.engineering",
    }
)

BASIC_HIDDEN_COMMAND_IDS = frozenset(
    {
        "analysis.maths.show",
        "analysis.pointCompare.show",
        "requirements.limits.show",
        "requirements.margins.show",
        "requirements.refresh",
        "reporting.notes.show",
        "reporting.notes.refresh",
        "reporting.notes.copy",
        "reporting.notes.clear",
        "panel.show.maths.channels",
        "panel.show.compare.points",
        "panel.show.requirements.limits",
        "panel.show.notes.engineering",
        "workspace.apply.analysis",
        "workspace.apply.comparison",
        "workspace.apply.reporting",
        "workspace.apply.dataEditing",
        "workspace.saveCustom",
        "workspace.restoreCustom",
    }
)