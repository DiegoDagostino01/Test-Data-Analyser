---
name: python-refactor-safely
description: Use this when refactoring the Test Data Analyser Python Tkinter codebase, extracting modules, removing duplicate methods, or improving maintainability.
---

# Python Refactor Safely

You are refactoring a Python Tkinter application called **Test Data Analyser**.

## Refactor goals

- Follow `ARCHITECTURE.md` as the source of truth.
- Actively remove duplicated functionality after extraction.
- Treat extracted modules as the source of truth.
- Do not preserve backward compatibility unless explicitly requested.
- Keep secondary Y-axis behaviour working.
- Keep Eaton branding unchanged.
- Keep the app runnable using `python run_app.py`.
- Prefer small, focused modules over large mixed-responsibility files.
- Do not summarise the whole codebase after changes.

## Refactor process

When refactoring:

1. Inspect relevant files first.
2. Identify the smallest coherent responsibility to extract.
3. Move related methods into a focused mixin or pure helper module.
4. Update imports and class composition.
5. Remove duplicate methods from `gui_base.py`.
6. Check for circular imports.
7. Check that required `self` attributes still exist.
8. Report only files changed, methods moved, duplicates removed, assumptions, and manual GUI checks.
