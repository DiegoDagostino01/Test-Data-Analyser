---
name: session-profile-state-guardian
description: "Use when: changing plot profiles, session save/load, generated plot restore, label state, engineering notes, limits, runs, maths channels, legend state, or per-plot configuration."
---

# Session Profile State Guardian

Protect saved analysis-session and per-plot-profile state.

## State to preserve

Restore in the order listed; treat missing keys according to the tolerance rule
unless marked required.

### Axis, Plot, And Labels

- X column, selected primary Y columns, and selected secondary Y columns.
- Title, X label, primary Y label, secondary Y label, and manual label flags.
- Plot kind, filter settings, analysis window, axis padding, auto/manual axis
  limits, secondary Y-axis limits, legend settings, and figure appearance.

### Data Sources

- Raw data options and selected data behaviour.

### Annotations And Notes

- Engineering Notes and Requirements/Limits.

### Maths Channels

- Maths channel definitions and recalculation on restore.
- If a maths channel definition references a column that no longer exists at
  capture time, serialize the definition as-is and mark it invalid in the
  session model. On restore, skip recalculation for marked-invalid channels and
  surface a warning to the user rather than raising an exception.

### Runs And Comparisons

- Runs / Comparison entries, active run, enabled state, colours, and comparison
  settings.
- Generated plot state and restore-after-load behaviour.
- Cursor compare data must be cleared on session load unless a dedicated
  restore code path exists in the session model and is explicitly invoked. Do
  not attempt partial restoration.

## Rules

- Use `MainWindowViewModel.capture_working_state()` and `restore_session()` as
  the session boundary.
- If `restore_session()` receives a null, empty, or unparseable payload, abort
  the restore, leave the current state unchanged, and log an error. Do not
  partially apply state from a corrupt payload.
- Keep domain session models tolerant of missing keys unless a prompt explicitly
  allows a breaking format change.
- A breaking format change is defined as: removing a previously serialized key,
  renaming a key, or changing a key's value type. Any such change requires an
  explicit instruction in the task prompt stating "this is a breaking session
  format change" before the model may implement it.
- Do not allow labels, selections, limits, notes, or generated state to leak
  between plot profiles.
- Do not reset manual labels unless auto-label behaviour is explicitly invoked.
- Do not break secondary Y-axis profile restoration.
- Add regression tests for every session/profile change that modifies
  serialization, deserialization, or state restoration logic. Only omit tests
  when the change is purely cosmetic, such as a label rename with no structural
  impact.
