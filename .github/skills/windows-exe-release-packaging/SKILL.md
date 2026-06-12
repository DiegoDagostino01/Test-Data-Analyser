---
name: windows-exe-release-packaging
description: "Use when: generating, rebuilding, testing, cleaning, or distributing the Windows .exe / PyInstaller launch folder for Test Data Analyser, including shortcut icon updates and release handoff."
---

# Windows EXE Release Packaging

Use this skill when preparing or refreshing the Windows executable release for
Test Data Analyser.

## Packaging Position

- Keep PyInstaller `--onedir` as the default build engine for this app.
- Do not switch to `--onefile` unless the settings/config path behavior has been
  reviewed again; the app expects bundled files such as `config/settings.json`
  and Qt assets to exist beside the frozen app.
- Treat the generated launch folder as a frozen release artifact. Python source
  edits in the repo do not update the existing `.exe` automatically.
- Rebuild the bundle after Python code, dependency, version, icon, import, or
  packaging changes.
- Replacing individual files in `_internal/` is acceptable only for files that
  are not compiled or linked code: specifically, config files such as
  `config/settings.json` and image/icon assets such as `app_icon.png` or
  `app_icon.ico`; and only after a smoke test confirms the packaged app still
  starts correctly.

## Pre-Build Checks

- Confirm the source app still runs from the repo when relevant.
- Run `python -m unittest discover -s tests` before a release build.
- Set `QT_QPA_PLATFORM=offscreen` for Qt tests and packaged startup smoke tests.
- Confirm `requirements.txt` includes any new runtime dependency.
- Update `__version__` in `test_data_analyser/core/config.py` and add a top
  entry to `VERSION_HISTORY.md` for release-facing changes.
- Keep the app icon assets in `test_data_analyser/qt_app/assets/`:
  `app_icon.png` for Qt runtime and `app_icon.ico` for the Windows executable
  and shortcut.

## Build Command

Use this PyInstaller shape from the repo root:

```powershell
python -m PyInstaller --noconfirm --clean --onedir --windowed `
  --name "Test Data Analyser" `
  --icon "test_data_analyser\qt_app\assets\app_icon.ico" `
  --add-data "config\settings.json;config" `
  --add-data "test_data_analyser\qt_app\assets;test_data_analyser\qt_app\assets" `
  --hidden-import openpyxl `
  --hidden-import xlrd `
  --hidden-import xlsxwriter `
  --hidden-import pyarrow `
  --hidden-import scipy `
  --hidden-import reportlab `
  --hidden-import docx `
  run_qt_app.py
```

If a dependency is removed from the app, remove unnecessary hidden imports only
after checking that the packaged app still starts and the full test suite passes.

If the PyInstaller command exits with a non-zero code, stop immediately. Do not
proceed with Refresh Launch Folder or Cleanup. Report the last 30 lines of
PyInstaller output and ask the user how to proceed.

## Refresh Launch Folder

After a successful build, replace the user-facing launch folder with the new
`dist` output:

```powershell
Remove-Item -Recurse -Force "Test Data Analyser Launch" -ErrorAction Stop
Copy-Item -Recurse "dist\Test Data Analyser" "Test Data Analyser Launch" -ErrorAction Stop
```

If `Copy-Item` fails after `Remove-Item` has already deleted the launch folder,
warn the user immediately: the previous launch folder has been deleted and the
replacement failed. Advise them to re-run the build and refresh steps, or
restore from source control before distributing.

Keep this release shape for handoff:

```text
Test Data Analyser.lnk
Test Data Analyser Launch/
  Test Data Analyser.exe
  _internal/
```

The `.exe` must stay beside `_internal/`. Do not distribute the `.exe` alone.

## Refresh Shortcut

Recreate or update the root shortcut so its target, working directory, and icon
all point at the refreshed launch folder:

Before running the shortcut script, confirm that `Get-Location` returns the repo
root: the directory containing `Test Data Analyser Launch\`. If it does not,
instruct the user to `cd` to the repo root first, or replace `(Get-Location)`
with the explicit absolute path.

```powershell
$shortcutPath = Join-Path (Get-Location) 'Test Data Analyser.lnk'
$targetPath = Join-Path (Get-Location) 'Test Data Analyser Launch\Test Data Analyser.exe'
$workingDirectory = Join-Path (Get-Location) 'Test Data Analyser Launch'
$iconPath = Join-Path (Get-Location) 'Test Data Analyser Launch\_internal\test_data_analyser\qt_app\assets\app_icon.ico'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $targetPath
$shortcut.WorkingDirectory = $workingDirectory
$shortcut.IconLocation = "$iconPath,0"
$shortcut.Save()
```

Pointing the shortcut directly at the `.ico` is more reliable than relying on
Windows to extract the icon from the `.exe`.

## Verification

Run these checks before calling the release ready:

- Focused Qt checks when UI metadata changed:
  `python -m unittest tests.test_qt_adapters.MainWindowLayoutTests`
- Full suite:
  `python -m unittest discover -s tests`
- Confirm launch folder contents are `Test Data Analyser.exe` and `_internal/`.
- Confirm bundled icon exists at
  `Test Data Analyser Launch/_internal/test_data_analyser/qt_app/assets/app_icon.ico`.
- Smoke-test the packaged app offscreen:

```powershell
$exe = Join-Path (Get-Location) 'Test Data Analyser Launch\Test Data Analyser.exe'
$workdir = Join-Path (Get-Location) 'Test Data Analyser Launch'
$env:QT_QPA_PLATFORM = 'offscreen'
$process = Start-Process -FilePath $exe -WorkingDirectory $workdir -PassThru
$exited = $process.WaitForExit(8000)
if ($exited -and $process.ExitCode -ne 0) { exit $process.ExitCode }
if (-not $exited) { $process.Kill(); $process.WaitForExit() }
```

Expected outcome: the process should not exit within 8 seconds, meaning
`$exited` is `$false` and the GUI is running. If it exits within 8 seconds with
a non-zero exit code, the smoke test fails. If it exits within 8 seconds with
exit code 0, treat this as unexpected and flag it for manual verification,
because a healthy GUI app should not self-terminate.

For the smoke test, staying alive until killed means the GUI started
successfully under the offscreen platform.

## Cleanup

After copying the refreshed launch folder, remove generated build leftovers
unless the user has stated in the current conversation that they want to keep or
inspect the `build/`, `dist/`, `.spec`, or `__pycache__/` artifacts:

```powershell
Remove-Item -Recurse -Force "build", "dist" -ErrorAction SilentlyContinue
Remove-Item -Force "Test Data Analyser.spec" -ErrorAction SilentlyContinue
Remove-Item -Recurse -Force "__pycache__" -ErrorAction SilentlyContinue
```

Do not remove source files, tests, docs, config, `.github/skills/`, the launch
folder, or the root shortcut during cleanup.

## Final Response Checklist

Report only the high-signal release facts:

- Files changed, especially version/history/icon or packaging workflow changes.
- Build result and where the runnable bundle lives.
- Tests and packaged smoke checks run.
- Whether `build/`, `dist/`, `.spec`, and root `__pycache__/` were cleaned.
- Distribution shape: root shortcut plus `Test Data Analyser Launch/`.