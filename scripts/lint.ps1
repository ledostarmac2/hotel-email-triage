$ErrorActionPreference = "Stop"
. "$PSScriptRoot\Resolve-Python.ps1"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Resolve-ReplyRightPython
$localTarget = Join-Path $repoRoot ".build-venv-codex-site"
if (Test-Path -LiteralPath $localTarget) {
    $env:PYTHONPATH = $localTarget
}

& $python -m ruff check outlook_dashboard replyright_kernel tests
