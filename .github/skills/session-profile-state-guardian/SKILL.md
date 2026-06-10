---
name: session-profile-state-guardian
description: "Use when: changing plot profiles, session save/load, generated plot restore, label state, engineering notes, limits, runs, maths channels, legend state, or per-plot configuration."
---

# Session Profile State Guardian

Protect saved analysis-session and per-plot-profile state.

## State to preserve

- X column, selected primary Y columns, and selected secondary Y columns.
- Title, X label, primary Y label, secondary Y label, and manual label flags.
- Plot kind, filter settings, analysis window, axis padding, auto/manual axis
  limits, secondary Y-axis limits, legend settings, and figure appearance.
- Raw data options and selected data behaviour.
- Engineering Notes and Requirements/Limits.
- Maths channel definitions and recalculation on restore.
- Runs / Comparison entries, active run, enabled state, colours, and comparison
  settings.
- Generated plot state and restore-after-load behaviour.
- Cursor compare data should clear or restore only when intentionally supported.

## Rules

- Use `MainWindowViewModel.capture_working_state()` and `restore_session()` as
  the session boundary.
- Keep domain session models tolerant of missing keys unless a prompt explicitly
  allows a breaking format change.
- Do not allow labels, selections, limits, notes, or generated state to leak
  between plot profiles.
- Do not reset manual labels unless auto-label behaviour is explicitly invoked.
- Do not break secondary Y-axis profile restoration.
- Add regression tests for session/profile changes whenever practical.
