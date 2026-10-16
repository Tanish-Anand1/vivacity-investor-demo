param([switch]$Dev, [switch]$NoBrowser)
$ErrorActionPreference='Stop'
$projectRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$pythonExe=Join-Path $projectRoot '.venv\Scripts\python.exe'
$frontendRoot=Join-Path $projectRoot 'frontend'
if (!(Test-Path -LiteralPath $pythonExe)) { throw 'Install the Python environment first: see README.md.' }
$nodeExe=(Get-Command node -ErrorAction Stop).Source
$viteCli=Join-Path $frontendRoot 'node_modules\vite\bin\vite.js'
if (!(Test-Path -LiteralPath $viteCli)) { throw 'Run npm ci from frontend first.' }
if (!$Dev -and !(Test-Path -LiteralPath (Join-Path $frontendRoot 'dist\index.html'))) { throw 'Run npm run build from frontend first.' }
$runRoot=Join-Path $projectRoot 'data\run'
New-Item -ItemType Directory -Path $runRoot -Force | Out-Null
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
$env:OMP_NUM_THREADS='1';$env:OPENBLAS_NUM_THREADS='1';$env:MKL_NUM_THREADS='1'
$owned=@()
function Record-Process([int]$processId,[string]$marker) {
  $info=Get-CimInstance Win32_Process -Filter "ProcessId=$processId"
  if(!$info){throw "Started process $processId exited before readiness."}
  return @{id=$processId;executable=$info.ExecutablePath;commandMarker=$marker;createdAt=$info.CreationDate.ToUniversalTime().ToString('o')}
}
function Wait-Endpoint([string]$url) {
  for($i=0;$i -lt 60;$i++){
    try { return Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 2 } catch { Start-Sleep -Milliseconds 500 }
  }
  throw "Service did not become ready: $url. Inspect logs under $runRoot."
}
try {
  $backend=$null
  try { $backend=Invoke-RestMethod 'http://127.0.0.1:8000/health' -TimeoutSec 2 } catch {}
  if($backend){
    if(!$backend.backends.mujoco -or !$backend.backends.scipy){throw 'Port 8000 belongs to another service.'}
  } else {
    $process=Start-Process -FilePath $pythonExe -ArgumentList @('-m','uvicorn','vivacity.api:app','--host','127.0.0.1','--port','8000') -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runRoot "backend-$stamp.log") -RedirectStandardError (Join-Path $runRoot "backend-$stamp.error.log")
    $owned+=Record-Process $process.Id 'vivacity.api:app'
    Wait-Endpoint 'http://127.0.0.1:8000/health' | Out-Null
    $listenerId=(Get-NetTCPConnection -LocalPort 8000 -State Listen | Select-Object -First 1).OwningProcess
    if($listenerId -ne $process.Id){
      # The Windows venv redirector may start the real interpreter as a child.
      $listener=Get-CimInstance Win32_Process -Filter "ProcessId=$listenerId"
      if($listener.ParentProcessId -ne $process.Id){throw 'Port 8000 was claimed by a different process.'}
      $owned+=Record-Process $listenerId 'vivacity.api:app'
    }
  }
  $frontend=$null
  try { $frontend=Invoke-WebRequest 'http://127.0.0.1:5173/' -UseBasicParsing -TimeoutSec 2 } catch {}
  if($frontend){
    if($frontend.Content -notmatch 'Vivacity'){throw 'Port 5173 belongs to another service.'}
  } else {
    $mode=if($Dev){'dev'}else{'preview'}
    $process=Start-Process -FilePath $nodeExe -ArgumentList @(('"'+$viteCli+'"'),$mode,'--host','127.0.0.1','--port','5173','--strictPort') -WorkingDirectory $frontendRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runRoot "frontend-$stamp.log") -RedirectStandardError (Join-Path $runRoot "frontend-$stamp.error.log")
    $owned+=Record-Process $process.Id $viteCli
    Wait-Endpoint 'http://127.0.0.1:5173/' | Out-Null
  }
  if($owned.Count){ConvertTo-Json -InputObject @($owned) | Set-Content -LiteralPath (Join-Path $runRoot 'demo-processes.json') -Encoding utf8}
  Write-Output 'Vivacity is ready: http://127.0.0.1:5173  |  API: http://127.0.0.1:8000/docs'
  Write-Output 'Existing services are reused. Stop only processes launched by this script with scripts/stop-demo.ps1.'
  if(!$NoBrowser){Start-Process 'http://127.0.0.1:5173'}
} catch {
  foreach($item in $owned){Stop-Process -Id $item.id -ErrorAction SilentlyContinue}
  throw
}
