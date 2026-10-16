param(
  [Parameter(Mandatory=$true)][ValidateSet('backend','frontend')][string]$Service
)
$ErrorActionPreference = 'Stop'
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
if ($Service -eq 'backend') {
  $env:VIVACITY_DATABASE = Join-Path $RepoRoot 'artifacts/factory-configurator-e2e.sqlite3'
  $env:VIVACITY_CORS_ORIGINS = 'http://127.0.0.1:5176'
  & (Join-Path $RepoRoot '.venv/Scripts/python.exe') -m uvicorn vivacity.api:app --host 127.0.0.1 --port 8002 --no-access-log
} else {
  $env:VITE_API_BASE_URL = 'http://127.0.0.1:8002'
  Push-Location (Join-Path $RepoRoot 'frontend')
  try { & (Join-Path $RepoRoot 'frontend/node_modules/.bin/vite.cmd') preview --host 127.0.0.1 --port 5176 --strictPort }
  finally { Pop-Location }
}
exit $LASTEXITCODE
