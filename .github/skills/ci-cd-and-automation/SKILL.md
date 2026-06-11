---
name: ci-cd-and-automation
description: "Use when: adding or changing CI, GitHub Actions, automated unittest checks, dependency installation, or Qt offscreen test automation for this Python/PySide6 project."
---

# CI/CD and Automation

Automate the checks that keep the desktop app healthy. Tailor CI to this Python,
PySide6, pandas, and Matplotlib repository rather than importing web or Node
pipeline defaults.

## Quality Gates

At minimum, CI should be able to:

- Install Python dependencies from `requirements.txt`.
- Run `python -m unittest discover -s tests`.
- Set `QT_QPA_PLATFORM=offscreen` for Qt-related tests.
- Fail clearly when imports, tests, or package setup break.

Optional gates can include linting, formatting checks, packaging smoke tests, or
artifact builds if the repo adopts those tools explicitly.

## GitHub Actions Shape

Use this as the default pattern when adding a workflow:

```yaml
name: Tests

on:
  push:
  pull_request:

jobs:
  unittest:
    runs-on: windows-latest
    env:
      QT_QPA_PLATFORM: offscreen
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"
      - name: Install dependencies
        run: python -m pip install -r requirements.txt
      - name: Run tests
        run: python -m unittest discover -s tests
```

Prefer Windows for the primary job because this app is developed and used on
Windows. Add Linux/macOS matrix jobs only when the project needs cross-platform
coverage.

## CI Failure Workflow

- Read the first real failure, not just the final exit code.
- Reproduce locally when feasible.
- Use `debugging-and-error-recovery` for failing tests or import errors.
- Fix the root cause instead of weakening CI.
- Do not skip tests unless the user explicitly approves a temporary quarantine with a follow-up plan.

## Secrets and Artifacts

- Do not put secrets in workflow files.
- Do not upload user data, local test data, or generated engineering files as artifacts unless they are scrubbed and intentional.
- Keep workflow triggers and permissions minimal.

## Verification

- Workflow syntax is valid.
- CI commands match local project commands.
- Qt tests set `QT_QPA_PLATFORM=offscreen`.
- New checks are documented in the final response.
- The same command passes locally before relying on CI when feasible.