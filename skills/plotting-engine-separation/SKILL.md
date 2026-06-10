---
name: plotting-engine-separation
description: Use this when refactoring plotting, FFT, axis limits, legends, figure saving, or data preparation out of Tkinter GUI methods.
---

# Plotting Engine Separation

Refactor plotting toward a cleaner separation between pure plotting/data-preparation logic and Tkinter GUI event handling.

## Rules

- Keep GUI callbacks thin.
- Move pure data transformation and plotting decisions into non-Tkinter functions where practical.
- Do not break current primary/secondary Y-axis behaviour.
- Preserve:
  - line plots
  - scatter plots
  - line + marker plots
  - secondary Y-axis
  - manual axis limits
  - auto axis limits
  - limit-line visibility in axis ranges
  - FFT plotting
  - external legend behaviour
  - save figure behaviour
- Avoid importing `tkinter` in pure plotting modules unless absolutely necessary.
- Prefer functions that accept data/config objects and return figure/axis results or calculated ranges.
- Keep matplotlib usage explicit.
- Do not change Eaton plot colours or styling unless requested.
