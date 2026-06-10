# VS Code Agent Skills for Test Data Analyser

This repository contains GitHub Copilot / VS Code Agent Skills for the current
PySide6 / Qt Test Data Analyser workflow.

## Active placement

The active VS Code discovery location is:

```text
.github/
  copilot-instructions.md
  skills/
    python-refactor-safely/
      SKILL.md
    pyside6-qt-gui-maintainer/
      SKILL.md
    plotting-engine-separation/
      SKILL.md
    pandas-data-cleaning-analysis/
      SKILL.md
    code-review-bug-hunter/
      SKILL.md
    python-test-writer/
      SKILL.md
    performance-cleanup/
      SKILL.md
    session-profile-state-guardian/
      SKILL.md
    engineering-app-documentation/
      SKILL.md
    git-change-discipline/
      SKILL.md
```

Skills are maintained only under `.github/skills/`. Do not recreate a root
`skills/` mirror; update the active `.github/skills/<name>/SKILL.md` file when a
skill changes.

## Skill triggers

| Skill | Use when |
| --- | --- |
| `python-refactor-safely` | Refactoring layered Python modules or moving responsibilities. |
| `pyside6-qt-gui-maintainer` | Modifying Qt widgets, layouts, signals, dialogs, or Matplotlib canvas code. |
| `plotting-engine-separation` | Changing plotting, FFT, legends, axis limits, figure export, or plot data preparation. |
| `pandas-data-cleaning-analysis` | Working on CSV/Excel loading, numeric coercion, raw data, filtering, statistics, or export. |
| `code-review-bug-hunter` | Reviewing changed Python/Qt code for regressions. |
| `python-test-writer` | Adding or updating the `unittest`-based test suite. |
| `performance-cleanup` | Improving responsiveness, caching, dataframe operations, or UI rebuild cost. |
| `session-profile-state-guardian` | Changing sessions, plot profiles, generated state, labels, limits, notes, or per-plot configuration. |
| `engineering-app-documentation` | Updating README, architecture, migration, or engineering notes. |
| `git-change-discipline` | Making multi-file changes that should stay reviewable and easy to revert. |
