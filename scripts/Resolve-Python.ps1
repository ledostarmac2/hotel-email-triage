function Test-ReplyRightPython {
    param([string]$PythonPath)

    if (-not $PythonPath) { return $false }
    try {
        & $PythonPath --version *> $null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Resolve-ReplyRightPython {
    $repoRoot = Split-Path -Parent $PSScriptRoot
    $candidates = @()

    $localVenv = Join-Path $repoRoot ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $localVenv) {
        $candidates += $localVenv
    }

    foreach ($commandName in @("python", "py")) {
        $command = Get-Command $commandName -ErrorAction SilentlyContinue
        if ($command -and $command.Source) {
            $candidates += $command.Source
        }
    }

    foreach ($root in @("HKCU:\Software\Python\PythonCore", "HKLM:\Software\Python\PythonCore")) {
        if (-not (Test-Path -LiteralPath $root)) { continue }
        Get-ChildItem -LiteralPath $root -ErrorAction SilentlyContinue | ForEach-Object {
            $installPath = Join-Path $_.PsPath "InstallPath"
            try {
                $value = (Get-ItemProperty -LiteralPath $installPath -ErrorAction Stop)."(default)"
                if ($value) {
                    $candidates += (Join-Path $value "python.exe")
                }
            } catch {
            }
        }
    }

    $windowsApps = Join-Path $env:ProgramFiles "WindowsApps"
    if (Test-Path -LiteralPath $windowsApps) {
        Get-ChildItem -LiteralPath $windowsApps -Filter "PythonSoftwareFoundation.Python.3.*" -Directory -ErrorAction SilentlyContinue |
            Sort-Object Name -Descending |
            ForEach-Object {
                $candidates += (Join-Path $_.FullName "python3.12.exe")
                $candidates += (Join-Path $_.FullName "python3.11.exe")
                $candidates += (Join-Path $_.FullName "python.exe")
            }
    }

    foreach ($candidate in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
        if (Test-ReplyRightPython $candidate) {
            return $candidate
        }
    }

    throw "No working Python interpreter found. Install Python 3.11+ or repair .venv."
}
