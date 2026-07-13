[CmdletBinding()]
param(
    [string]$PythonExecutable = ".\.venv\Scripts\python.exe",
    [switch]$SkipTests,
    [switch]$KeepBuildArtifacts
)

$ErrorActionPreference = "Stop"
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
Push-Location $repoRoot
try {
    if (-not (Test-Path $PythonExecutable)) {
        throw "Python executable not found: $PythonExecutable"
    }
    & $PythonExecutable -c "import PyInstaller" 2>$null
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller is not installed. Run: $PythonExecutable -m pip install -r requirements-build.txt"
    }
    if (-not $SkipTests) {
        $env:QT_QPA_PLATFORM = "offscreen"
        & $PythonExecutable -m unittest discover -s tests
        if ($LASTEXITCODE -ne 0) { throw "Test suite failed; release build stopped." }
    }

    $assets = Join-Path $repoRoot "test_data_analyser\qt_app\assets"
    & $PythonExecutable -m PyInstaller --noconfirm --clean --onedir --windowed `
        --name "Test Data Analyser" `
        --icon (Join-Path $assets "app_icon.ico") `
        --add-data "$assets;test_data_analyser\qt_app\assets" `
        --hidden-import openpyxl `
        --hidden-import xlrd `
        --hidden-import scipy `
        run_qt_app.py
    if ($LASTEXITCODE -ne 0) { throw "PyInstaller build failed." }

    $distFolder = Join-Path $repoRoot "dist\Test Data Analyser"
    $launchFolder = Join-Path $repoRoot "Test Data Analyser Launch"
    $licenseSource = & $PythonExecutable -c "import sys; from pathlib import Path; import PySide6QtAds; root=Path(PySide6QtAds.__file__).resolve().parent; matches=list(root.rglob('license/ads/LICENSE')); len(matches) == 1 or sys.exit(f'Expected one QtAds license, found {len(matches)}'); print(str(matches[0]))"
    if ($LASTEXITCODE -ne 0 -or -not $licenseSource -or -not (Test-Path $licenseSource)) {
        throw "The installed PySide6-QtAds license could not be located."
    }
    $licenseFolder = Join-Path $distFolder "THIRD_PARTY_LICENSES"
    New-Item -ItemType Directory -Force -Path $licenseFolder | Out-Null
    Copy-Item "THIRD_PARTY_NOTICES.md" (Join-Path $distFolder "THIRD_PARTY_NOTICES.md") -Force
    Copy-Item $licenseSource (Join-Path $licenseFolder "PySide6-QtAds-LICENSE.txt") -Force
    Copy-Item "README.md" (Join-Path $distFolder "README.md") -Force

    & $PythonExecutable "tools\scan_release_artifacts.py" $distFolder
    if ($LASTEXITCODE -ne 0) { throw "Release artifact sanitization failed." }

    $stagingFolder = "$launchFolder.new"
    $previousFolder = "$launchFolder.previous"
    Remove-Item -Recurse -Force $stagingFolder, $previousFolder -ErrorAction SilentlyContinue
    Copy-Item -Recurse $distFolder $stagingFolder
    & $PythonExecutable "tools\scan_release_artifacts.py" $stagingFolder
    if ($LASTEXITCODE -ne 0) { throw "Staged release artifact sanitization failed." }

    if (Test-Path $launchFolder) {
        Move-Item $launchFolder $previousFolder
    }
    try {
        Move-Item $stagingFolder $launchFolder
    }
    catch {
        if (Test-Path $previousFolder) {
            Move-Item $previousFolder $launchFolder
        }
        throw
    }
    Remove-Item -Recurse -Force $previousFolder -ErrorAction SilentlyContinue

    $shortcutPath = Join-Path $repoRoot "Test Data Analyser.lnk"
    $targetPath = Join-Path $launchFolder "Test Data Analyser.exe"
    $iconPath = Join-Path $launchFolder "_internal\test_data_analyser\qt_app\assets\app_icon.ico"
    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($shortcutPath)
    $shortcut.TargetPath = $targetPath
    $shortcut.WorkingDirectory = $launchFolder
    $shortcut.IconLocation = "$iconPath,0"
    $shortcut.Save()

    $env:QT_QPA_PLATFORM = "offscreen"
    $process = Start-Process -FilePath $targetPath -WorkingDirectory $launchFolder -PassThru
    $exited = $process.WaitForExit(8000)
    if ($exited) {
        throw "Packaged application exited unexpectedly with code $($process.ExitCode)."
    }
    $process.Kill()
    $process.WaitForExit()
    Write-Output "Release build and packaged startup smoke test passed: $launchFolder"
}
finally {
    if (-not $KeepBuildArtifacts) {
        Remove-Item -Recurse -Force "build", "dist" -ErrorAction SilentlyContinue
        Remove-Item -Force "Test Data Analyser.spec" -ErrorAction SilentlyContinue
        Remove-Item -Recurse -Force "__pycache__" -ErrorAction SilentlyContinue
    }
    Pop-Location
}