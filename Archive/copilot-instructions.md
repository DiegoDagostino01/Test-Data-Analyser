# Test Data Analyser - Copilot Instructions

This is a PySide6 / Qt desktop engineering analysis application for loading,
plotting, and reviewing CSV/XLSX/XLS test data. The current architecture is
Qt-only and is documented in `ARCHITECTURE.md`.

## Project priorities

- Follow `ARCHITECTURE.md` as the source of truth.
- Preserve the strict dependency direction: `qt_app/` -> `viewmodels/` ->
  `services/` -> `domain/` -> `core/`.
- Only `qt_app/` may import PySide6, create widgets, open dialogs, or show
  message boxes.
- Keep `domain/`, `services/`, and `viewmodels/` framework-independent.
  ViewModels coordinate `AppState` and services, returning plain data or
  `OperationResult`.
- Keep Qt widgets and adapters thin: collect UI state, call viewmodels, render
  results, and wire explicit Qt signals.
- Preserve Eaton branding, theme colours, and plot colour sources from
  `test_data_analyser/core/config.py`.
- Preserve current behaviour for CSV/XLSX/XLS loading, tolerant numeric
  conversion, secondary Y-axis plotting, plot/session profile state, Engineering
  Notes, Requirements/Limits, Raw Data editing/export, Maths Channels, Runs /
  Comparison, Point Compare, settings, and figure export.
- Keep the app runnable using `python run_qt_app.py` and
  `python -m test_data_analyser`.
- Use `python -m unittest discover -s tests` for the test suite. Use the Qt
  offscreen platform for explicit Qt smoke tests.

## Skill workflow

- Load and follow the relevant skill from `.github/skills/` before making task
  changes. Skills are maintained only in `.github/skills/`.
- Use `python-refactor-safely` for layered Python refactors.
- Use `pyside6-qt-gui-maintainer` for Qt widgets, layout, signals, dialogs, and
  Matplotlib canvas work.
- Use `plotting-engine-separation` for plotting, legends, axis limits, figure
  export, or plot data preparation.
- Use `pandas-data-cleaning-analysis` for data loading, numeric coercion,
  statistics, raw data, filtering, and export.
- Use `session-profile-state-guardian` for sessions, plot profiles, labels,
  limits, notes, generated state, and per-plot configuration.
- Use `python-test-writer` when adding or changing tests.
- Use `performance-cleanup`, `code-review-bug-hunter`,
  `engineering-app-documentation`, and `git-change-discipline` when those task
  types apply.

## Response style

- Do not summarise the whole codebase.
- Report only the files changed, behaviour preserved or changed, tests/manual
  checks run, assumptions, and any follow-up risk.
