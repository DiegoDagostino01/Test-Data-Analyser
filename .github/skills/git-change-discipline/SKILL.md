---
name: git-change-discipline
description: "Use when: making multi-file code changes that should remain easy to review, commit, revert, or split into focused commits."
---

# Git Change Discipline

Make changes in small, reviewable batches.

## Rules

- Check the working tree before editing when feasible.
- Keep each change focused on one responsibility.
- Do not mix unrelated refactors.
- Avoid formatting-only churn unless requested.
- Avoid renaming files or methods unless useful and justified.
- Remove dead code created by the change.
- Do not revert user changes unless explicitly asked.
- Report files changed and why.
- Suggest a concise commit message for multi-file changes.
