# Restart only the owned API; keep the verified tunnel URL unchanged.
$ErrorActionPreference='Stop'
$projectRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$runRoot=Join-Path $projectRoot 'data\public'
$endpoint=Get-Content -LiteralPath (Join-Path $runRoot 'endpoint.json') -Raw | ConvertFrom-Json
$record=Join-Path $runRoot 'processes.json'
$previous=Get-Content -LiteralPath $record -Raw | ConvertFrom-Json
foreach($item in $previous | Where-Object {$_.commandMarker -eq 'vivacity.api:app'}){
  $p=Get-CimInstance Win32_Process -Filter "ProcessId=$([int]$item.id)"
  if($p -and $p.CreationDate.ToUniversalTime().Ticks -eq ([datetime]$item.createdAt).ToUniversalTime().Ticks -and $p.ExecutablePath -eq $item.executable -and $p.CommandLine.Contains($item.commandMarker)){Stop-Process -Id $item.id -ErrorAction SilentlyContinue}
}
$port=[int]$endpoint.apiPort
for($i=0;$i -lt 20;$i++){if(!(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue)){break};Start-Sleep -Milliseconds 250}
if(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue){throw 'Public port remains occupied; no unrelated process was stopped.'}
$env:VIVACITY_DATABASE=Join-Path $runRoot 'vivacity.sqlite3'
$env:VIVACITY_CORS_ORIGINS=$endpoint.frontendOrigin.TrimEnd('/')+',https://demo.tryvivacity.com,https://vivacity-investor-demo.vercel.app,http://127.0.0.1:5173,http://localhost:5173'
$env:OMP_NUM_THREADS='1';$env:OPENBLAS_NUM_THREADS='1';$env:MKL_NUM_THREADS='1'
$env:OPENAI_API_KEY=$null;$env:OPENAI_MODEL=$null
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
$pythonExe=Join-Path $projectRoot '.venv\Scripts\python.exe'
$process=Start-Process -FilePath $pythonExe -ArgumentList @('-m','uvicorn','vivacity.api:app','--host','127.0.0.1','--port',"$port") -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runRoot "api-$stamp.log") -RedirectStandardError (Join-Path $runRoot "api-$stamp.error.log")
$owned=@($previous | Where-Object {$_.commandMarker -ne 'vivacity.api:app'})
function Record-Process([int]$processId){$p=Get-CimInstance Win32_Process -Filter "ProcessId=$processId";if(!$p){throw 'API exited.'};return @{id=$processId;executable=$p.ExecutablePath;commandMarker='vivacity.api:app';createdAt=$p.CreationDate.ToUniversalTime().ToString('o')}}
$owned+=Record-Process $process.Id
ConvertTo-Json -InputObject @($owned) | Set-Content -LiteralPath $record -Encoding utf8
$ready=$false
for($i=0;$i -lt 60;$i++){try{$h=Invoke-RestMethod "http://127.0.0.1:$port/health" -TimeoutSec 2;if($h.backends.cloth){$ready=$true;break}}catch{};Start-Sleep -Milliseconds 500}
if(!$ready){throw 'Restarted API failed readiness.'}
$listenerId=(Get-NetTCPConnection -LocalPort $port -State Listen | Select-Object -First 1).OwningProcess
if($listenerId -ne $process.Id){$listener=Get-CimInstance Win32_Process -Filter "ProcessId=$listenerId";if($listener.ParentProcessId -ne $process.Id){throw 'Public listener identity mismatch.'};$owned+=Record-Process $listenerId}
ConvertTo-Json -InputObject @($owned) | Set-Content -LiteralPath $record -Encoding utf8
$h=Invoke-RestMethod ($endpoint.apiUrl+'/health') -TimeoutSec 15
if(!$h.backends.cloth){throw 'External tunnel readiness failed.'}
Write-Output $endpoint.apiUrl
