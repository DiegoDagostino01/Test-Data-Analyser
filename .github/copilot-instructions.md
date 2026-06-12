# Test Data Analyser - Copilot Instructions

This is a PySide6 / Qt desktop engineering analysis application for loading,
plotting, and reviewing CSV/XLSX/XLS test data. The current architecture is
Qt-only and is documented in `ARCHITECTURE.md`.

## Project priorities

- When these constraints conflict, resolve them in this order: (1) dependency
  direction, (2) framework independence of domain/services/viewmodels, (3)
  thin widgets, (4) branding/theme, (5) behavioural preservation, (6)
  runnability, (7) test suite compatibility.
- Follow `ARCHITECTURE.md` as the source of truth. If `ARCHITECTURE.md` is not
  accessible or does not address the scenario, state this explicitly and apply
  the dependency direction and layer separation rules defined in these
  instructions as the fallback source of truth. Do not invent architectural
  decisions.
- Preserve the strict dependency direction: `qt_app/` -> `viewmodels/` ->
  `services/` -> `domain/` -> `core/`.
- If a requested change cannot be implemented without violating the dependency
  direction, do not implement the violation. Instead, explain why it is not
  possible within the current architecture and propose a compliant alternative
  design before writing any code.
- Only `qt_app/` may import PySide6, create widgets, open dialogs, or show
  message boxes.
- Keep `domain/`, `services/`, and `viewmodels/` framework-independent.
  ViewModels coordinate `AppState` and services, returning plain data or
  `OperationResult`.
- Keep Qt widgets and adapters thin: collect UI state, call viewmodels, render
  results, and wire explicit Qt signals.
- Preserve Eaton branding, theme colours, and plot colour sources from
  `test_data_analyser/core/config.py`.
- Do not introduce unintentional regressions in the following features:
  CSV/XLSX/XLS loading, tolerant numeric conversion, secondary Y-axis plotting,
  plot/session profile state, Engineering Notes, Requirements/Limits, Raw Data
  editing/export, Maths Channels, Runs / Comparison, Point Compare, settings,
  and figure export. Intentional changes to these features are permitted when
  explicitly requested by the user.
- Keep the app runnable using `python run_qt_app.py` and
  `python -m test_data_analyser`.
- Use `python -m unittest discover -s tests` for the test suite. Use the Qt
  offscreen platform for explicit Qt smoke tests.

## Skill workflow

- Before making changes, identify all applicable skills from `.github/skills/`.
  Apply them in this order of precedence when they conflict:
  `python-refactor-safely` > `pyside6-qt-gui-maintainer` >
  `plotting-engine-separation` > `pandas-data-cleaning-analysis` >
  `session-profile-state-guardian` > `python-test-writer`. Apply all other
  skills (`performance-cleanup`, `code-review-bug-hunter`,
  `engineering-app-documentation`, `git-change-discipline`) in addition when
  the task type applies.
- If the relevant skill file is not found in `.github/skills/`, state this
  explicitly, list the skill name that was expected, and proceed using only the
  constraints defined in these instructions. Do not fabricate skill file
  content.
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
- If no automated tests cover the changed area and adding them is out of scope,
  explicitly state "No automated test coverage for this change" under
  tests/manual checks and list the manual verification steps performed instead.
