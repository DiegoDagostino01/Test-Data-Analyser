---
name: python-refactor-safely
description: "Use when: refactoring Test Data Analyser Python modules, moving responsibilities between qt_app, viewmodels, services, domain, or core, or reducing duplication."
---

# Python Refactor Safely

Use this skill when refactoring the PySide6 / Qt Test Data Analyser codebase.

## Refactor goals

- Follow `ARCHITECTURE.md` as the source of truth.
- Keep dependency direction strict: `qt_app/` -> `viewmodels/` -> `services/`
  -> `domain/` -> `core/`.
- Only `qt_app/` may import PySide6, create widgets, open dialogs, or show
  message boxes.
- Move reusable engineering/data logic down into `services/`, `domain/`, or
  `core/`; keep `viewmodels/` UI-independent and Qt widgets thin.
- Do not reintroduce deleted Tkinter modules or `run_app.py`.
- Preserve secondary Y-axis behaviour, sessions, plot/profile state,
  Engineering Notes, Requirements/Limits, Runs / Comparison, Raw Data editing,
  Maths Channels, Point Compare, settings, and Eaton branding.
- Prefer small, focused modules and reviewable changes.

## Refactor process

1. Inspect the relevant files and nearby tests first.
2. Identify the smallest coherent responsibility to move or simplify.
3. Keep public behaviour stable unless the prompt requests a change.
4. Update imports along the established layer boundaries.
5. Check for circular imports and Qt imports outside `qt_app/`.
6. Add or update focused tests when behaviour or shared logic changes.
7. Run `python -m unittest discover -s tests` when feasible.
8. Report only files changed, behaviour preserved or changed, tests/manual
   checks, assumptions, and remaining risk.
