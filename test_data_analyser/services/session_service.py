"""Analysis-session persistence extracted into a framework-independent service.

Builds/normalises session dictionaries through the domain
:class:`~test_data_analyser.domain.SessionState` model and reads/writes them to
disk. It does not open file dialogs or show message boxes; callers pass an
explicit path and translate the returned/raised result into UI feedback.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
import json

from ..domain import SOURCE_EXCEL, SOURCE_MANUAL, ChannelRegistry, SessionState, normalise_plot_profile
from . import dataset_service, maths_channel_service


@dataclass(frozen=True)
class SessionWriteValidation:
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors


def normalise_session(raw: Any) -> SessionState:
    """Return a :class:`SessionState` for a raw session dict (missing keys OK)."""
    return SessionState.from_dict(raw)


def validate_session_for_write(session: SessionState) -> SessionWriteValidation:
    """Validate a normalised session that is about to be written by the app.

    Legacy reads remain tolerant through :func:`normalise_session`; this check is
    for newly assembled session payloads so bugs fail before writing JSON.
    """
    errors: list[str] = []
    warnings: list[str] = []
    if not session.version.strip():
        errors.append("Session version is required.")
    if not session.plot_profiles:
        errors.append("At least one plot profile is required.")
    elif not 0 <= session.active_plot_profile_index < len(session.plot_profiles):
        errors.append("Active plot profile index is out of range.")
    if session.data_source_type not in {SOURCE_EXCEL, SOURCE_MANUAL}:
        errors.append(f"Unsupported data source type: {session.data_source_type!r}.")
    if session.data_source_type == SOURCE_EXCEL and not session.file_path.strip():
        warnings.append("Excel session has no source file path.")
    if session.data_source_type == SOURCE_MANUAL and not session.channel_registry.columns:
        warnings.append("Manual session has no channel registry columns.")
    return SessionWriteValidation(errors=errors, warnings=warnings)


def _raise_if_invalid_for_write(session: SessionState) -> None:
    validation = validate_session_for_write(session)
    if validation.errors:
        raise ValueError("Invalid session payload: " + "; ".join(validation.errors))


def build_runtime_session_dict(
    *,
    version: str,
    root_file_directory: str,
    file_path: str,
    sheet_name: str,
    runs: list[dict[str, Any]],
    comparison: dict[str, Any],
    active_plot_profile_index: int,
    plot_profiles: list[dict[str, Any]],
    calculated_channels: dict[str, Any],
    data_source_type: str,
    channel_registry: ChannelRegistry,
    df: Any,
) -> dict[str, Any]:
    """Build a write-validated session dict from runtime state sections."""
    manual = data_source_type == SOURCE_MANUAL
    dataset_rows = dataset_service.rows_from_dataframe(channel_registry, df) if manual else []
    return build_session_dict(
        version=version,
        root_file_directory=root_file_directory,
        file_path=file_path,
        sheet_name=sheet_name,
        runs=runs,
        comparison=comparison,
        active_plot_profile_index=active_plot_profile_index,
        plot_profiles=[normalise_plot_profile(profile) for profile in plot_profiles],
        calculated_channels=maths_channel_service.normalise_calculated_channel_definitions(calculated_channels),
        data_source_type=data_source_type,
        channel_registry=channel_registry.to_dict(),
        dataset_rows=dataset_rows,
    )


def build_session_dict(
    *,
    version: str,
    root_file_directory: str,
    file_path: str,
    sheet_name: str,
    runs: list[dict[str, Any]],
    comparison: dict[str, Any],
    active_plot_profile_index: int,
    plot_profiles: list[dict[str, Any]],
    calculated_channels: dict[str, Any],
    data_source_type: str = "excel",
    channel_registry: dict[str, Any] | None = None,
    dataset_rows: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Assemble and normalise a session dictionary from its parts.

    The assembled dict is round-tripped through :class:`SessionState` so the
    persisted structure has consistent keys/types regardless of how each section
    was produced.
    """
    raw: dict[str, Any] = {
        "version": version,
        "root_file_directory": root_file_directory,
        "file_path": file_path,
        "sheet_name": sheet_name,
        "data_source_type": data_source_type,
        "channel_registry": channel_registry or {},
        "dataset_rows": dataset_rows or [],
        "runs": runs,
        "active_plot_profile_index": active_plot_profile_index,
        "plot_profiles": plot_profiles,
        "calculated_channels": calculated_channels,
    }
    raw.update(comparison)
    session = SessionState.from_dict(raw)
    _raise_if_invalid_for_write(session)
    return session.to_dict()


def save_session_dict(path: str | Path, session: dict[str, Any]) -> Path:
    """Write a session dict to ``path`` as JSON, returning the final path.

    Adds a ``.json`` suffix when the path has none. Raises ``RuntimeError`` if
    the file was not created.
    """
    target = Path(path)
    if target.suffix == "":
        target = target.with_suffix(".json")
    target.write_text(json.dumps(session, indent=2), encoding="utf-8")
    if not target.exists():
        raise RuntimeError("Session file was not created.")
    return target


def load_session_dict(path: str | Path) -> dict[str, Any]:
    """Read and JSON-decode a session file, returning the raw dict."""
    return json.loads(Path(path).read_text(encoding="utf-8"))
