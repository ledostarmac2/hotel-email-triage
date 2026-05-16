from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path

# Allow up to 3 minutes for the macro to scan the inbox, build JSON, and POST
# back to the import endpoint.  30 s was too short for large inboxes because
# Application.Run is synchronous — PowerShell waits for the entire VBA macro
# to finish before returning.
_MACRO_TIMEOUT_SECONDS = 180


class OutlookDesktopExportError(RuntimeError):
    pass


def export_mailbox_folder_to_msg(
    mailbox_name: str,
    folder_name: str,
    export_root: Path,
    macro_name: str,
) -> dict[str, object]:
    export_root.mkdir(parents=True, exist_ok=True)
    return _run_outlook_macro(macro_name)


def _run_outlook_macro(macro_name: str) -> dict[str, object]:
    if not macro_name:
        raise OutlookDesktopExportError("Outlook macro name is not configured.")

    macro_json = json.dumps(macro_name)

    # The script does a thorough search for a running Outlook process first.
    # If found: connects via COM and runs the macro on the existing instance
    #   so no duplicate Outlook window is opened.
    # If not found: discovers the outlook.exe path from the registry (three
    #   locations checked) and starts it with /autorun to trigger the macro.
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        f"$macroName = {macro_json}\n"
        r'''
# ── Step 1: thorough search for a running Outlook process ────────────────────
# Check both "OUTLOOK" and "outlook" (case-insensitive on Windows).
$outlookProc = Get-Process -Name "OUTLOOK" -ErrorAction SilentlyContinue
if (-not $outlookProc) {
    $outlookProc = Get-Process | Where-Object { $_.Name -imatch '^outlook$' } | Select-Object -First 1
}

if ($outlookProc) {
    # ── Outlook is already open — run macro via VBScript (true IDispatch / late-binding) ──
    # PowerShell wraps the COM object as ApplicationClass which doesn't expose Run().
    # VBScript's GetObject() uses pure IDispatch and Application.Run works correctly.
    Write-Output "Outlook is running (PID $($outlookProc.Id)). Triggering macro via VBScript..."
    $vbsContent = "Set ol = GetObject(,""Outlook.Application"")`nol.Run ""$macroName"""
    $vbsPath = [System.IO.Path]::GetTempFileName() -replace '\.tmp$','.vbs'
    try {
        Set-Content -Path $vbsPath -Value $vbsContent -Encoding ASCII
        $vbsResult = & cscript.exe //NoLogo $vbsPath 2>&1
        if ($LASTEXITCODE -ne 0) {
            $errMsg = ($vbsResult | Out-String).Trim()
            $hint1 = "  1. Macro security may be blocking it: Outlook > File > Options > Trust Center > Macro Settings > enable macros."
            $hint2 = "  2. The macro may not be installed: open Outlook VBA editor (Alt+F11) and import outlook_refresh_macro.bas."
            $hint3 = "  3. If the macro is in a named module, set OUTLOOK_EXPORT_MACRO=Module1.ExportNYCWAReservationsInboxOnly in .env."
            throw "VBScript macro call failed (exit $LASTEXITCODE): $errMsg`n$hint1`n$hint2`n$hint3"
        }
        Write-Output "Macro '$($macroName)' triggered on existing Outlook instance."
    } finally {
        Remove-Item $vbsPath -Force -ErrorAction SilentlyContinue
    }
} else {
    # ── Outlook is not running — find it and start it with /autorun ──────────
    Write-Output "No running Outlook found. Searching for outlook.exe..."

    $outlookExe = $null

    # Registry search — three locations covering Click-to-Run and MSI installs
    $regPaths = @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\OUTLOOK.EXE",
        "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths\OUTLOOK.EXE",
        "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\App Paths\OUTLOOK.EXE"
    )
    foreach ($rp in $regPaths) {
        if (-not $outlookExe) {
            $entry = Get-ItemProperty -Path $rp -ErrorAction SilentlyContinue
            if ($entry -and $entry.'(default)') {
                $outlookExe = $entry.'(default)'
            }
        }
    }

    # PATH fallback
    if (-not $outlookExe) {
        $cmd = Get-Command "OUTLOOK.EXE" -ErrorAction SilentlyContinue
        if ($cmd) { $outlookExe = $cmd.Source }
    }

    # Hard-coded Office install paths as a last resort
    if (-not $outlookExe) {
        $candidateDirs = @(
            "$env:ProgramFiles\Microsoft Office\root\Office16",
            "$env:ProgramFiles\Microsoft Office\root\Office15",
            "${env:ProgramFiles(x86)}\Microsoft Office\root\Office16",
            "${env:ProgramFiles(x86)}\Microsoft Office\Office16",
            "${env:ProgramFiles(x86)}\Microsoft Office\Office15"
        )
        foreach ($d in $candidateDirs) {
            $candidate = Join-Path $d "OUTLOOK.EXE"
            if (-not $outlookExe -and (Test-Path $candidate)) {
                $outlookExe = $candidate
            }
        }
    }

    if (-not $outlookExe) {
        throw "Could not locate outlook.exe. Please ensure Microsoft Outlook is installed."
    }

    Write-Output "Found outlook.exe: $outlookExe"
    Start-Process -FilePath $outlookExe -ArgumentList "/autorun", $macroName
    Write-Output "Outlook started with macro: $($macroName)"
}
'''
    )

    encoded = base64.b64encode(script.encode("utf-16le")).decode("ascii")
    try:
        completed = subprocess.run(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                encoded,
            ],
            capture_output=True,
            text=True,
            timeout=_MACRO_TIMEOUT_SECONDS,
            check=False,
        )
    except subprocess.TimeoutExpired:
        raise OutlookDesktopExportError(
            f"The Outlook macro did not complete within {_MACRO_TIMEOUT_SECONDS} seconds. "
            "This can happen with a very large inbox. "
            "Try again — if it keeps timing out, reduce the inbox size or increase _MACRO_TIMEOUT_SECONDS."
        )

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "Could not run Outlook macro.").strip()
        raise OutlookDesktopExportError(detail)

    return {
        "mailbox": None,
        "folder": None,
        "export_dir": None,
        "checked_count": None,
        "exported_count": None,
        "skipped_count": None,
        "launched_macro": True,
        "macro": macro_name,
        "stdout": (completed.stdout or "").strip(),
    }
