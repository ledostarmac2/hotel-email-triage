$ErrorActionPreference = "Stop"

# VS Code auto-activates project venvs, which may not have PyInstaller.
# Skip any python inside a .venv or .build-venv folder; use the first system Python.
$PYTHON = $null
$candidates = Get-Command python -All -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
foreach ($c in $candidates) {
    if ($c -match '[\\/]\.(venv|build-venv)[\\/]') { continue }
    $PYTHON = $c
    break
}
if (-not $PYTHON) { throw "Could not find a system Python. Ensure Python is installed outside any virtual environment." }
Write-Host "Using Python: $PYTHON"

# If the previous EXE is locked (e.g. by Windows Defender scanning it),
# rename it out of the way so PyInstaller can write the new one.
$oldExe = Join-Path (Get-Location) "dist\ReplyRight.exe"
if (Test-Path $oldExe) {
    try {
        Remove-Item $oldExe -Force -ErrorAction Stop
    } catch {
        $backupExe = $oldExe + ".old"
        Remove-Item $backupExe -Force -ErrorAction SilentlyContinue
        Rename-Item $oldExe $backupExe -Force -ErrorAction Stop
    }
}

$vendorPath = Join-Path (Get-Location) ".vendor"
$runtimePackages = @(
    "fastapi",
    "uvicorn[standard]",
    "httpx",
    "python-dotenv",
    "openai",
    "anthropic",
    "pywebview>=4.4,<6",
    "pythonnet",
    "pywin32"
)

if (-not (Test-Path $vendorPath)) {
    $env:TEMP = Join-Path (Get-Location) ".build-tmp"
    $env:TMP = $env:TEMP
    New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
    New-Item -ItemType Directory -Force -Path $vendorPath | Out-Null
    # Keep runtime dependencies in .vendor so the EXE can be rebuilt on a
    # machine that does not already have the same packages globally installed.
    # Ignore pip resolver warnings about globally-installed packages (e.g. semantic-kernel)
    # that are not part of this vendor install — they do not affect the EXE.
    & $PYTHON -m pip install --no-cache-dir --target $vendorPath $runtimePackages 2>&1 | Where-Object { $_ -notmatch "^ERROR: pip" -and $_ -notmatch "dependency resolver" -and $_ -notmatch "behaviour is the source" -and $_ -notmatch "incompatible" } | Write-Host
} elseif (-not (Test-Path (Join-Path $vendorPath "win32com"))) {
    & $PYTHON -m pip install --no-cache-dir --upgrade --target $vendorPath pywin32 2>&1 | Write-Host
}

& $PYTHON -m PyInstaller `
    --onefile `
    --windowed `
    --name ReplyRight `
    --icon "outlook_dashboard/static/replyright.ico" `
    --paths $vendorPath `
    --add-data "outlook_dashboard/static;outlook_dashboard/static" `
    --collect-all webview `
    --collect-all pythonnet `
    --collect-all outlook_dashboard `
    --collect-submodules win32com `
    --hidden-import webview.platforms.edgechromium `
    --hidden-import webview.platforms.winforms `
    --hidden-import clr `
    --hidden-import pythoncom `
    --hidden-import pywintypes `
    --hidden-import win32com.client `
    run_desktop.py

$exePath = (Resolve-Path "dist\ReplyRight.exe").Path

# Copy .env next to the EXE so it can load API keys at runtime
if (Test-Path ".env") {
    Copy-Item ".env" "dist\.env" -Force
    Write-Host "Copied .env to dist\"
}

function New-ReplyRightShortcut {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Target
    )

    $shell = New-Object -ComObject WScript.Shell
    $shortcut = $shell.CreateShortcut($Path)
    $shortcut.TargetPath = $Target
    $shortcut.WorkingDirectory = Split-Path $Target
    $shortcut.IconLocation = "$Target,0"
    $shortcut.Description = "ReplyRight"
    $shortcut.Save()
}

$desktopShortcut = Join-Path ([Environment]::GetFolderPath("DesktopDirectory")) "ReplyRight.lnk"
$startMenuShortcut = Join-Path ([Environment]::GetFolderPath("Programs")) "ReplyRight.lnk"

try {
    New-ReplyRightShortcut -Path $desktopShortcut -Target $exePath
} catch {
    $fallbackDesktop = Join-Path $env:USERPROFILE "Desktop\ReplyRight.lnk"
    try {
        New-ReplyRightShortcut -Path $fallbackDesktop -Target $exePath
        $desktopShortcut = $fallbackDesktop
    } catch {
        Write-Warning "Could not create Desktop shortcut: $($_.Exception.Message)"
    }
}
try {
    New-ReplyRightShortcut -Path $startMenuShortcut -Target $exePath
} catch {
    Write-Warning "Could not create Start Menu shortcut: $($_.Exception.Message)"
}

Write-Host "Built $exePath"
if (Test-Path $desktopShortcut) {
    Write-Host "Created shortcut $desktopShortcut"
}
if (Test-Path $startMenuShortcut) {
    Write-Host "Created shortcut $startMenuShortcut"
}
