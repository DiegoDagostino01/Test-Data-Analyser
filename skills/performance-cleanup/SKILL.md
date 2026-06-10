---
name: performance-cleanup
description: Use this when improving performance, caching, dataframe operations, UI rebuild efficiency, or large dataset responsiveness.
---

# Performance Cleanup

Improve performance without changing user-facing behaviour.

## Focus areas

- Avoid repeated full-column numeric conversion.
- Reuse existing caches where possible.
- Avoid unnecessary dataframe copies.
- Avoid rebuilding Tkinter widgets more often than necessary.
- Debounce expensive UI updates where appropriate.
- Keep pandas operations vectorized.
- Do not make clever changes that reduce readability.
- After changes, explain what was made more efficient and why it is safe.
