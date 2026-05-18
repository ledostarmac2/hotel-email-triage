param(
    [string]$Model = "gemini-3-flash-preview"
)

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir
$EnvPath = Join-Path $RepoRoot ".env"
$ExamplePath = Join-Path $RepoRoot ".env.example"

if (-not (Test-Path -LiteralPath $EnvPath)) {
    if (Test-Path -LiteralPath $ExamplePath) {
        Copy-Item -LiteralPath $ExamplePath -Destination $EnvPath
    } else {
        New-Item -ItemType File -Path $EnvPath | Out-Null
    }
}

function Set-EnvValue {
    param(
        [string]$Path,
        [string]$Name,
        [string]$Value
    )

    $escapedName = [regex]::Escape($Name)
    $line = "$Name=$Value"
    $lines = @()
    if (Test-Path -LiteralPath $Path) {
        $lines = @(Get-Content -LiteralPath $Path)
    }

    $updated = $false
    $next = foreach ($existing in $lines) {
        if ($existing -match "^$escapedName=") {
            $updated = $true
            $line
        } else {
            $existing
        }
    }

    if (-not $updated) {
        $next += $line
    }

    Set-Content -LiteralPath $Path -Value $next -Encoding UTF8
}

$secureKey = Read-Host "Paste your NEW Google AI Studio API key" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $plainKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr).Trim()
} finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

if (-not $plainKey) {
    throw "No Google AI Studio API key was provided."
}

Set-EnvValue -Path $EnvPath -Name "GOOGLE_AI_API_KEY" -Value $plainKey
Set-EnvValue -Path $EnvPath -Name "GOOGLE_AI_MODEL" -Value $Model

Write-Host "Google AI Studio is configured in .env for ReplyRight."
Write-Host "The key was not printed and .env is ignored by git."
Write-Host "Restart ReplyRight, then check /api/health for google_ai_configured=true."
