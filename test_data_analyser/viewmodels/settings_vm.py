"""Settings viewmodel.

UI-independent coordination over a ``SettingsManager``. Exposes safe getters,
returns :class:`OperationResult` for mutating operations, and surfaces theme
information without importing any UI framework.
"""
from __future__ import annotations

from typing import Any

from ..services import plot_render_service, settings_service
from ..services.results import OperationResult


class SettingsViewModel:
    def __init__(self, settings_manager: Any = None) -> None:
        self.settings_manager = settings_manager

    def get(self, section: str, key: str, default: Any = None) -> Any:
        return settings_service.safe_get(self.settings_manager, section, key, default)

    def set(self, section: str, key: str, value: Any) -> OperationResult:
        if self.settings_manager is None:
            return OperationResult.failure("No settings manager is available.")
        try:
            self.settings_manager.set(section, key, value)
        except Exception as exc:
            return OperationResult.failure(str(exc))
        return OperationResult.success(f"{section}.{key} updated.")

    def save(self) -> OperationResult:
        if self.settings_manager is None:
            return OperationResult.failure("No settings manager is available.")
        try:
            self.settings_manager.save()
        except Exception as exc:
            return OperationResult.failure(f"Could not save settings: {exc}")
        return OperationResult.success("Settings saved.")

    def theme_name(self) -> str:
        return settings_service.theme_name(self.settings_manager)

    def is_dark_theme(self) -> bool:
        return settings_service.is_dark_theme(self.settings_manager)

    def palette(self) -> dict[str, str]:
        return settings_service.palette_for(self.settings_manager)

    def plot_colours(self) -> list[str]:
        cycle_name = str(self.get("plot_appearance", "colour_cycle", "eaton"))
        return plot_render_service.resolve_plot_colours(cycle_name)

    def secondary_plot_colours(self, colours: list[str] | None = None) -> list[str]:
        return plot_render_service.secondary_colour_cycle(colours or self.plot_colours())

    def options_for(self, section: str, key: str) -> list | None:
        """Return the ``available_*`` option list for a setting, if one exists.

        The settings schema names option lists by pluralising the key (e.g.
        ``colour_cycle`` -> ``available_colour_cycles``). Returns ``None`` when no
        matching option list is defined.
        """
        if self.settings_manager is None:
            return None
        for candidate in (f"available_{key}s", f"available_{key}es", f"available_{key}"):
            options = settings_service.safe_get(self.settings_manager, section, candidate, None)
            if isinstance(options, list):
                return list(options)
        return None

