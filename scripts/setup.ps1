# SplitSync AI - one-time setup for Windows. Run via setup.bat (double-click).
$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root

function Find-Python {
    foreach ($v in @("3.13", "3.12", "3.11")) {
        try { $p = & py "-$v" -c "import sys;print(sys.executable)" 2>$null; if ($LASTEXITCODE -eq 0 -and $p) { return $p.Trim() } } catch {}
    }
    foreach ($cmd in @("python", "py")) {
        try { $p = & $cmd -c "import sys;print(sys.executable)" 2>$null; if ($LASTEXITCODE -eq 0 -and $p -and $p -notmatch "WindowsApps") { return $p.Trim() } } catch {}
    }
    $found = Get-ChildItem "$env:LOCALAPPDATA\Programs\Python", "$env:LOCALAPPDATA\Python" -Recurse -Filter python.exe -ErrorAction SilentlyContinue |
        Where-Object { $_.FullName -notmatch "\\(venv|\.venv|Lib|Scripts)\\" -and $_.FullName -notmatch "\\bin\\" } |
        Sort-Object FullName | Select-Object -First 1
    if ($found) { return $found.FullName }
    return $null
}

Write-Host "`n=== SplitSync AI setup ===`n" -ForegroundColor Cyan

$python = Find-Python
if (-not $python) {
    Write-Host "Python not found. Install Python 3.12 or 3.13 from https://www.python.org/downloads/ (tick 'Add python.exe to PATH')." -ForegroundColor Red
    exit 1
}
Write-Host "Python: $python"

if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host "Node.js not found. Install the LTS version from https://nodejs.org, then re-run setup.bat." -ForegroundColor Red
    exit 1
}
Write-Host "Node:   $(node --version)"

Write-Host "`n[1/3] Backend: virtual environment + packages..." -ForegroundColor Yellow
Set-Location "$root\backend"
if (-not (Test-Path ".venv\Scripts\python.exe")) { & $python -m venv .venv }
& ".venv\Scripts\python.exe" -m pip install --upgrade pip -q
& ".venv\Scripts\python.exe" -m pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) {
    Write-Host "`npip install failed. If the error mentions Rust/cargo/wheel, your Python is too new: install Python 3.13, delete backend\.venv and run setup.bat again." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env"; Write-Host "Created backend\.env (works without keys - demo mode)." }

Write-Host "`n[2/3] Frontend: npm install..." -ForegroundColor Yellow
Set-Location "$root\frontend"
npm install
if ($LASTEXITCODE -ne 0) { Write-Host "npm install failed." -ForegroundColor Red; exit 1 }

Write-Host "`n[3/3] Done! Double-click start.bat to launch SplitSync AI." -ForegroundColor Green
