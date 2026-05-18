$ErrorActionPreference = "Stop"
. "$PSScriptRoot\Resolve-Python.ps1"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Resolve-ReplyRightPython
$localTarget = Join-Path $repoRoot ".build-venv-codex-site"
if (Test-Path -LiteralPath $localTarget) {
    $env:PYTHONPATH = $localTarget
}

Write-Host "Using Python: $python"

& $python -m ruff check outlook_dashboard replyright_kernel tests
& $python -m black --check outlook_dashboard replyright_kernel tests
& $python -m mypy outlook_dashboard replyright_kernel
& $python -m pytest --cov=outlook_dashboard --cov=replyright_kernel --cov-report=term-missing
