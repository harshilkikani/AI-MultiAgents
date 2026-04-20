# One-command demo launcher for Windows.
# Starts the FastAPI backend and the Vite frontend in separate terminals.
# Usage:  .\start-demo.ps1

$ErrorActionPreference = "Stop"

$root = $PSScriptRoot
$backend = Join-Path $root "backend"
$frontend = Join-Path $root "frontend"

Write-Host "AI Multi-Level Agent System — launcher" -ForegroundColor Cyan
Write-Host ""

# --- Backend: create venv if missing, install deps, run uvicorn in new window ---
$venvPython = Join-Path $backend ".venv\Scripts\python.exe"
if (-not (Test-Path $venvPython)) {
  Write-Host "Creating backend venv..." -ForegroundColor Yellow
  python -m venv (Join-Path $backend ".venv")
  & $venvPython -m pip install -r (Join-Path $backend "requirements.txt")
}

if (-not (Test-Path (Join-Path $backend ".env"))) {
  Copy-Item (Join-Path $backend ".env.example") (Join-Path $backend ".env")
  Write-Host "Created backend\.env (DEMO_MODE=false — edit to add ANTHROPIC_API_KEY or set DEMO_MODE=true)" -ForegroundColor Yellow
}

Write-Host "Starting backend on http://localhost:8000 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$backend'; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8000"

# --- Frontend: install deps if needed, run vite in new window ---
if (-not (Test-Path (Join-Path $frontend "node_modules"))) {
  Write-Host "Installing frontend dependencies..." -ForegroundColor Yellow
  Push-Location $frontend
  npm install
  Pop-Location
}

Write-Host "Starting frontend on http://localhost:5173 ..." -ForegroundColor Green
Start-Process powershell -ArgumentList "-NoExit", "-Command", "cd '$frontend'; npm run dev"

Write-Host ""
Write-Host "Both services launching in separate windows." -ForegroundColor Cyan
Write-Host "Open http://localhost:5173 once Vite reports 'ready'." -ForegroundColor Cyan
