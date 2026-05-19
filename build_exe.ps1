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

# If a previous build is locked (e.g. by Windows Defender scanning it), rename
# it out of the way so PyInstaller can write the new onedir bundle.
$distRoot = Join-Path (Get-Location) "dist"
$oldOneFileExe = Join-Path $distRoot "ReplyRight.exe"
$appDir = Join-Path $distRoot "ReplyRight"
if (Test-Path $oldOneFileExe) {
    try {
        Remove-Item $oldOneFileExe -Force -ErrorAction Stop
    } catch {
        $backupExe = $oldOneFileExe + ".old"
        Remove-Item $backupExe -Force -ErrorAction SilentlyContinue
        Rename-Item $oldOneFileExe $backupExe -Force -ErrorAction Stop
    }
}
if (Test-Path $appDir) {
    try {
        Remove-Item $appDir -Recurse -Force -ErrorAction Stop
    } catch {
        $backupDir = Join-Path $distRoot "ReplyRight.old"
        Remove-Item $backupDir -Recurse -Force -ErrorAction SilentlyContinue
        Rename-Item $appDir $backupDir -Force -ErrorAction Stop
    }
}

$vendorPath = Join-Path (Get-Location) ".vendor"
$runtimePackages = @(
    "fastapi",
    "uvicorn[standard]",
    "httpx",
    "requests",
    "python-dotenv",
    "openai",
    "anthropic",
    "PySide6>=6.7",
    "pywin32",
    "dateparser",
    "scikit-learn",
    "joblib",
    "threadpoolctl"
)

function Invoke-VendorPipInstall {
    param(
        [Parameter(Mandatory = $true)][string[]]$Packages,
        [switch]$Upgrade
    )

    $pipArgs = @("-m", "pip", "install", "--no-cache-dir")
    if ($Upgrade) {
        $pipArgs += "--upgrade"
    }
    $pipArgs += @("--target", $vendorPath)
    $pipArgs += $Packages

    # pip writes dependency-resolution warnings to stderr even when the install
    # succeeds. With $ErrorActionPreference="Stop", PowerShell can treat those
    # warning lines as NativeCommandError and abort clean CI builds before
    # PyInstaller starts. Capture output under Continue, then enforce the real
    # native exit code ourselves.
    $previousErrorActionPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        $output = & $PYTHON @pipArgs 2>&1
        $exitCode = $LASTEXITCODE
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }

    $output |
        Where-Object {
            $_ -notmatch "^ERROR: pip" -and
            $_ -notmatch "dependency resolver" -and
            $_ -notmatch "behaviour is the source" -and
            $_ -notmatch "incompatible"
        } |
        Write-Host

    if ($exitCode -ne 0) {
        throw "pip install failed with exit code $exitCode"
    }
}

# Wipe stale vendor cache if it contains pywebview (old WebView2 stack)
if ((Test-Path $vendorPath) -and (Test-Path (Join-Path $vendorPath "webview"))) {
    Write-Host "Removing stale vendor cache (pywebview detected - replaced by PySide6)"
    Remove-Item $vendorPath -Recurse -Force
}

if (-not (Test-Path $vendorPath)) {
    $env:TEMP = Join-Path (Get-Location) ".build-tmp"
    $env:TMP = $env:TEMP
    New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
    New-Item -ItemType Directory -Force -Path $vendorPath | Out-Null
    try {
        Invoke-VendorPipInstall -Packages $runtimePackages
    } catch {
        Remove-Item $vendorPath -Recurse -Force -ErrorAction SilentlyContinue
        throw
    }
} else {
    # Check for packages that may have been added since .vendor was last built
    $vendorChecks = @{
        "win32com"      = "pywin32"
        "anthropic"     = "anthropic"
        "dateparser"    = "dateparser"
        "httpx"         = "httpx"
        "requests"      = "requests"
        "joblib"        = "joblib"
        "openai"        = "openai"
        "sklearn"       = "scikit-learn"
        "threadpoolctl" = "threadpoolctl"
        "PySide6"       = "PySide6>=6.7"
    }
    $toInstall = @()
    foreach ($dir in $vendorChecks.Keys) {
        if (-not (Test-Path (Join-Path $vendorPath $dir))) {
            $toInstall += $vendorChecks[$dir]
        }
    }
    if ($toInstall.Count -gt 0) {
        Write-Host "Installing missing vendor packages: $($toInstall -join ', ')"
        Invoke-VendorPipInstall -Packages $toInstall -Upgrade
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
    --onedir `
    --clean `
    --windowed `
    --name ReplyRight `
    --icon "outlook_dashboard/static/replyright.ico" `
    --paths $vendorPath `
    --add-data "outlook_dashboard/static;outlook_dashboard/static" `
    --add-data "outlook_dashboard/build_info.json;outlook_dashboard" `
    --collect-all PySide6 `
    --collect-all outlook_dashboard `
    --collect-all replyright_qt `
    --collect-all anthropic `
    --collect-all sklearn `
    --collect-all scikit_learn `
    --collect-all dateparser `
    --collect-all joblib `
    --collect-all threadpoolctl `
    --collect-submodules win32com `
    --hidden-import PySide6.QtCore `
    --hidden-import PySide6.QtWidgets `
    --hidden-import PySide6.QtGui `
    --hidden-import pythoncom `
    --hidden-import pywintypes `
    --hidden-import win32com.client `
    --hidden-import sklearn.utils._cython_blas `
    --hidden-import sklearn.neighbors._partition_nodes `
    run_desktop.py

$exePath = (Resolve-Path "dist\ReplyRight\ReplyRight.exe").Path

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
