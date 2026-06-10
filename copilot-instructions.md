# Test Data Analyser — Copilot Instructions

This is a Python Tkinter engineering analysis application for test data plotting and review.

## Project priorities

- Follow `ARCHITECTURE.md`.
- Prefer focused modules over monolithic GUI code.
- Extract functionality from `gui_base.py` into mixins or pure helper modules.
- Remove duplicated functionality after extraction.
- Treat extracted modules as the source of truth.
- Do not worry about backward compatibility with old session files unless explicitly requested.
- Preserve secondary Y-axis behaviour.
- Preserve plot profile independence.
- Preserve Engineering Notes behaviour.
- Keep Eaton branding and styling unchanged.
- Keep the app runnable using `python run_app.py`.
- Prefer pure plotting/data-preparation logic separated from Tkinter where practical.
- Improve efficiency where safe and obvious.

## Response style

- Do not summarise the whole codebase.
- Report only:
  1. Files changed.
  2. Methods moved.
  3. Duplicates removed.
  4. Assumptions.
  5. Manual checks.
