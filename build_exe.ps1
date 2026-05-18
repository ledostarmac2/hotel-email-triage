$ErrorActionPreference = "Stop"

# Prefer the project venv if it has PyInstaller (avoids Windows App Store Python --target restriction).
# Fall back to the first non-venv system Python if the venv lacks PyInstaller.
$PYTHON = $null
$venvPython = Join-Path (Get-Location) ".venv\Scripts\python.exe"
if (Test-Path $venvPython) {
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $pyiCheck = & $venvPython -m PyInstaller --version 2>$null
        if ($LASTEXITCODE -eq 0) { $PYTHON = $venvPython }
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
}
if (-not $PYTHON) {
    $candidates = Get-Command python -All -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source
    foreach ($c in $candidates) {
        if ($c -match '[\\/]\.(venv|build-venv)[\\/]') { continue }
        $PYTHON = $c
        break
    }
}
if (-not $PYTHON) { throw "Could not find a Python with PyInstaller. Run: pip install pyinstaller" }
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
    & $PYTHON -m pip install --no-cache-dir --target $vendorPath $runtimePackages 2>&1 | Where-Object { $_ -notmatch "^ERROR: pip" -and $_ -notmatch "dependency resolver" -and $_ -notmatch "behaviour is the source" -and $_ -notmatch "incompatible" } | Write-Host
} else {
    # Check for packages that may have been added since .vendor was last built
    $vendorChecks = @{
        "win32com"  = "pywin32"
        "anthropic" = "anthropic"
        "httpx"     = "httpx"
        "openai"    = "openai"
    }
    $toInstall = @()
    foreach ($dir in $vendorChecks.Keys) {
        if (-not (Test-Path (Join-Path $vendorPath $dir))) {
            $toInstall += $vendorChecks[$dir]
        }
    }
    if ($toInstall.Count -gt 0) {
        Write-Host "Installing missing vendor packages: $($toInstall -join ', ')"
        & $PYTHON -m pip install --no-cache-dir --upgrade --target $vendorPath $toInstall 2>&1 | Write-Host
    }
}

# Embed build metadata so the running EXE can report its own version/commit.
$gitCommit = try { (git rev-parse HEAD 2>$null).Trim() } catch { "unknown" }
if (-not $gitCommit) { $gitCommit = "unknown" }
$gitShort = $gitCommit.Substring(0, [Math]::Min(8, $gitCommit.Length))
$buildDate = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
$initContent = Get-Content "outlook_dashboard\__init__.py" -Raw -ErrorAction SilentlyContinue
$appVersion = if ($initContent -match '"(\d+\.\d+\.\d+)"') { $Matches[1] } else { "0.1.0" }
$buildInfoJson = "{`"commit`":`"$gitShort`",`"build_date`":`"$buildDate`",`"version`":`"$appVersion`"}"
$buildInfoJson | Set-Content "outlook_dashboard\build_info.json" -Encoding utf8
Write-Host "Build metadata: $buildInfoJson"

& $PYTHON -m PyInstaller `
    --onefile `
    --windowed `
    --name ReplyRight `
    --icon "outlook_dashboard/static/replyright.ico" `
    --paths $vendorPath `
    --add-data "outlook_dashboard/static;outlook_dashboard/static" `
    --add-data "outlook_dashboard/build_info.json;outlook_dashboard" `
    --collect-all webview `
    --collect-all pythonnet `
    --collect-all outlook_dashboard `
    --collect-all anthropic `
    --collect-all sklearn `
    --collect-all scikit_learn `
    --collect-all dateparser `
    --collect-all joblib `
    --collect-all threadpoolctl `
    --collect-submodules win32com `
    --hidden-import webview.platforms.edgechromium `
    --hidden-import webview.platforms.winforms `
    --hidden-import clr `
    --hidden-import pythoncom `
    --hidden-import pywintypes `
    --hidden-import win32com.client `
    --hidden-import sklearn.utils._cython_blas `
    --hidden-import sklearn.neighbors._partition_nodes `
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
