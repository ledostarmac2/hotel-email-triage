$ErrorActionPreference = "Stop"

$vendorPath = Join-Path (Get-Location) ".vendor"

if (-not (Test-Path $vendorPath)) {
    $env:TEMP = Join-Path (Get-Location) ".build-tmp"
    $env:TMP = $env:TEMP
    $env:PYTHONPATH = (Resolve-Path "build_support").Path
    New-Item -ItemType Directory -Force -Path $env:TEMP | Out-Null
    New-Item -ItemType Directory -Force -Path $vendorPath | Out-Null
    python -m pip install --no-cache-dir --only-binary=:all: --target $vendorPath fastapi "uvicorn[standard]" httpx python-dotenv openai
}

python -m PyInstaller `
    --onefile `
    --windowed `
    --name ReplyRight `
    --icon "outlook_dashboard/static/replyright.ico" `
    --paths $vendorPath `
    --add-data "outlook_dashboard/static;outlook_dashboard/static" `
    run_desktop.py

$exePath = (Resolve-Path "dist\ReplyRight.exe").Path

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
