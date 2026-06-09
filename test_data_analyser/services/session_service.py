"""Analysis-session persistence extracted into a framework-independent service.

Builds/normalises session dictionaries through the domain
:class:`~test_data_analyser.domain.SessionState` model and reads/writes them to
disk. It does not open file dialogs or show message boxes; callers pass an
explicit path and translate the returned/raised result into UI feedback.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any
import json

from ..domain import SessionState


def normalise_session(raw: Any) -> SessionState:
    """Return a :class:`SessionState` for a raw session dict (missing keys OK)."""
    return SessionState.from_dict(raw)


def build_session_dict(
    *,
    version: str,
    file_path: str,
    sheet_name: str,
    runs: list[dict[str, Any]],
    comparison: dict[str, Any],
    active_plot_profile_index: int,
    plot_profiles: list[dict[str, Any]],
    calculated_channels: dict[str, Any],
) -> dict[str, Any]:
    """Assemble and normalise a session dictionary from its parts.

    The assembled dict is round-tripped through :class:`SessionState` so the
    persisted structure has consistent keys/types regardless of how each section
    was produced.
    """
    raw: dict[str, Any] = {
        "version": version,
        "file_path": file_path,
        "sheet_name": sheet_name,
        "runs": runs,
        "active_plot_profile_index": active_plot_profile_index,
        "plot_profiles": plot_profiles,
        "calculated_channels": calculated_channels,
    }
    raw.update(comparison)
    return SessionState.from_dict(raw).to_dict()


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
