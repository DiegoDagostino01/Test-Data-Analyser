"""Plot-profile domain model.

A ``PlotProfile`` is the framework-independent representation of a single plot
tab: its selected channels, labels, axis limits, analysis window, filter,
legend, raw-data view, engineering notes, and limit lines. The Tkinter UI still
stores active profiles as dictionaries for compatibility, normalising through
``normalise_plot_profile`` at the creation/apply/save/load boundaries.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .conversions import _mapping, _string, _string_list
from .engineering_notes import EngineeringNotes
from .limits import LimitLine
from .settings import (
    AnalysisWindow,
    AxisLimits,
    FilterSettings,
    LegendSettings,
    ManualLabelFlags,
    RawDataViewSettings,
)


@dataclass
class PlotProfile:
    name: str = "Plot 1"
    x_column: str = ""
    y_columns: list[str] = field(default_factory=list)
    secondary_y_columns: list[str] = field(default_factory=list)
    title: str = "Engineering Test Data"
    x_label: str = ""
    y_label: str = "Selected Signals"
    secondary_y_label: str = ""
    plot_kind: str = "Line"
    grid: bool = True
    auto_fit_axes: bool = True
    axis_limits: AxisLimits = field(default_factory=AxisLimits)
    analysis_window: AnalysisWindow = field(default_factory=AnalysisWindow)
    filter: FilterSettings = field(default_factory=FilterSettings)
    legend: LegendSettings = field(default_factory=LegendSettings)
    raw_data: RawDataViewSettings = field(default_factory=RawDataViewSettings)
    engineering_notes: EngineeringNotes = field(default_factory=EngineeringNotes)
    limit_lines: list[LimitLine] = field(default_factory=list)
    manual_labels: ManualLabelFlags = field(default_factory=ManualLabelFlags)
    generated: bool = False

    @classmethod
    def from_dict(cls, value: object) -> "PlotProfile":
        data = _mapping(value)
        limit_lines = data.get("limit_lines", [])
        return cls(
            name=_string(data.get("name", "Plot 1"), "Plot 1"),
            x_column=_string(data.get("x_column")),
            y_columns=_string_list(data.get("y_columns")),
            secondary_y_columns=_string_list(data.get("secondary_y_columns")),
            title=_string(data.get("title", "Engineering Test Data"), "Engineering Test Data"),
            x_label=_string(data.get("x_label")),
            y_label=_string(data.get("y_label", "Selected Signals"), "Selected Signals"),
            secondary_y_label=_string(data.get("secondary_y_label")),
            plot_kind=_string(data.get("plot_kind", "Line"), "Line"),
            grid=bool(data.get("grid", True)),
            auto_fit_axes=bool(data.get("auto_fit_axes", True)),
            axis_limits=AxisLimits.from_dict(data.get("axis_limits")),
            analysis_window=AnalysisWindow.from_dict(data.get("analysis_window")),
            filter=FilterSettings.from_dict(data.get("filter")),
            legend=LegendSettings.from_dict(data.get("legend")),
            raw_data=RawDataViewSettings.from_dict(data.get("raw_data")),
            engineering_notes=EngineeringNotes.from_dict(data.get("engineering_notes")),
            limit_lines=[LimitLine.from_dict(line) for line in limit_lines] if isinstance(limit_lines, list) else [],
            manual_labels=ManualLabelFlags.from_dict(data.get("manual_labels")),
            generated=bool(data.get("generated", False)),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "x_column": self.x_column,
            "y_columns": list(self.y_columns),
            "secondary_y_columns": list(self.secondary_y_columns),
            "title": self.title,
            "x_label": self.x_label,
            "y_label": self.y_label,
            "secondary_y_label": self.secondary_y_label,
            "plot_kind": self.plot_kind,
            "grid": self.grid,
            "auto_fit_axes": self.auto_fit_axes,
            "axis_limits": self.axis_limits.to_dict(),
            "analysis_window": self.analysis_window.to_dict(),
            "filter": self.filter.to_dict(),
            "legend": self.legend.to_dict(),
            "raw_data": self.raw_data.to_dict(),
            "engineering_notes": self.engineering_notes.to_dict(),
            "limit_lines": [line.to_dict() for line in self.limit_lines],
            "manual_labels": self.manual_labels.to_dict(),
            "generated": self.generated,
        }


def plot_profile_from_dict(value: object) -> PlotProfile:
    return PlotProfile.from_dict(value)


def plot_profile_to_dict(profile: PlotProfile | dict[str, object]) -> dict[str, object]:
    if isinstance(profile, PlotProfile):
        return profile.to_dict()
    return PlotProfile.from_dict(profile).to_dict()


def normalise_plot_profile(value: object) -> dict[str, object]:
    return plot_profile_to_dict(plot_profile_from_dict(value))
