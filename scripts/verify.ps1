$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$pythonPath = Join-Path $projectRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonPath)) { throw 'Create this project''s .venv and install backend/requirements.txt first.' }
Push-Location $projectRoot
try {
    & $pythonPath scripts/check_dependencies.py
    if ($LASTEXITCODE -ne 0) { throw 'Python dependency check failed.' }
    & $pythonPath scripts/verify.py
    if ($LASTEXITCODE -ne 0) { throw 'Offline Python checks failed.' }
    Push-Location frontend
    try {
        & npm.cmd test
        if ($LASTEXITCODE -ne 0) { throw 'Frontend tests failed.' }
        & npm.cmd run build
        if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    } finally { Pop-Location }
} finally { Pop-Location }
