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

1. Inventory consumers with search and targeted reads: runtime code, tests, docs, config, sessions, and exports. If a complete inventory cannot be confirmed (for example, field names are constructed dynamically or used as serialized strings), do not proceed with removal. Flag the uncertainty explicitly in the response and propose a conservative compatibility wrapper as an intermediate step.
2. Confirm the replacement exists and covers the important behavior.
2a. If there is no replacement because the feature is being removed entirely, document the intentional removal in version notes, confirm no active user workflows depend on the feature via the inventory from Step 1, and skip Steps 3-5 for the deprecated path. Proceed directly to removal and update docs to state the feature is no longer available.
3. Preserve compatibility for any field that is read from disk (session files, profiles, or settings). Compatibility shims for in-memory-only objects are not required.
4. Migrate one consumer path at a time.
5. Add tests for compatibility, fallback, or clear failure behavior.
5a. If a compatibility shim was added in Step 3, document its intended removal condition (for example, after one release cycle or after all known session files have been migrated). Do not remove the shim in the same change that removes the original code.
6. Remove old code only after all references are gone from runtime code, tests, documentation, comments, and configuration files.
7. Update docs or version notes if any of the following change: UI behavior, exported file format, session/profile field names, or settings keys.

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
- Session files written by the new implementation can still be loaded correctly if a user downgrades. If backward compatibility cannot be guaranteed, note this explicitly in the version notes and in the response.
- Existing tests pass with `python -m unittest discover -s tests`.
- User-visible migrations are mentioned in the final response and docs/version notes when appropriate.