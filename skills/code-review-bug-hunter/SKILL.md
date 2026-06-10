---
name: code-review-bug-hunter
description: Use this when reviewing changed Python code for bugs, broken imports, duplicate methods, GUI regressions, or refactor mistakes.
---

# Code Review Bug Hunter

Review the current changes as a strict Python code reviewer.

## Check for

- Broken imports.
- Circular imports.
- Duplicate method definitions.
- Methods moved but still referenced incorrectly.
- Missing `self` attributes.
- Broken Tkinter callbacks.
- Method resolution order issues.
- Changed behaviour not requested.
- Dead code left in `gui_base.py`.
- Session/profile state inconsistencies.
- Secondary Y-axis regressions.
- Raw data/export regressions.
- Plotting/legend/save regressions.

## Response format

Do not rewrite large sections unless requested.

Return:

1. High-risk issues.
2. Medium-risk issues.
3. Low-risk cleanup.
4. Specific fixes.
5. Manual checks to run in the GUI.
