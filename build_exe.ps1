$ErrorActionPreference = "Stop"

if (-not (Test-Path ".venv")) {
    python -m venv .venv
}

.\.venv\Scripts\python.exe -m pip install --upgrade pip
.\.venv\Scripts\python.exe -m pip install -r requirements.txt

.\.venv\Scripts\pyinstaller.exe `
    --onefile `
    --name HotelEmailIntelligence `
    --add-data "outlook_dashboard/static;outlook_dashboard/static" `
    run_desktop.py

Write-Host "Built dist\HotelEmailIntelligence.exe"
