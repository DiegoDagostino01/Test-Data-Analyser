"""Run / comparison / calculated-channel domain models.

Framework-independent dataclasses for the Runs & Comparison feature and the
Maths (calculated) channels. They mirror the dictionary structures currently
serialised into JSON sessions so existing sessions keep loading.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .conversions import _int, _mapping, _string, _string_list


@dataclass
class RunMetadata:
    """Metadata describing a single loaded run/file in the comparison view.

    The actual dataframe is intentionally not stored here; it is re-loaded from
    ``filepath``/``sheet_name`` when a session is restored.
    """

    name: str = ""
    filepath: str = ""
    sheet_name: str = ""
    enabled: bool = True
    colour: str = ""

    @classmethod
    def from_dict(cls, value: object) -> "RunMetadata":
        data = _mapping(value)
        return cls(
            name=_string(data.get("name")),
            filepath=_string(data.get("filepath")),
            sheet_name=_string(data.get("sheet_name")),
            enabled=bool(data.get("enabled", True)),
            colour=_string(data.get("colour")),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "filepath": self.filepath,
            "sheet_name": self.sheet_name,
            "enabled": self.enabled,
            "colour": self.colour,
        }


@dataclass
class ComparisonSettings:
    """Top-level Runs/Comparison settings stored alongside a session."""

    comparison_mode_enabled: bool = False
    comparison_common_x_range: bool = False
    comparison_prefix_legend: bool = True
    active_run_index: int = -1

    @classmethod
    def from_dict(cls, value: object) -> "ComparisonSettings":
        data = _mapping(value)
        return cls(
            comparison_mode_enabled=bool(data.get("comparison_mode_enabled", False)),
            comparison_common_x_range=bool(data.get("comparison_common_x_range", False)),
            comparison_prefix_legend=bool(data.get("comparison_prefix_legend", True)),
            active_run_index=_int(data.get("active_run_index", -1), -1),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "comparison_mode_enabled": self.comparison_mode_enabled,
            "comparison_common_x_range": self.comparison_common_x_range,
            "comparison_prefix_legend": self.comparison_prefix_legend,
            "active_run_index": self.active_run_index,
        }


@dataclass
class CalculatedChannelDefinition:
    """A single Maths (calculated) channel definition."""

    name: str = ""
    formula: str = ""
    description: str = ""
    enabled: bool = True
    created_from_columns: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: object, *, fallback_name: str = "") -> "CalculatedChannelDefinition":
        data = _mapping(value)
        name = _string(data.get("name") or fallback_name).strip()
        formula = _string(data.get("formula")).strip()
        return cls(
            name=name,
            formula=formula,
            description=_string(data.get("description")),
            enabled=bool(data.get("enabled", True)),
            created_from_columns=_string_list(data.get("created_from_columns")),
        )

    @property
    def is_valid(self) -> bool:
        return bool(self.name and self.formula)

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "formula": self.formula,
            "description": self.description,
            "enabled": self.enabled,
            "created_from_columns": list(self.created_from_columns),
        }
