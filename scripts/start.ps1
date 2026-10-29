$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Create .venv and install backend/requirements.txt first.' }
if (-not (Test-Path -LiteralPath (Join-Path $projectRoot 'frontend\dist\index.html'))) { throw 'Run npm ci and npm run build inside frontend first.' }
Push-Location $projectRoot
try {
    & $pythonPath -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000 --workers 1 --no-access-log
} finally { Pop-Location }
