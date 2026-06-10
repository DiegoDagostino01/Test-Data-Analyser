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
  `services/plot_render_service.py`, or `viewmodels/plot_workspace_vm.py` when
  practical.
- Keep Qt/Matplotlib canvas embedding in `qt_app/widgets/plot_workspace.py` and
  `qt_app/adapters/matplotlib_qt_adapter.py`.
- Do not import PySide6 outside `qt_app/`.
- Preserve line, scatter, and line + marker plot kinds.
- Preserve primary and secondary Y-axis behaviour, including `twinx`, merged
  legends, secondary colour cycling, and `[Right Y]` labels.
- Preserve analysis-window filtering, low-pass filtering, cursor point
  comparison, manual/auto axis limits, axis padding settings, limit-line
  overlays, legend display mode, and figure export behaviour.
- Use `OperationResult` for recoverable plotting failures.
- Do not change Eaton plot colours or styling unless requested.

## Checks

- Prefer service/viewmodel tests for pure preparation logic.
- For canvas changes, add or update focused Qt adapter/widget tests under the
  offscreen platform.
