"""Built-in V1.03.00 workspace visibility profiles."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class WorkspacePreset(str, Enum):
    ANALYSIS = "analysis"
    COMPARISON = "comparison"
    REPORTING = "reporting"
    DATA_EDITING = "data_editing"
    CUSTOM = "custom"


@dataclass(frozen=True)
class WorkspacePresetDefinition:
    preset: WorkspacePreset
    visible_panels: frozenset[str]
    focused_panel: str


PLOT_PANEL_ID = "plot.workspace"

BUILT_IN_PRESETS: dict[WorkspacePreset, WorkspacePresetDefinition] = {
    WorkspacePreset.ANALYSIS: WorkspacePresetDefinition(
        WorkspacePreset.ANALYSIS,
        frozenset(
            {
                PLOT_PANEL_ID,
                "plot.controls",
                "plot.legend",
                "analysis.statistics",
                "requirements.limits",
            }
        ),
        PLOT_PANEL_ID,
    ),
    WorkspacePreset.COMPARISON: WorkspacePresetDefinition(
        WorkspacePreset.COMPARISON,
        frozenset(
            {
                PLOT_PANEL_ID,
                "plot.controls",
                "plot.legend",
                "runs.comparison",
                "analysis.statistics",
            }
        ),
        "runs.comparison",
    ),
    WorkspacePreset.REPORTING: WorkspacePresetDefinition(
        WorkspacePreset.REPORTING,
        frozenset(
            {
                PLOT_PANEL_ID,
                "plot.legend",
                "notes.engineering",
                "analysis.best_fit_formulas",
            }
        ),
        "notes.engineering",
    ),
    WorkspacePreset.DATA_EDITING: WorkspacePresetDefinition(
        WorkspacePreset.DATA_EDITING,
        frozenset(
            {
                PLOT_PANEL_ID,
                "plot.controls",
                "data.raw",
                "analysis.statistics",
            }
        ),
        "data.raw",
    ),
}


def parse_workspace_preset(value: object) -> WorkspacePreset:
    if isinstance(value, WorkspacePreset):
        return value
    try:
        return WorkspacePreset(str(value))
    except ValueError:
        return WorkspacePreset.ANALYSIS
