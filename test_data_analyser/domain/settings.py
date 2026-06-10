"""Per-plot view and setting structures.

Framework-independent dataclasses describing the axis limits, analysis window,
low-pass filter, legend, raw-data view, and manual-label state that belong to a
single plot profile. Each provides ``from_dict``/``to_dict`` helpers so JSON
session compatibility is preserved.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .conversions import _mapping, _string


@dataclass
class AxisLimits:
    xmin: str = ""
    xmax: str = ""
    ymin: str = ""
    ymax: str = ""
    y2min: str = ""
    y2max: str = ""

    @classmethod
    def from_dict(cls, value: object) -> "AxisLimits":
        data = _mapping(value)
        return cls(
            xmin=_string(data.get("xmin")),
            xmax=_string(data.get("xmax")),
            ymin=_string(data.get("ymin")),
            ymax=_string(data.get("ymax")),
            y2min=_string(data.get("y2min")),
            y2max=_string(data.get("y2max")),
        )

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class AxisTickSettings:
    x_major_tick: str = ""
    y_major_tick: str = ""
    y2_major_tick: str = ""
    align_secondary_y_axis_grid: bool = False

    @classmethod
    def from_dict(cls, value: object) -> "AxisTickSettings":
        data = _mapping(value)
        return cls(
            x_major_tick=_string(data.get("x_major_tick")),
            y_major_tick=_string(data.get("y_major_tick")),
            y2_major_tick=_string(data.get("y2_major_tick")),
            align_secondary_y_axis_grid=bool(data.get("align_secondary_y_axis_grid", False)),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class AnalysisWindow:
    start_x: str = ""
    end_x: str = ""

    @classmethod
    def from_dict(cls, value: object) -> "AnalysisWindow":
        data = _mapping(value)
        return cls(
            start_x=_string(data.get("start_x")),
            end_x=_string(data.get("end_x")),
        )

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class FilterSettings:
    enabled: bool = False
    cutoff_hz: str = ""
    order: str = "4"

    @classmethod
    def from_dict(cls, value: object) -> "FilterSettings":
        data = _mapping(value)
        return cls(
            enabled=bool(data.get("enabled", False)),
            cutoff_hz=_string(data.get("cutoff_hz")),
            order=_string(data.get("order", "4"), "4"),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class LegendSettings:
    max_inline_entries: object = 10
    location: str = "best"
    display_mode: str = "panel"

    @classmethod
    def from_dict(cls, value: object) -> "LegendSettings":
        data = _mapping(value)
        return cls(
            max_inline_entries=data.get("max_inline_entries", 10),
            location=_string(data.get("location", "best"), "best"),
            display_mode=_string(data.get("display_mode", "panel"), "panel"),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class RawDataViewSettings:
    rows_to_display: str = "All"
    apply_analysis_window: bool = True
    hide_blank_rows: bool = True

    @classmethod
    def from_dict(cls, value: object) -> "RawDataViewSettings":
        data = _mapping(value)
        return cls(
            rows_to_display=_string(data.get("rows_to_display", "All"), "All"),
            apply_analysis_window=bool(data.get("apply_analysis_window", True)),
            hide_blank_rows=bool(data.get("hide_blank_rows", True)),
        )

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass
class ManualLabelFlags:
    title: bool = False
    x_label: bool = False
    y_label: bool = False
    secondary_y_label: bool = False

    @classmethod
    def from_dict(cls, value: object) -> "ManualLabelFlags":
        data = _mapping(value)
        return cls(
            title=bool(data.get("title", False)),
            x_label=bool(data.get("x_label", False)),
            y_label=bool(data.get("y_label", False)),
            secondary_y_label=bool(data.get("secondary_y_label", False)),
        )

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)
