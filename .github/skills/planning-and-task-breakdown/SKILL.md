---
name: planning-and-task-breakdown
description: "Use when: a clear requirement or spec needs to be decomposed into small, ordered, reviewable Test Data Analyser tasks before implementation."
---

# Planning and Task Breakdown

Break app work into small tasks that preserve architecture boundaries and leave the
program runnable after each step.

## Planning Rules

- Plan in read-only mode first. Do not edit code while discovering the task structure.
- Start from the spec, failing behavior, or user workflow.
- Identify affected layers before choosing an implementation order.
- Prefer vertical slices that include state/service/viewmodel/UI only when all are required for one user-visible result.
- Keep each task small enough to test and review in one focused session.
- Put risky or uncertain work early so it fails fast.
- Do not mix refactors, behavior changes, formatting churn, and documentation updates unless they are inseparable.

## Task Template

Use this shape for each task:

```markdown
## Task N: Short title

Goal: One sentence.

Likely files:
- path/to/file.py

Acceptance:
- [ ] Specific observable result.

Verification:
- [ ] Focused test or manual check.

Dependencies: Task numbers or None.
Risk: Low/Medium/High and why.
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

## Verification

- Every task has acceptance criteria.
- Every task has a verification step.
- Dependencies are ordered.
- No task is an unbounded "implement the feature" bucket.
- The plan calls out which app-specific skills should be loaded during implementation.