---
name: planning-and-task-breakdown
description: "Use when: a clear requirement or spec needs to be decomposed into small, ordered, reviewable Test Data Analyser tasks before implementation."
---

# Planning and Task Breakdown

Break app work into small tasks that preserve architecture boundaries and leave the
program runnable after each step.

## Planning Rules

- Plan in read-only mode first. Do not edit code while discovering the task structure. (required)
- Start from the spec, failing behavior, or user workflow. (required)
- If the spec is ambiguous or missing information needed to identify affected layers, list the open questions explicitly before producing any tasks. Do not invent answers to unresolved spec questions. (required)
- Identify affected layers before choosing an implementation order. (required)
- Use vertical slices (state + service + viewmodel + UI in one task) only when the user-visible result is impossible to verify without all layers present. Otherwise, follow the Layer Ordering Guide and build bottom-up, one layer per task. (required)
- Keep each task small enough to test and review in one focused session. Aim for tasks that take 30-90 minutes of focused work. If a plan exceeds 10 tasks, split it into phases and plan one phase at a time. (required)
- Put risky or uncertain work early so it fails fast. (required)
- Do not mix refactors, behavior changes, formatting churn, and documentation updates unless they are inseparable. (required)

## Task Template

Use this shape for each task: (required)

```markdown
## Task N: Short title

Goal: One sentence. (required)

Likely files: (required)
- path/to/file.py

Acceptance: (required)
- [ ] Specific observable result.

Verification: (required)
- [ ] Focused test or manual check.

Dependencies: Task numbers or None. (required)
Risk: Low/Medium/High and why. (required)
```

## Layer Ordering Guide

- Data parsing or dataframe behavior: start in `core/` or `services/`, then viewmodel, then UI.
- Business/session/profile state: start in `domain/` or `services/`, then viewmodel, then UI.
- UI-only layout or signal wiring: stay in `qt_app/` unless behavior requires a viewmodel change.
- Plot preparation: prefer service/domain preparation before Qt canvas rendering changes.
- Tests: add focused service/domain/viewmodel tests before broader Qt smoke checks when possible.

## Checkpoints

Add checkpoints after every two or three tasks for larger work:

- Focused tests pass.
- Full suite passes when shared behavior changed.
- Manual Qt workflow is checked if UI behavior changed.
- Plan is adjusted if implementation reveals incorrect assumptions.
