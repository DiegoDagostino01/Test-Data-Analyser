---
name: engineering-app-documentation
description: "Use when: updating README, ARCHITECTURE.md, migration notes, user notes, implementation notes, or internal engineering documentation for the app."
---

# Engineering App Documentation

Write concise engineering-focused documentation for Test Data Analyser.

## Rules

- Be practical and direct.
- Explain what changed, why it matters, and how to use it.
- Avoid marketing language.
- Keep terminology consistent with the app: PySide6 / Qt UI, viewmodels,
  services, domain, core, `OperationResult`, analysis sessions, Requirements /
  Limits, Runs / Comparison, Maths Channels, Raw Data, Engineering Notes, and
  Point Compare.
- If a concept is not covered by the terminology list above, use the exact name
  as it appears in the source code. Do not invent synonyms or abbreviations.
- Use document-type formats consistently: README files use short prose sections
  with code examples; ARCHITECTURE.md uses module tables and dependency
  diagrams; migration notes use numbered step lists with before/after code
  snippets; user notes use task-oriented numbered steps with no internal jargon.
- Keep `ARCHITECTURE.md` aligned with the actual module structure and dependency
  direction.
- Keep historical Tkinter references only in migration/history context.
- Document manual GUI checks after UI refactors only when the refactor changes
  visible widget layout, signal/slot wiring, or user-facing behaviour.
- Do not document standard Python idioms such as list comprehensions, property
  accessors, or `__init__` parameter assignments. Do document any non-trivial
  algorithm, design decision, or Qt-specific behaviour.
