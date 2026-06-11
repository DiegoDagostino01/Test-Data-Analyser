---
name: deprecation-and-migration
description: "Use when: retiring old Test Data Analyser code, replacing archived/migration-era behavior, moving users to a new implementation, or removing session/profile/state fields safely."
---

# Deprecation and Migration

Remove or replace old behavior deliberately. In this app, migration risk is mostly
about preserving user workflows, saved sessions, plot profiles, settings, exports,
and analysis results while simplifying the codebase.

## When To Use

- Removing code from migration-era or archived implementations.
- Replacing one implementation with another across layers.
- Retiring a setting, saved-session field, profile option, or exported format.
- Consolidating duplicate services, viewmodels, or Qt widgets.
- Deleting dead code that may still be referenced by tests, docs, sessions, or user workflows.

## Process

1. Inventory consumers with search and targeted reads: runtime code, tests, docs, config, sessions, and exports.
2. Confirm the replacement exists and covers the important behavior.
3. Preserve compatibility where reasonable, especially for session/profile/settings load paths.
4. Migrate one consumer path at a time.
5. Add tests for compatibility, fallback, or clear failure behavior.
6. Remove old code only after references are gone.
7. Update docs or version notes if user-visible behavior changes.

## Decision Questions

- Does the old behavior still provide unique user value?
- Is there a tested replacement?
- Are saved sessions or profiles from older versions expected to load?
- What is the failure mode if old data appears?
- Can removal be split into compatibility first, deletion second?

## Red Flags

- Deleting fields without checking session/profile restore.
- Removing code because it looks unused without searching tests and docs.
- Changing exported file shape without noting it.
- Migrating UI first while services/viewmodels still expose old contracts.
- Keeping two implementations indefinitely with no owner or cutoff.

## Verification

- No active references remain to removed code.
- Compatibility behavior is tested or explicitly documented.
- Existing tests pass with `python -m unittest discover -s tests`.
- User-visible migrations are mentioned in the final response and docs/version notes when appropriate.