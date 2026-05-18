<#
.SYNOPSIS
    ReplyRight one-command Windows setup script.
    Run this on any Windows machine to get a fully working ReplyRight install.

.USAGE
    # From PowerShell (run as standard user, no admin required):
    irm https://raw.githubusercontent.com/[OWNER]/hotel-email-triage/main/setup.ps1 | iex

    # Or if you already have the repo cloned:
    .\setup.ps1
#>

$ErrorActionPreference = "Stop"
$REPO_URL = "https://github.com/[OWNER]/hotel-email-triage.git"
$INSTALL_DIR = Join-Path $env:USERPROFILE "ReplyRight"
$PYTHON_VERSION = "3.11"

Write-Host ""
Write-Host "  ReplyRight — Setup" -ForegroundColor Cyan
Write-Host "  Waldorf Astoria New York · Reservations Intelligence" -ForegroundColor DarkGray
Write-Host ""

# ── Step 1: Check Python ──────────────────────────────────────────────────────
function Find-Python {
    $candidates = @(
        "python",
        "$env:LOCALAPPDATA\Programs\Python\Python311\python.exe",
        "$env:LOCALAPPDATA\Programs\Python\Python310\python.exe",
        "C:\Python311\python.exe"
    )
    foreach ($c in $candidates) {
        try {
            $ver = & $c --version 2>&1
            if ($ver -match "Python 3\.(1[0-9]|[2-9]\d)") { return $c }
        } catch { }
    }
    return $null
}

$python = Find-Python
if (-not $python) {
    Write-Host "Python 3.10+ not found. Downloading Python $PYTHON_VERSION installer..." -ForegroundColor Yellow
    $pyInstaller = "$env:TEMP\python-installer.exe"
    $pyUrl = "https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe"
    Invoke-WebRequest -Uri $pyUrl -OutFile $pyInstaller -UseBasicParsing
    Start-Process -FilePath $pyInstaller -ArgumentList "/quiet InstallAllUsers=0 PrependPath=1 Include_pip=1" -Wait
    Remove-Item $pyInstaller -Force -ErrorAction SilentlyContinue
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH", "User") + ";" + $env:PATH
    $python = Find-Python
    if (-not $python) { throw "Python installation failed. Please install Python 3.11 manually from python.org." }
    Write-Host "Python installed: $python" -ForegroundColor Green
} else {
    Write-Host "Python found: $python" -ForegroundColor Green
}

# ── Step 2: Clone or update repo ─────────────────────────────────────────────
if (Test-Path (Join-Path $INSTALL_DIR ".git")) {
    Write-Host "Updating existing ReplyRight repo at $INSTALL_DIR..." -ForegroundColor Cyan
    Push-Location $INSTALL_DIR
    git pull --ff-only
    Pop-Location
} elseif (Test-Path $INSTALL_DIR) {
    Write-Host "Directory $INSTALL_DIR exists but is not a git repo. Using it as-is." -ForegroundColor Yellow
    Push-Location $INSTALL_DIR
} else {
    Write-Host "Cloning ReplyRight to $INSTALL_DIR..." -ForegroundColor Cyan
    git clone $REPO_URL $INSTALL_DIR
    Push-Location $INSTALL_DIR
}

Set-Location $INSTALL_DIR

# ── Step 3: Virtual environment ───────────────────────────────────────────────
$venvPython = Join-Path $INSTALL_DIR ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    & $python -m venv .venv
}
Write-Host "Installing/updating dependencies..." -ForegroundColor Cyan
& .venv\Scripts\pip install --quiet --upgrade pip
& .venv\Scripts\pip install --quiet -r requirements.txt

# ── Step 4: Build EXE ─────────────────────────────────────────────────────────
Write-Host "Building ReplyRight.exe..." -ForegroundColor Cyan
& .venv\Scripts\pip install --quiet pyinstaller==6.20.0
.\build_exe.ps1

$exePath = Join-Path $INSTALL_DIR "dist\ReplyRight.exe"
if (-not (Test-Path $exePath)) {
    throw "Build failed — dist\ReplyRight.exe not found."
}

# ── Step 5: Shortcuts ─────────────────────────────────────────────────────────
$shell = New-Object -ComObject WScript.Shell
foreach ($shortcutPath in @(
    (Join-Path ([Environment]::GetFolderPath("DesktopDirectory")) "ReplyRight.lnk"),
    (Join-Path ([Environment]::GetFolderPath("Programs")) "ReplyRight.lnk")
)) {
    try {
        $sc = $shell.CreateShortcut($shortcutPath)
        $sc.TargetPath = $exePath
        $sc.WorkingDirectory = Split-Path $exePath
        $sc.IconLocation = "$exePath,0"
        $sc.Description = "ReplyRight — Waldorf Astoria Reservations Intelligence"
        $sc.Save()
        Write-Host "Shortcut created: $shortcutPath" -ForegroundColor Green
    } catch {
        Write-Warning "Could not create shortcut at $shortcutPath`: $_"
    }
}

Write-Host ""
Write-Host "  Setup complete!" -ForegroundColor Green
Write-Host "  Launch ReplyRight from your Desktop shortcut or run:" -ForegroundColor Cyan
Write-Host "  $exePath" -ForegroundColor White
Write-Host ""

# Offer to launch immediately
$launch = Read-Host "Launch ReplyRight now? [Y/n]"
if ($launch -ne "n" -and $launch -ne "N") {
    Start-Process $exePath
}
