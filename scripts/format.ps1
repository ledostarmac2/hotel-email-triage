param(
    [switch]$Check
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\Resolve-Python.ps1"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Resolve-ReplyRightPython
$localTarget = Join-Path $repoRoot ".build-venv-codex-site"
if (Test-Path -LiteralPath $localTarget) {
    $env:PYTHONPATH = $localTarget
}

if ($Check) {
    & $python -m black --check outlook_dashboard replyright_kernel tests
} else {
    & $python -m black outlook_dashboard replyright_kernel tests
    & $python -m ruff check --fix outlook_dashboard replyright_kernel tests
}
