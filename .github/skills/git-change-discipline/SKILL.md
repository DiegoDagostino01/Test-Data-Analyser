---
name: git-change-discipline
description: "Use when: making multi-file code changes that should remain easy to review, commit, revert, or split into focused commits."
---

# Git Change Discipline

Make changes in small, reviewable batches.

## Rules

- Check the working tree before editing unless the user has explicitly listed all currently modified files and their states, or no terminal access is available.
- If the working tree check fails or the directory is not a git repository, report this to the user and ask them to confirm the current file states before proceeding.
- Keep each change focused on one responsibility.
- If a single-responsibility change affects more than 5 files, note this in the report and ask the user whether to proceed as one batch or split into stages.
- Do not mix unrelated refactors.
- If the user explicitly requests an action that conflicts with a rule above, comply but note in the report which rule is being overridden and why.
- Avoid formatting-only churn unless requested.
- Do not rename files or methods unless the user explicitly requests it.
- If a misleading name is clearly contributing to a bug, note it in the report and suggest a rename, but do not apply it without user confirmation.
- Remove code that becomes dead or unreachable as a direct result of this change only. Do not remove pre-existing dead code unless explicitly asked.
- Do not revert user changes unless explicitly asked.
- Report files changed and why.
- Suggest a concise commit message for every change, whether single-file or multi-file.
