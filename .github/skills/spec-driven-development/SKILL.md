---
name: spec-driven-development
description: "Use when: starting a significant Test Data Analyser feature, changing cross-layer behavior, altering saved/session/profile state, or when requirements are ambiguous enough that coding would be guessing."
---

# Spec-Driven Development

Write a small, explicit spec before non-trivial app work. The spec should clarify
the user workflow, the engineering boundaries, and how success will be verified.

## When To Use

- New user-facing workflow or tab behavior.
- Changes that touch more than one architecture layer.
- Changes to saved sessions, plot profiles, labels, requirements/limits, runs, maths channels, or generated plot state.
- Requirements with unclear scope, acceptance criteria, or preservation expectations.
- Work that could plausibly affect CSV/XLSX/XLS loading, plotting, raw data editing/export, notes, or settings.

## Spec Contents

Keep the spec concise. Include:

- Objective: what user problem is being solved.
- Current behavior: what must be preserved.
- Proposed behavior: what changes in the app.
- Architecture boundaries: which layers may change and which may not.
- State impact: whether sessions, profiles, settings, or exported files change.
- UI impact: affected tabs, widgets, dialogs, tables, and plots.
- Data impact: CSV/Excel/dataframe assumptions, numeric conversion, filtering, or export behavior.
- Verification: focused tests, full suite command, and any manual Qt workflow.
- Open questions: anything that needs user decision before implementation.

## Project Defaults

- Respect `ARCHITECTURE.md` as the source of truth.
- Preserve dependency direction: `qt_app/` -> `viewmodels/` -> `services/` -> `domain/` -> `core/`.
- Keep PySide6 out of `domain/`, `services/`, and `viewmodels/`.
- Keep widgets thin: gather UI state, call viewmodels, render results, wire explicit signals.
- Prefer focused tests in `tests/` using `unittest`.
- Use `python -m unittest discover -s tests` for the full suite.

## Handoff

After the spec is accepted, use `planning-and-task-breakdown` for multi-step work.
For implementation, load the relevant app-specific skill before editing.

## Verification

- Success criteria are specific and testable.
- Preservation expectations are explicit.
- Layer ownership is clear.
- Session/profile/settings compatibility is considered when relevant.
- The user has approved or corrected the spec before implementation begins.