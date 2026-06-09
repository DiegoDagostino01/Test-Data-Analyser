from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Optional
import pandas as pd

@dataclass
class PlotData:
    x: pd.Series
    y_map: dict[str, pd.Series]
    # Optional per-series X data. This allows wide Excel files where each test/run
    # has its own Flow Rate column to plot every Y channel against the matching
    # Flow Rate from the same test block, instead of forcing all Y channels to use
    # one global X column.
    x_map: Optional[dict[str, pd.Series]] = None


def _mapping(value: object) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _string(value: object, default: str = "") -> str:
    if value is None:
        return default
    return str(value)


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item) for item in value]


def _float(value: object, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


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

    @classmethod
    def from_dict(cls, value: object) -> "LegendSettings":
        data = _mapping(value)
        return cls(
            max_inline_entries=data.get("max_inline_entries", 10),
            location=_string(data.get("location", "best"), "best"),
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


@dataclass
class EngineeringNotes:
    schema: str = "structured_engineering_notes_v1"
    objective: str = ""
    test_article: str = ""
    conditions: str = ""
    observations: str = ""
    rationale: str = ""
    anomalies: str = ""
    comparison: str = ""
    actions: str = ""
    report_summary: str = ""

    @classmethod
    def from_dict(cls, value: object) -> "EngineeringNotes":
        if isinstance(value, str):
            return cls(observations=value)
        data = _mapping(value)
        return cls(
            schema=_string(data.get("schema", "structured_engineering_notes_v1"), "structured_engineering_notes_v1"),
            objective=_string(data.get("objective")),
            test_article=_string(data.get("test_article")),
            conditions=_string(data.get("conditions")),
            observations=_string(data.get("observations")),
            rationale=_string(data.get("rationale")),
            anomalies=_string(data.get("anomalies")),
            comparison=_string(data.get("comparison")),
            actions=_string(data.get("actions")),
            report_summary=_string(data.get("report_summary")),
        )

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class LimitPoint:
    x: float = 0.0
    y: float = 0.0

    @classmethod
    def from_dict(cls, value: object) -> "LimitPoint":
        data = _mapping(value)
        return cls(x=_float(data.get("x")), y=_float(data.get("y")))

    def to_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass
class LimitLine:
    name: str = "Limit 1"
    type: str = "Upper Limit"
    applies_to: str = "All selected Y channels"
    color: str = "#005A8C"
    points: list[LimitPoint] = field(default_factory=list)

    @classmethod
    def from_dict(cls, value: object) -> "LimitLine":
        data = _mapping(value)
        points = data.get("points", [])
        return cls(
            name=_string(data.get("name", "Limit 1"), "Limit 1"),
            type=_string(data.get("type", "Upper Limit"), "Upper Limit"),
            applies_to=_string(data.get("applies_to", "All selected Y channels"), "All selected Y channels"),
            color=_string(data.get("color", "#005A8C"), "#005A8C"),
            points=[LimitPoint.from_dict(point) for point in points] if isinstance(points, list) else [],
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "type": self.type,
            "applies_to": self.applies_to,
            "color": self.color,
            "points": [point.to_dict() for point in self.points],
        }


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
