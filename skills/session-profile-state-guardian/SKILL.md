---
name: session-profile-state-guardian
description: Use this when changing plot profiles, session save/load, label state, engineering notes, limits, or per-plot configuration.
---

# Session Profile State Guardian

Protect per-plot-profile state in **Test Data Analyser**.

## Each plot profile should independently preserve

- X column.
- Selected Y columns.
- Secondary Y columns.
- Title.
- X label.
- Primary Y label.
- Secondary Y label.
- Manual label flags.
- Plot kind.
- Grid setting.
- Auto/manual axis limits.
- Secondary Y-axis limits.
- Analysis window.
- Filter settings.
- Legend settings.
- Raw data options.
- Engineering notes.
- Limit lines.
- Generated state.

## Rules

- Do not allow one plot tab's labels or selections to leak into another.
- Do not reset manual labels unless **Auto Labels** is explicitly used.
- Do not break secondary Y-axis profile restoration.
- No backward compatibility with old session files is required unless explicitly requested.
