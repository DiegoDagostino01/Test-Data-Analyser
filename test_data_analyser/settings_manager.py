from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Callable, Optional
import json
import logging

logger = logging.getLogger(__name__)


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
        "auto_save_enabled": False,
        "auto_save_interval_minutes": 10,
        "confirm_before_delete": True,
        "show_tooltips": True,
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
        "fft_window_function": "hanning",
        "available_fft_windows": ["hanning", "hamming", "blackman", "rectangular"],
        "fft_overlap_percent": 50,
        "significant_figures_maths": 6,
    },
}

SettingsCallback = Callable[[dict[str, dict[str, Any]]], None]


class SettingsManager:
    """Load, save, access, and reset application settings."""

    def __init__(self, settings_path: Optional[str | Path] = None) -> None:
        app_dir = Path(__file__).resolve().parent.parent
        self.settings_path = Path(settings_path) if settings_path is not None else app_dir / "settings.json"
        self._callbacks: list[SettingsCallback] = []
        self._settings = self._load_or_create_settings()

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
        self.settings_path.parent.mkdir(parents=True, exist_ok=True)
        self.settings_path.write_text(
            json.dumps(self._settings, indent=2),
            encoding="utf-8",
        )
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
            self.settings_path.parent.mkdir(parents=True, exist_ok=True)
            self.settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
            return settings

        try:
            loaded = json.loads(self.settings_path.read_text(encoding="utf-8"))
            if not isinstance(loaded, dict):
                raise ValueError("settings.json root must be an object")
        except Exception as exc:
            logger.warning("Could not load settings from %s; using defaults. %s", self.settings_path, exc)
            settings = deepcopy(DEFAULT_SETTINGS)
            self.settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
            return settings

        settings, changed = self._merge_with_defaults(loaded)
        if changed:
            self.settings_path.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        return settings

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