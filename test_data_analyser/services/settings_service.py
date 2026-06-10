"""Settings access helpers extracted into a framework-independent service.

The :class:`~test_data_analyser.settings_manager.SettingsManager` is already
UI-free; this module adds small, defensive helpers for safe getter, theme
resolution, and palette lookup. It must not import Tkinter or PySide6.
"""
from __future__ import annotations

from typing import Any, Protocol

from ..core.config import theme_palette


class SettingsReader(Protocol):
    """Minimal protocol satisfied by ``SettingsManager`` (and test doubles)."""

    def get(self, section: str, key: str) -> Any:  # pragma: no cover - structural
        ...


def safe_get(manager: SettingsReader | None, section: str, key: str, default: Any = None) -> Any:
    """Return ``manager.get(section, key)`` or ``default`` on any failure."""
    if manager is None:
        return default
    try:
        return manager.get(section, key)
    except Exception:
        return default


def theme_name(manager: SettingsReader | None) -> str:
    """Return the configured theme name ("light" or "dark")."""
    return str(safe_get(manager, "general_ui", "theme", "light"))


def is_dark_theme(manager: SettingsReader | None) -> bool:
    """Return True when the dark theme is selected."""
    return theme_name(manager).lower() == "dark"


def palette_for(manager: SettingsReader | None) -> dict[str, str]:
    """Return the colour palette for the configured theme."""
    return theme_palette(theme_name(manager))
