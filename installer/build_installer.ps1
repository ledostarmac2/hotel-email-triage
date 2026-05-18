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
    $winget = Get-Command "winget.exe" -ErrorAction SilentlyContinue
    if ($winget) {
        try {
            & $winget.Source install --id JRSoftware.InnoSetup --exact --silent --accept-package-agreements --accept-source-agreements
            $found = Find-Iscc
            if ($found) { return $found }
        } catch {
            Write-Warning "winget Inno Setup install failed: $($_.Exception.Message)"
        }
    }

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

if (-not (Test-Path -LiteralPath (Join-Path $repoRoot "dist\ReplyRight.exe"))) {
    throw "dist\ReplyRight.exe was not found. Run .\build_exe.ps1 first."
}

$iscc = Find-Iscc
if (-not $iscc) {
    Write-Host "Inno Setup Compiler not found. Installing Inno Setup..."
    $iscc = Install-InnoSetup
}

Write-Host "Using ISCC: $iscc"
& $iscc $issPath
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
