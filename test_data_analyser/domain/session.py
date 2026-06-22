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
from pathlib import PurePath, PureWindowsPath

from .conversions import _int, _mapping, _string
from .dataset import SOURCE_EXCEL, ChannelRegistry, normalise_source_type
from .plot_profile import PlotProfile, plot_profile_to_dict
from .run_model import CalculatedChannelDefinition, ComparisonSettings, RunMetadata


@dataclass
class SessionState:
    version: str = ""
    root_file_directory: str = ""
    file_path: str = ""
    sheet_name: str = ""
    data_source_type: str = SOURCE_EXCEL
    channel_registry: ChannelRegistry = field(default_factory=ChannelRegistry)
    dataset_rows: list[dict] = field(default_factory=list)
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

        file_path = _string(data.get("file_path"))
        root_file_directory = _string(data.get("root_file_directory")).strip()

        raw_rows = data.get("dataset_rows", [])
        dataset_rows = (
            [row for row in raw_rows if isinstance(row, dict)] if isinstance(raw_rows, list) else []
        )

        return cls(
            version=_string(data.get("version")),
            root_file_directory=root_file_directory or _parent_directory_text(file_path),
            file_path=file_path,
            sheet_name=_string(data.get("sheet_name")),
            data_source_type=normalise_source_type(data.get("data_source_type")),
            channel_registry=ChannelRegistry.from_dict(data.get("channel_registry")),
            dataset_rows=dataset_rows,
            runs=runs,
            comparison=ComparisonSettings.from_dict(data),
            active_plot_profile_index=_int(data.get("active_plot_profile_index", 0), 0),
            plot_profiles=profiles,
            calculated_channels=channels,
        )

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "version": self.version,
            "root_file_directory": self.root_file_directory,
            "file_path": self.file_path,
            "sheet_name": self.sheet_name,
            "data_source_type": self.data_source_type,
            "channel_registry": self.channel_registry.to_dict(),
            "dataset_rows": list(self.dataset_rows),
            "runs": [run.to_dict() for run in self.runs],
            "active_plot_profile_index": self.active_plot_profile_index,
            "plot_profiles": [plot_profile_to_dict(profile) for profile in self.plot_profiles],
            "calculated_channels": {
                name: definition.to_dict() for name, definition in self.calculated_channels.items()
            },
        }
        result.update(self.comparison.to_dict())
        return result


def _parent_directory_text(file_path: str) -> str:
    path_text = str(file_path).strip()
    if not path_text:
        return ""
    path = PureWindowsPath(path_text) if _looks_windows_path(path_text) else PurePath(path_text)
    parent = str(path.parent)
    return "" if parent in {"", "."} else parent


def _looks_windows_path(path_text: str) -> bool:
    return "\\" in path_text or (len(path_text) >= 2 and path_text[1] == ":")
