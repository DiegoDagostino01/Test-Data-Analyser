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
- Keep `ARCHITECTURE.md` aligned with the actual module structure and dependency
  direction.
- Keep historical Tkinter references only in migration/history context.
- Document manual GUI checks after UI refactors when relevant.
- Do not over-document obvious Python code.
