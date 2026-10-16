param([string]$FrontendOrigin='https://demo.tryvivacity.com',[int]$ApiPort=8001)
$ErrorActionPreference='Stop'
$projectRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$runRoot=Join-Path $projectRoot 'data\public'
New-Item -ItemType Directory -Path $runRoot -Force | Out-Null
$endpointFile=Join-Path $runRoot 'endpoint.json'
if(Test-Path -LiteralPath $endpointFile){
  $saved=Get-Content -LiteralPath $endpointFile -Raw | ConvertFrom-Json
  try { $health=Invoke-RestMethod ($saved.apiUrl+'/health') -TimeoutSec 10; if($health.backends.cloth){Write-Output $saved.apiUrl;exit 0} } catch {}
}
if(Get-NetTCPConnection -LocalPort $ApiPort -State Listen -ErrorAction SilentlyContinue){throw "Port $ApiPort is already in use. Inspect the owned public services before restarting."}
$uri=[uri]$FrontendOrigin
if($uri.Scheme -ne 'https' -or $uri.AbsolutePath -ne '/' -or $uri.Query -or $uri.Fragment){throw 'FrontendOrigin must be an HTTPS origin.'}
$env:VIVACITY_DATABASE=Join-Path $runRoot 'vivacity.sqlite3'
$env:VIVACITY_CORS_ORIGINS=$FrontendOrigin.TrimEnd('/')+',https://demo.tryvivacity.com,https://vivacity-investor-demo.vercel.app,http://127.0.0.1:5173,http://localhost:5173'
$env:OMP_NUM_THREADS='1';$env:OPENBLAS_NUM_THREADS='1';$env:MKL_NUM_THREADS='1'
$env:OPENAI_API_KEY=$null;$env:OPENAI_MODEL=$null
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
$owned=@()
function Record-Process([int]$processId,[string]$marker){$p=Get-CimInstance Win32_Process -Filter "ProcessId=$processId";if(!$p){throw 'Public service exited before readiness.'};return @{id=$processId;executable=$p.ExecutablePath;commandMarker=$marker;createdAt=$p.CreationDate.ToUniversalTime().ToString('o')}}
function Save-Processes {ConvertTo-Json -InputObject @($owned) | Set-Content -LiteralPath (Join-Path $runRoot 'processes.json') -Encoding utf8}
$pythonExe=Join-Path $projectRoot '.venv\Scripts\python.exe'
$process=Start-Process -FilePath $pythonExe -ArgumentList @('-m','uvicorn','vivacity.api:app','--host','127.0.0.1','--port',"$ApiPort") -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runRoot "api-$stamp.log") -RedirectStandardError (Join-Path $runRoot "api-$stamp.error.log")
$owned+=Record-Process $process.Id 'vivacity.api:app';Save-Processes
$ready=$false
for($i=0;$i -lt 60;$i++){try{$health=Invoke-RestMethod "http://127.0.0.1:$ApiPort/health" -TimeoutSec 2;if($health.backends.cloth){$ready=$true;break}}catch{};Start-Sleep -Milliseconds 500}
if(!$ready){throw 'Public API failed readiness. Inspect data/public logs.'}
$listenerId=(Get-NetTCPConnection -LocalPort $ApiPort -State Listen | Select-Object -First 1).OwningProcess
if($listenerId -ne $process.Id){$listener=Get-CimInstance Win32_Process -Filter "ProcessId=$listenerId";if($listener.ParentProcessId -ne $process.Id){throw 'Another process claimed the public API port.'};$owned+=Record-Process $listenerId 'vivacity.api:app';Save-Processes}
$tunnelExe=(Get-Command cloudflared -ErrorAction Stop).Source
$tunnelError=Join-Path $runRoot "tunnel-$stamp.error.log"
$tunnel=Start-Process -FilePath $tunnelExe -ArgumentList @('--no-autoupdate','tunnel','--url',"http://127.0.0.1:$ApiPort") -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runRoot "tunnel-$stamp.log") -RedirectStandardError $tunnelError
$owned+=Record-Process $tunnel.Id 'cloudflared';Save-Processes
$apiUrl=$null
for($i=0;$i -lt 100;$i++){
  $tunnel.Refresh()
  if($tunnel.HasExited){throw 'Tunnel registration failed; inspect data/public logs.'}
  if(Test-Path -LiteralPath $tunnelError){
    $logText=[string](Get-Content -LiteralPath $tunnelError -Raw)
    if(![string]::IsNullOrWhiteSpace($logText)){
      $match=[regex]::Match($logText,'https://(?!api\.)[a-z0-9-]+\.trycloudflare\.com')
      if($match.Success){$apiUrl=$match.Value;break}
    }
  }
  Start-Sleep -Milliseconds 500
}
if(!$apiUrl){throw 'Tunnel URL not obtained. Inspect data/public logs.'}
$externalReady=$false
for($i=0;$i -lt 20;$i++){try{$health=Invoke-RestMethod ($apiUrl+'/health') -TimeoutSec 5;if($health.backends.cloth){$externalReady=$true;break}}catch{};Start-Sleep -Milliseconds 500}
if(!$externalReady){throw 'Tunnel exists but external API readiness failed.'}
@{apiUrl=$apiUrl;frontendOrigin=$FrontendOrigin;apiPort=$ApiPort;createdAt=(Get-Date).ToUniversalTime().ToString('o');scope='Temporary tunnel to this machine; not durable hosting'} | ConvertTo-Json | Set-Content -LiteralPath $endpointFile -Encoding utf8
Write-Output $apiUrl
