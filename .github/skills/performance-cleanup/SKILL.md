---
name: performance-cleanup
description: "Use when: improving performance, caching, dataframe operations, Qt table/model refreshes, plotting responsiveness, or large dataset handling."
---

# Performance Cleanup

Improve performance without changing user-facing behaviour. If a meaningful
performance gain is only achievable by altering user-facing behaviour (e.g.,
changing result precision, dropping edge-case support), do not make the change.
Instead, add a code comment flagging the trade-off and explain it in your
response.

## Focus areas

- Avoid repeated full-column numeric conversion; reuse caches scoped to a single
  function call or a clearly bounded object lifetime (e.g., a widget that owns
  its data); do not cache across ambiguous ownership boundaries.
- Avoid unnecessary dataframe copies.
- Keep pandas/numpy operations vectorized only when the result remains plainly
  readable and does not introduce cleverness that obscures intent.
- Only modify code within the project codebase. If the bottleneck is inside a
  third-party library, document it with a comment and suggest an alternative API
  or library in your explanation instead of patching library code.
- Avoid rebuilding Qt models, widgets, tables, and plot canvases more often than
  necessary.
- Debounce or coalesce UI refreshes that can be triggered more than once per
  user action or data update cycle (e.g., signals fired in a loop, resize events,
  live data feeds).
- Keep Matplotlib redraw/export work scoped to real changes.
- Do not make clever changes that reduce readability.
- Add focused regression tests when logic changes: at minimum, a test asserting
  the operation runs in O(n) or better (e.g., by timing two inputs of size n and
  10n and asserting the ratio is below a constant), or a call-count assertion
  using a mock or profiler.
- Explain what became more efficient and why the change is behaviour-safe.
