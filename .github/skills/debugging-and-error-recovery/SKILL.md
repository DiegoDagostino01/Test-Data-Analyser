---
name: debugging-and-error-recovery
description: "Use when: a test fails, the PySide6 app crashes, data loading behaves unexpectedly, plots render incorrectly, or a regression needs root-cause debugging before changing more code."
---

# Debugging and Error Recovery

Use a stop-the-line debugging workflow for failures in the Test Data Analyser app.
Do not keep adding features on top of a broken test, broken UI path, or unexplained
runtime error.

## Rules

- Preserve the evidence first: exact error text, traceback, failing command, input file type, selected tab/workflow, and recent change.
- Reproduce before fixing. If the failure cannot be reproduced, narrow the conditions and say what is still unknown. If the failure still cannot be reproduced after narrowing, do not propose a code change. Instead, list the specific information needed from the user (for example, exact input file, OS, Qt platform, Python version, or session state) and stop until that information is provided.
- Localize by architecture layer: `qt_app/`, `viewmodels/`, `services/`, `domain/`, or `core/`.
- Fix the root cause, not the visible symptom in the widget or plot.
- Always add or update a focused regression test after fixing a bug or changing observable behavior, unless no testable interface exists (for example, a purely visual PySide6 rendering issue with no offscreen equivalent).
- When multiple domain skills apply, handle the lowest data/domain layer first in this order: `pandas-data-cleaning-analysis`, `plotting-engine-separation`, `pyside6-qt-gui-maintainer`, then `python-test-writer`. State which skills are engaged and why before proceeding.
- If the issue involves tests, use `python-test-writer` for the regression guard.
- If the issue involves PySide6 widgets, signals, dialogs, tables, or canvas behavior, use `pyside6-qt-gui-maintainer` as the domain skill.
- If the issue involves plotting, use `plotting-engine-separation` as the domain skill.
- If the issue involves CSV/Excel/dataframe behavior, use `pandas-data-cleaning-analysis` as the domain skill.

## Workflow

1. Reproduce the failure with the smallest useful command or workflow.
2. Capture the relevant output and affected file paths.
3. Identify the failing layer and check the dependency direction from `ARCHITECTURE.md`. If `ARCHITECTURE.md` does not exist or does not document the relevant layer, state this explicitly and infer dependency direction from the folder structure (`qt_app/` -> `viewmodels/` -> `services/` -> `domain/` -> `core/`) before proceeding.
4. Reduce the case to the smallest data shape, plot configuration, session state, or UI action that still fails.
5. Change only the code needed to address the root cause.
6. Add or update the regression guard at the lowest practical level.
7. Re-run the focused test first, then the wider suite if the change affects shared behavior.

## Common Checks

- Import errors: verify the target module exists and dependency direction is allowed.
- Qt errors: confirm PySide6 imports stay inside `qt_app/`.
- State bugs: verify `AppState`, viewmodel outputs, and session/profile serialization are consistent.
- Plot bugs: verify prepared plot data before changing canvas rendering.
- Data bugs: verify dataframe shape, column names, numeric coercion, empty values, and filtered rows before changing UI display.
- Test pollution: run the failing test in isolation and then in the full suite.

## Verification

- The root cause is named in the final response.
- A focused repro or failing test exists for the original issue when feasible.
- The fix passes the focused verification.
- Run `python -m unittest discover -s tests` when the changed code is imported by more than one module, touches `AppState`, viewmodel interfaces, or service contracts, or modifies any shared utility in `core/`.
- Any manual Qt check uses the offscreen platform when appropriate.