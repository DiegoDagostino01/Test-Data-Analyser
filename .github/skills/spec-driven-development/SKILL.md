---
name: spec-driven-development
description: "Use when any condition in the When To Use section applies."
---

# Spec-Driven Development

Write a spec of one to two pages (300-600 words) before any work that meets the criteria in the When To Use section. The spec should clarify
the user workflow, the engineering boundaries, and how success will be verified.

## When To Use

- New user-facing workflow or tab behavior.
- Changes that touch more than one architecture layer.
- Changes to saved sessions, plot profiles, labels, requirements/limits, runs, maths channels, or generated plot state.
- Requirements with unclear scope, acceptance criteria, or preservation expectations.
- Work that could plausibly affect CSV/XLSX/XLS loading, plotting, raw data editing/export, notes, or settings.

## Override Policy

If the user asks to skip the spec, explain that implementation without a spec risks misaligned scope. Offer to write a minimal spec (objective + proposed behavior + verification only) that can be reviewed in under two minutes before proceeding.

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
If open questions exist, present them to the user and do not proceed to implementation or planning until each is resolved or explicitly deferred by the user.

## Project Defaults

- Respect `ARCHITECTURE.md` as the source of truth.
- Preserve dependency direction: `qt_app/` -> `viewmodels/` -> `services/` -> `domain/` -> `core/`.
- Keep PySide6 out of `domain/`, `services/`, and `viewmodels/`.
- Keep widgets thin: gather UI state, call viewmodels, render results, wire explicit signals.
- Prefer focused tests in `tests/` using `unittest`.
- Use `python -m unittest discover -s tests` for the full suite.

## Handoff

After the user explicitly approves the spec in the conversation (e.g., replies "approved" or "looks good"), switch to the `planning-and-task-breakdown` prompt for multi-step work.
Before editing implementation files, load the relevant skill from `.github/skills/` (for example, `pyside6-qt-gui-maintainer`, `pandas-data-cleaning-analysis`, `plotting-engine-separation`, `session-profile-state-guardian`, or `python-refactor-safely`).

## Verification

- Success criteria are specific and testable.
- Preservation expectations are explicit.
- Layer ownership is clear.
- Session/profile/settings compatibility is considered when relevant.
- The user has approved or corrected the spec before implementation begins.