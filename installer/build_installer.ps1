$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$issPath = Join-Path $PSScriptRoot "replyright_setup.iss"

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

# Read version from __init__.py so the installer name stays in sync with the code.
$initContent = Get-Content (Join-Path $repoRoot "outlook_dashboard\__init__.py") -Raw -ErrorAction SilentlyContinue
$appVersion = if ($initContent -match '"(\d+\.\d+\.\d+[^"]*)"') { $Matches[1] } else { "0.1.1" }
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
