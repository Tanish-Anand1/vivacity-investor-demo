# Renew an expired quick-tunnel hostname without restarting healthy physics.
param([string]$RegisteredUrl)
$ErrorActionPreference='Stop'
$projectRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$runRoot=Join-Path $projectRoot 'data\public'
$endpointPath=Join-Path $runRoot 'endpoint.json'
$recordPath=Join-Path $runRoot 'processes.json'
$endpoint=Get-Content -LiteralPath $endpointPath -Raw | ConvertFrom-Json
$previous=@(Get-Content -LiteralPath $recordPath -Raw | ConvertFrom-Json)
$health=Invoke-RestMethod "http://127.0.0.1:$($endpoint.apiPort)/health" -TimeoutSec 5
if(!$health.backends.cloth){throw 'Local API must be healthy before rotating its tunnel.'}
$apiUrl=$RegisteredUrl
if($apiUrl -and $apiUrl -notmatch '^https://(?!api\.)[a-z0-9-]+\.trycloudflare\.com$'){throw 'RegisteredUrl must be an owned HTTPS quick-tunnel origin.'}
if(!$apiUrl){
foreach($item in $previous | Where-Object {$_.commandMarker -eq 'cloudflared'}){
  $p=Get-CimInstance Win32_Process -Filter "ProcessId=$([int]$item.id)"
  if($p -and $p.CreationDate.ToUniversalTime().Ticks -eq ([datetime]$item.createdAt).ToUniversalTime().Ticks -and $p.ExecutablePath -eq $item.executable -and $p.CommandLine.Contains($item.commandMarker)){
    Stop-Process -Id $item.id -ErrorAction SilentlyContinue
  }
}
$stamp=Get-Date -Format 'yyyyMMdd-HHmmss'
$errorLog=Join-Path $runRoot "tunnel-$stamp.error.log"
$exe=(Get-Command cloudflared -ErrorAction Stop).Source
$tunnel=Start-Process -FilePath $exe -ArgumentList @('--no-autoupdate','tunnel','--url',"http://127.0.0.1:$($endpoint.apiPort)") -WorkingDirectory $projectRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $runRoot "tunnel-$stamp.log") -RedirectStandardError $errorLog
$p=Get-CimInstance Win32_Process -Filter "ProcessId=$($tunnel.Id)"
if(!$p){throw 'New tunnel exited before registration.'}
$owned=@($previous | Where-Object {$_.commandMarker -ne 'cloudflared'})
$owned+=@{id=$p.ProcessId;executable=$p.ExecutablePath;commandMarker='cloudflared';createdAt=$p.CreationDate.ToUniversalTime().ToString('o')}
ConvertTo-Json -InputObject @($owned) | Set-Content -LiteralPath $recordPath -Encoding utf8
$apiUrl=$null
for($i=0;$i -lt 100;$i++){
  $tunnel.Refresh()
  if($tunnel.HasExited){throw 'Tunnel registration failed; inspect owned tunnel logs.'}
  if(Test-Path -LiteralPath $errorLog){
    $logText=Get-Content -LiteralPath $errorLog -Raw
    if(![string]::IsNullOrWhiteSpace($logText)){
      $match=[regex]::Match($logText,'https://(?!api\.)[a-z0-9-]+\.trycloudflare\.com')
      if($match.Success){$apiUrl=$match.Value;break}
    }
  }
  Start-Sleep -Milliseconds 500
}
if(!$apiUrl){throw 'New hostname not registered; inspect owned tunnel logs.'}
}
$ready=$false
for($i=0;$i -lt 120;$i++){
  try{$health=Invoke-RestMethod ($apiUrl+'/health') -TimeoutSec 5;if($health.backends.cloth){$ready=$true;break}}catch{}
  Start-Sleep -Milliseconds 500
}
if(!$ready){throw 'New tunnel has not passed external readiness; endpoint metadata remains unchanged.'}
$endpoint.apiUrl=$apiUrl
$endpoint | Add-Member -NotePropertyName createdAt -NotePropertyValue ((Get-Date).ToUniversalTime().ToString('o')) -Force
$endpoint | ConvertTo-Json | Set-Content -LiteralPath $endpointPath -Encoding utf8
Write-Output $apiUrl
Write-Output 'Rebuild the frontend with this VITE_API_BASE_URL and verify HTTPS/WSS.'
