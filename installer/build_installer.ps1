$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$issPath = Join-Path $PSScriptRoot "replyright_setup.iss"

function Test-RequiredPath {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Description
    )

    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Required installer input missing: $Description ($Path)"
    }
}

Test-RequiredPath -Path $issPath -Description "Inno Setup script"
Test-RequiredPath -Path (Join-Path $PSScriptRoot "sample.env") -Description "safe sample env template"
Test-RequiredPath -Path (Join-Path $repoRoot "outlook_dashboard\__init__.py") -Description "runtime version module"
Test-RequiredPath -Path (Join-Path $repoRoot "outlook_dashboard\static\replyright.ico") -Description "installer icon"

function Find-Iscc {
    $cmd = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $candidates = @(
        "$env:ProgramFiles(x86)\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe"
    )
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate)) {
            return $candidate
        }
    }
    return $null
}

function Install-InnoSetup {
    # Try winget first (works on modern Windows desktops).
    $winget = Get-Command "winget.exe" -ErrorAction SilentlyContinue
    if ($winget) {
        try {
            $null = & $winget.Source install --id JRSoftware.InnoSetup --exact --silent --accept-package-agreements --accept-source-agreements 2>&1
            $found = Find-Iscc
            if ($found) { return $found }
        } catch {
            Write-Warning "winget Inno Setup install failed: $($_.Exception.Message)"
        }
    }

    # Try Chocolatey second (reliable on GitHub Actions windows-latest runners).
    $choco = Get-Command "choco.exe" -ErrorAction SilentlyContinue
    if ($choco) {
        try {
            $null = & $choco.Source install innosetup -y --no-progress 2>&1
            $found = Find-Iscc
            if ($found) { return $found }
        } catch {
            Write-Warning "Chocolatey Inno Setup install failed: $($_.Exception.Message)"
        }
    }

    # Fall back to downloading the bootstrapper directly.
    $installerPath = Join-Path $env:TEMP "innosetup.exe"
    $url = "https://jrsoftware.org/download.php/is.exe"
    Invoke-WebRequest -Uri $url -OutFile $installerPath
    Start-Process -FilePath $installerPath -ArgumentList "/VERYSILENT", "/NORESTART", "/CURRENTUSER" -Wait -WindowStyle Hidden

    $found = Find-Iscc
    if (-not $found) {
        throw "Inno Setup Compiler (ISCC.exe) was not found after installation."
    }
    return $found
}

$appExe = Join-Path $repoRoot "dist\ReplyRight\ReplyRight.exe"
if (-not (Test-Path -LiteralPath $appExe)) {
    throw "dist\ReplyRight\ReplyRight.exe was not found. Run .\build_exe.ps1 first."
}

$appDir = Join-Path $repoRoot "dist\ReplyRight"
$runtimeEnvFiles = Get-ChildItem -LiteralPath $appDir -Recurse -Force -File -ErrorAction SilentlyContinue |
    Where-Object { ($_.Name -eq ".env" -or $_.Name -like "*.env") -and $_.Name -ne "sample.env" }
foreach ($envFile in $runtimeEnvFiles) {
    Write-Host "Removing runtime env file from installer payload: $($envFile.FullName)"
    Remove-Item -LiteralPath $envFile.FullName -Force
}

# Read version from __init__.py so the installer name stays in sync with the code.
$initPath = Join-Path $repoRoot "outlook_dashboard\__init__.py"
$initContent = Get-Content $initPath -Raw -ErrorAction Stop
if ($initContent -notmatch '__version__\s*=\s*"(\d+\.\d+\.\d+[^"]*)"') {
    throw "Could not read __version__ from $initPath. Expected: __version__ = `"x.y.z`""
}
$appVersion = $Matches[1]
Write-Host "App version: $appVersion"

$iscc = Find-Iscc
if (-not $iscc) {
    Write-Host "Inno Setup Compiler not found. Installing Inno Setup..."
    $iscc = Install-InnoSetup
}

Write-Host "Using ISCC: $iscc"
& $iscc /DMyAppVersion=$appVersion $issPath
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE"
}

$output = Get-ChildItem (Join-Path $PSScriptRoot "output") -Filter "ReplyRightSetup-v*.exe" -ErrorAction SilentlyContinue |
    Sort-Object LastWriteTime -Descending |
    Select-Object -First 1
if ($output) {
    Write-Host "Built installer: $($output.FullName)"
} else {
    throw "ReplyRight installer was not created."
}
