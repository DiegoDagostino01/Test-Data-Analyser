---
name: plotting-engine-separation
description: "Use when: refactoring plotting, axis limits, legends, figure export, Matplotlib rendering, cursor plot data, or data preparation."
---

# Plotting Engine Separation

Use this skill when changing plotting or plot-preparation behaviour.

## Rules

- Keep Qt callbacks thin; they should gather panel state, call viewmodels, and
  render results.
- Keep data preparation in `services/plotting_data_service.py`,
  `services/plot_render_service.py`, or `viewmodels/plot_workspace_vm.py`. Only
  place logic elsewhere if it is tightly coupled to a specific widget with no
  reuse potential, and add a TODO comment explaining the deviation.
- Keep Qt/Matplotlib canvas embedding in `qt_app/widgets/plot_workspace.py` and
  `qt_app/adapters/matplotlib_qt_adapter.py`.
- Do not import PySide6 outside `qt_app/`.
- Preserve line, scatter, and line + marker plot kinds.
- Preserve primary and secondary Y-axis behaviour, including `twinx`.
- Preserve plotting behaviour by concern:
  - Axis: manual/auto axis limits, axis padding settings, and limit-line
    overlays.
  - Legend: merged legends, legend display mode, secondary colour cycling, and
    `[Right Y]` labels.
  - Data/filtering: analysis-window filtering and low-pass filtering.
  - Interaction: cursor point comparison.
  - Output: figure export behaviour.
- Preservation rules apply by default. If the user explicitly requests a change
  to a preserved behaviour, confirm the intent before modifying it and note
  which preserved behaviour is being altered.
- Use `OperationResult` for recoverable plotting failures.
- For unrecoverable plotting failures, such as missing required data or an
  unsupported plot kind, raise a typed exception defined in
  `services/exceptions.py` and let the Qt callback handle user-facing messaging.
- Do not change Eaton plot colours or styling unless requested.

## Checks

- Prefer service/viewmodel tests for pure preparation logic.
- For canvas changes, add or update focused Qt adapter/widget tests under the
  offscreen platform.
