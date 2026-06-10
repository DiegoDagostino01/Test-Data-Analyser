"""Small Qt-layer widget helpers.

Shared UI-flow helpers used by more than one panel. Currently this holds the
"last used directory" persistence used by file/session dialogs so they reopen
where the user last worked.

These helpers are deliberately defensive: they accept a settings-manager-like
object (or ``None``) and never raise, so panels can call them without requiring a
real settings manager (for example in headless tests).
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

_DATA_SECTION = "data_import"
_DATA_KEY = "last_data_directory"
_SESSION_SECTION = "general_ui"
_SESSION_KEY = "last_session_directory"


def last_data_directory(settings_manager: Any) -> str:
    """Return the stored last-used data directory, or "" if unavailable.

    Falls back to "" when there is no settings manager, the value is unset, or
    the stored directory no longer exists on disk.
    """
    return _last_directory(settings_manager, _DATA_SECTION, _DATA_KEY)


def remember_data_directory(settings_manager: Any, filename: str) -> None:
    """Persist the parent directory of ``filename`` as the last-used data directory."""
    _remember_directory(settings_manager, filename, _DATA_SECTION, _DATA_KEY)


def last_session_directory(settings_manager: Any) -> str:
    """Return the stored last-used session directory, or "" if unavailable."""
    return _last_directory(settings_manager, _SESSION_SECTION, _SESSION_KEY)


def remember_session_directory(settings_manager: Any, filename: str) -> None:
    """Persist the parent directory of ``filename`` as the last-used session directory."""
    _remember_directory(settings_manager, filename, _SESSION_SECTION, _SESSION_KEY)


def save_session_initial_directory(settings_manager: Any, data_filename: Any = None) -> str:
    """Return the initial directory for Save Session.

    Prefer the currently loaded data file's folder so a new analysis starts next
    to its source CSV/Excel file. When no usable data-file folder is available,
    fall back to the last-used session directory.
    """
    data_directory = _directory_for_filename(data_filename)
    return data_directory or last_session_directory(settings_manager)


def _last_directory(settings_manager: Any, section: str, key: str) -> str:
    if settings_manager is None:
        return ""
    try:
        directory = settings_manager.get(section, key)
    except Exception:
        return ""
    if directory and Path(directory).is_dir():
        return str(directory)
    return ""


def _directory_for_filename(filename: Any) -> str:
    if not filename:
        return ""
    try:
        directory = Path(filename).resolve().parent
    except Exception:
        return ""
    return str(directory) if directory.is_dir() else ""


def _remember_directory(settings_manager: Any, filename: str, section: str, key: str) -> None:
    if settings_manager is None:
        return
    try:
        parent = str(Path(filename).resolve().parent)
        settings_manager.set(section, key, parent)
        settings_manager.save()
    except Exception:
        pass
