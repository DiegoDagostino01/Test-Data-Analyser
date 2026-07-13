from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Optional
import json
import logging
import os

logger = logging.getLogger(__name__)

SETTINGS_VENDOR = "Eaton"
SETTINGS_APPLICATION = "Test Data Analyser"
MAX_SETTINGS_BYTES = 4 * 1024 * 1024


DEFAULT_SETTINGS: dict[str, dict[str, Any]] = {
    "plot_appearance": {
        "default_line_width": 1.5,
        "colour_cycle": "eaton",
        "available_colour_cycles": ["eaton", "matplotlib", "colourblind_safe"],
        "default_marker_style": "None",
        "grid_visible": True,
        "font_size_title": 14,
        "font_size_axis_label": 12,
        "font_size_tick_label": 10,
        "font_size_legend": 10,
        "plot_background_colour": "#FFFFFF",
    },
    "axis_scaling": {
        "auto_scale_mode": "padded",
        "auto_scale_pad_percent": 5,
        "pad_x_axis": True,
        "pad_x_percent": 5,
        "pad_y_axis": True,
        "pad_y_percent": 5,
        "scientific_notation_enabled": True,
        "scientific_notation_threshold": 1e4,
        "decimal_places_statistics": 4,
        "decimal_places_cursor": 4,
    },
    "data_import": {
        "default_delimiter": "auto",
        "available_delimiters": ["auto", ",", "\t", ";", "|"],
        "default_encoding": "utf-8",
        "available_encodings": ["utf-8", "latin-1", "cp1252", "ascii"],
        "header_row_index": 0,
        "skip_rows": 0,
        "decimal_separator": ".",
        "last_data_directory": "",
    },
    "export": {
        "default_image_format": "png",
        "available_image_formats": ["png", "svg", "pdf"],
        "default_dpi": 150,
        "default_export_directory": "",
        "include_statistics_in_export": False,
        "auto_timestamp_filenames": True,
    },
    "general_ui": {
        "theme": "light",
        "legend_threshold": 1,
        "startup_behaviour": "blank",
        "available_startup_behaviours": ["blank", "last_session", "prompt"],
        "user_experience_mode": "basic",
        "available_user_experience_modes": ["basic", "advanced"],
        "auto_save_enabled": False,
        "auto_save_interval_minutes": 10,
        "confirm_before_delete": True,
        "show_tooltips": True,
        "last_session_directory": "",
    },
    "engineering_analysis": {
        "default_statistics_columns": [
            "Count",
            "Min",
            "Max",
            "Mean",
            "Median",
            "Std Dev",
            "RMS",
            "Peak-to-Peak",
        ],
        "significant_figures_maths": 6,
    },
    "recent": {
        "recent_files": [],
        "recent_sessions": [],
    },
    "recovery": {
        "dismissed_fingerprints": [],
    },
    "workspace": {
        "payload": {},
    },
}

SettingsCallback = Callable[[dict[str, dict[str, Any]]], None]


class SettingsManager:
    """Load, save, access, and reset application settings."""

    def __init__(self, settings_path: Optional[str | Path] = None) -> None:
        self.settings_path = Path(settings_path) if settings_path is not None else self.default_settings_path()
        self._callbacks: list[SettingsCallback] = []
        self.is_read_only = False
        self._settings = self._load_or_create_settings()

    @classmethod
    def default_settings_path(
        cls,
        repo_root: Path | None = None,
        local_app_data: Path | None = None,
    ) -> Path:
        """Return the per-user settings path, copying a valid legacy file once."""
        root = repo_root or Path(__file__).resolve().parent.parent.parent
        app_data = local_app_data
        if app_data is None:
            local_app_data_text = os.environ.get("LOCALAPPDATA", "").strip()
            if not local_app_data_text:
                raise RuntimeError("LOCALAPPDATA is required to store application settings.")
            app_data = Path(local_app_data_text)
        settings_path = app_data / SETTINGS_VENDOR / SETTINGS_APPLICATION / "settings.json"
        if settings_path.exists():
            return settings_path
        legacy_path = root / "settings.json"
        if legacy_path.exists():
            cls._copy_valid_legacy_settings(legacy_path, settings_path)
        return settings_path

    def get(self, section: str, key: str) -> Any:
        """Return a setting value, falling back to the default if needed."""
        if section not in DEFAULT_SETTINGS:
            raise KeyError(f"Unknown settings section: {section}")
        if key not in DEFAULT_SETTINGS[section]:
            raise KeyError(f"Unknown setting: {section}.{key}")
        return deepcopy(self._settings.get(section, {}).get(key, DEFAULT_SETTINGS[section][key]))

    def set(self, section: str, key: str, value: Any) -> None:
        """Set a user-editable setting value in memory."""
        if section not in DEFAULT_SETTINGS:
            raise KeyError(f"Unknown settings section: {section}")
        if key not in DEFAULT_SETTINGS[section]:
            raise KeyError(f"Unknown setting: {section}.{key}")
        if key.startswith("available_"):
            raise ValueError(f"Read-only setting cannot be changed: {section}.{key}")
        self._settings.setdefault(section, {})[key] = deepcopy(value)

    def reset_section(self, section: str) -> None:
        """Reset one settings section to defaults in memory."""
        if section not in DEFAULT_SETTINGS:
            raise KeyError(f"Unknown settings section: {section}")
        self._settings[section] = deepcopy(DEFAULT_SETTINGS[section])

    def reset_all(self) -> None:
        """Reset every setting to defaults in memory."""
        self._settings = deepcopy(DEFAULT_SETTINGS)

    def save(self) -> None:
        """Write settings to disk and notify registered observers."""
        if self.is_read_only:
            raise RuntimeError(
                "Settings are read-only because the existing settings file could not be loaded."
            )
        self._write_settings(self.settings_path, self._settings)
        self._notify_callbacks()

    def add_callback(self, callback: SettingsCallback) -> None:
        """Register a callback called after settings are saved."""
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def remove_callback(self, callback: SettingsCallback) -> None:
        """Remove a registered settings callback."""
        if callback in self._callbacks:
            self._callbacks.remove(callback)

    def as_dict(self) -> dict[str, dict[str, Any]]:
        """Return a deep copy of all current settings."""
        return deepcopy(self._settings)

    def defaults(self) -> dict[str, dict[str, Any]]:
        """Return a deep copy of the default settings."""
        return deepcopy(DEFAULT_SETTINGS)

    def _load_or_create_settings(self) -> dict[str, dict[str, Any]]:
        if not self.settings_path.exists():
            settings = deepcopy(DEFAULT_SETTINGS)
            self._write_settings(self.settings_path, settings)
            return settings

        try:
            if self.settings_path.stat().st_size > MAX_SETTINGS_BYTES:
                raise ValueError("settings.json exceeds the supported size limit")
            loaded = json.loads(self.settings_path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError("settings.json root must be an object")
        except Exception as exc:
            logger.warning("Could not load application settings; using in-memory defaults. %s", exc)
            self.is_read_only = True
            return deepcopy(DEFAULT_SETTINGS)

        settings, changed = self._merge_with_defaults(loaded)
        loaded_general_ui = loaded.get("general_ui", {})
        if not isinstance(loaded_general_ui, dict) or "user_experience_mode" not in loaded_general_ui:
            # Preserve the full toolset for existing or migrated users; only a
            # genuinely new settings store starts in Basic mode.
            settings["general_ui"]["user_experience_mode"] = "advanced"
            changed = True
        if changed:
            self._write_settings(self.settings_path, settings)
        return settings

    @classmethod
    def _copy_valid_legacy_settings(cls, source: Path, target: Path) -> bool:
        try:
            if source.stat().st_size > MAX_SETTINGS_BYTES:
                return False
            loaded = json.loads(source.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                return False
            if target.exists():
                return True
            cls._write_settings(target, loaded)
            return True
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError):
            return False

    @staticmethod
    def _write_settings(path: Path, settings: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.tmp")
        temporary.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        temporary.replace(path)

    def _merge_with_defaults(self, loaded: dict[str, Any]) -> tuple[dict[str, dict[str, Any]], bool]:
        changed = False
        merged: dict[str, dict[str, Any]] = {}
        for section, defaults in DEFAULT_SETTINGS.items():
            loaded_section = loaded.get(section, {})
            if not isinstance(loaded_section, dict):
                loaded_section = {}
                changed = True
            merged_section: dict[str, Any] = {}
            for key, default_value in defaults.items():
                if key.startswith("available_"):
                    merged_section[key] = deepcopy(default_value)
                    if loaded_section.get(key) != default_value:
                        changed = True
                    continue
                if key in loaded_section:
                    merged_section[key] = deepcopy(loaded_section[key])
                else:
                    merged_section[key] = deepcopy(default_value)
                    changed = True
            merged[section] = merged_section
        if set(loaded) - set(DEFAULT_SETTINGS):
            changed = True
        return merged, changed

    def _notify_callbacks(self) -> None:
        snapshot = self.as_dict()
        for callback in list(self._callbacks):
            try:
                callback(snapshot)
            except Exception:
                logger.exception("Settings callback failed")