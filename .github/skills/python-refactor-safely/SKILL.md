---
name: python-refactor-safely
description: "Use when: refactoring Test Data Analyser Python modules, moving responsibilities between qt_app, viewmodels, services, domain, or core, or reducing duplication."
---

# Python Refactor Safely

Use this skill when refactoring the PySide6 / Qt Test Data Analyser codebase.

## Refactor goals

- Follow `ARCHITECTURE.md` as the source of truth.
- If `ARCHITECTURE.md` cannot be found or contradicts the existing module
  structure, stop and ask the user to clarify before making any changes.
- Keep dependency direction strict: `qt_app/` -> `viewmodels/` -> `services/`
  -> `domain/` -> `core/`.
- If the user's request would require an import that violates the layer
  dependency direction, refuse to make that change and explain which boundary
  would be crossed. Propose a compliant alternative instead.
- Only `qt_app/` may import PySide6, create widgets, open dialogs, or show
  message boxes.
- Move reusable engineering/data logic down into `services/`, `domain/`, or
  `core/`; keep `viewmodels/` UI-independent and Qt widgets thin.
- Do not reintroduce deleted Tkinter modules or `run_app.py`.
- Preservation checklist: confirm none of the following regress after changes,
  and for each affected area cite the test or manual check that confirms it:
  - UI features: secondary Y-axis behaviour, plot/profile state, Eaton branding.
  - Data features: Raw Data editing, Maths Channels, Point Compare.
  - Session/config features: sessions, settings, Engineering Notes,
    Requirements/Limits, Runs / Comparison.
- Prefer small, focused modules and reviewable changes.

## Refactor process

1. Inspect the relevant files and nearby tests first.
2. Identify the smallest coherent responsibility to move or simplify.
3. Keep public behaviour stable unless the user's current refactor request
  explicitly asks to change it.
4. Update imports along the established layer boundaries.
5. Check for circular imports and Qt imports outside `qt_app/`.
6. If a circular import is found, do not proceed with that change. Instead,
  describe the cycle and propose an alternative decomposition for user
  approval.
7. Add or update focused tests when behaviour or shared logic changes.
8. Run `python -m unittest discover -s tests` unless the changed files have no
  corresponding test files and no new logic was introduced.
9. Report only files changed, behaviour preserved or changed, tests/manual
   checks, assumptions, and remaining risk.
