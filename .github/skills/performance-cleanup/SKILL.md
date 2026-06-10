---
name: performance-cleanup
description: "Use when: improving performance, caching, dataframe operations, Qt table/model refreshes, plotting responsiveness, or large dataset handling."
---

# Performance Cleanup

Improve performance without changing user-facing behaviour.

## Focus areas

- Avoid repeated full-column numeric conversion; reuse scoped caches where the
  data lifetime is clear.
- Avoid unnecessary dataframe copies.
- Keep pandas/numpy operations vectorized where readable.
- Avoid rebuilding Qt models, widgets, tables, and plot canvases more often than
  necessary.
- Debounce or coalesce expensive UI refreshes when appropriate.
- Keep Matplotlib redraw/export work scoped to real changes.
- Do not make clever changes that reduce readability.
- Add focused regression/performance-shape tests when logic changes.
- Explain what became more efficient and why the change is behaviour-safe.
