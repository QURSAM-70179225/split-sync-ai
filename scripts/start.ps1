# SplitSync AI - starts backend + frontend in two windows and opens the browser.
$root = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path "$root\backend\.venv\Scripts\python.exe")) {
    Write-Host "Run setup.bat first." -ForegroundColor Red; Read-Host "Press Enter to exit"; exit 1
}
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle='SplitSync API'; cd '$root\backend'; .\.venv\Scripts\python.exe -m uvicorn main:app --reload --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", "`$host.UI.RawUI.WindowTitle='SplitSync Web'; cd '$root\frontend'; npm run dev"
Write-Host "Starting... the browser opens in a few seconds. Close the two new windows to stop." -ForegroundColor Green
Start-Sleep -Seconds 6
Start-Process "http://localhost:5173"
