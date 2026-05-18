param(
    [switch]$TargetLocal
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\Resolve-Python.ps1"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Resolve-ReplyRightPython

Write-Host "Using Python: $python"

if ($TargetLocal) {
    $target = Join-Path $repoRoot ".build-venv-codex-site"
    New-Item -ItemType Directory -Path $target -Force | Out-Null
    & $python -m pip install --upgrade --target $target -r (Join-Path $repoRoot "requirements-dev.txt")
} else {
    & $python -m pip install --upgrade pip
    & $python -m pip install -r (Join-Path $repoRoot "requirements-dev.txt")
}
