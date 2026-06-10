---
name: code-review-bug-hunter
description: "Use when: reviewing changed Python or PySide6 code for bugs, broken imports, layer violations, GUI regressions, state leaks, or refactor mistakes."
---

# Code Review Bug Hunter

Review changes as a strict Python/Qt code reviewer.

## Check for

- Broken imports and circular imports.
- PySide6 imports outside `qt_app/`.
- Services or viewmodels opening dialogs, showing message boxes, or holding Qt
  objects.
- Broken Qt signal wiring, stale widget attribute names, or modal dialogs in
  tests.
- Methods moved but still referenced incorrectly.
- Missing `self` attributes or state initialisation.
- Changed behaviour not requested by the prompt.
- Stale Tkinter or `run_app.py` references in active code or guidance.
- Session/profile state inconsistencies and generated-plot restore regressions.
- Secondary Y-axis, legend, axis limit, limit-line, cursor compare, save
  figure, raw data/export, maths channel, and runs comparison regressions.
- Missing tests for changed shared logic.

## Response format

Do not rewrite large sections unless requested. Return findings first:

1. High-risk issues.
2. Medium-risk issues.
3. Low-risk cleanup.
4. Specific fixes.
5. Tests and manual checks to run.
