param(
    [switch]$Watch,
    [switch]$Coverage
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\Resolve-Python.ps1"

$repoRoot = Split-Path -Parent $PSScriptRoot
$python = Resolve-ReplyRightPython
$localTarget = Join-Path $repoRoot ".build-venv-codex-site"
if (Test-Path -LiteralPath $localTarget) {
    $env:PYTHONPATH = $localTarget
}

$pytestArgs = @("-m", "pytest")
if ($Coverage) {
    $pytestArgs += @("--cov=outlook_dashboard", "--cov=replyright_kernel", "--cov-report=term-missing")
}
if ($Watch) {
    Write-Host "pytest-watch is not required for ReplyRight. Re-running once with pytest."
}

& $python @pytestArgs
