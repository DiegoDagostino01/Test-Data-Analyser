"""Top-level analysis-session domain model.

``SessionState`` aggregates the persisted application state: the source file,
runs/comparison settings, plot profiles, and calculated channels. It provides
``from_dict``/``to_dict`` helpers that normalise JSON sessions through the
domain models while preserving the existing on-disk key names so previously
saved sessions keep loading.

Note: legacy top-level ``engineering_notes`` / ``limit_lines`` keys (used by
very old sessions that pre-date plot profiles) are intentionally *not* owned by
this model. The UI layer still reads those raw keys as a fallback when a session
has no ``plot_profiles``, preserving the original migration behaviour.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .conversions import _int, _mapping, _string
from .plot_profile import PlotProfile, plot_profile_to_dict
from .run_model import CalculatedChannelDefinition, ComparisonSettings, RunMetadata


@dataclass
class SessionState:
    version: str = ""
    file_path: str = ""
    sheet_name: str = ""
    runs: list[RunMetadata] = field(default_factory=list)
    comparison: ComparisonSettings = field(default_factory=ComparisonSettings)
    active_plot_profile_index: int = 0
    plot_profiles: list[PlotProfile] = field(default_factory=list)
    calculated_channels: dict[str, CalculatedChannelDefinition] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, value: object) -> "SessionState":
        data = _mapping(value)

        raw_runs = data.get("runs", [])
        runs = [RunMetadata.from_dict(run) for run in raw_runs] if isinstance(raw_runs, list) else []

        raw_profiles = data.get("plot_profiles", [])
        profiles = (
            [PlotProfile.from_dict(profile) for profile in raw_profiles]
            if isinstance(raw_profiles, list)
            else []
        )

        channels: dict[str, CalculatedChannelDefinition] = {}
        raw_channels = data.get("calculated_channels", {})
        if isinstance(raw_channels, dict):
            for key, definition_value in raw_channels.items():
                definition = CalculatedChannelDefinition.from_dict(definition_value, fallback_name=str(key))
                if definition.is_valid:
                    channels[definition.name] = definition

        return cls(
            version=_string(data.get("version")),
            file_path=_string(data.get("file_path")),
            sheet_name=_string(data.get("sheet_name")),
            runs=runs,
            comparison=ComparisonSettings.from_dict(data),
            active_plot_profile_index=_int(data.get("active_plot_profile_index", 0), 0),
            plot_profiles=profiles,
            calculated_channels=channels,
        )

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "version": self.version,
            "file_path": self.file_path,
            "sheet_name": self.sheet_name,
            "runs": [run.to_dict() for run in self.runs],
            "active_plot_profile_index": self.active_plot_profile_index,
            "plot_profiles": [plot_profile_to_dict(profile) for profile in self.plot_profiles],
            "calculated_channels": {
                name: definition.to_dict() for name, definition in self.calculated_channels.items()
            },
        }
        result.update(self.comparison.to_dict())
        return result
