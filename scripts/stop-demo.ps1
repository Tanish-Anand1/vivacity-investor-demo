$ErrorActionPreference='Stop'
$projectRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$record=Join-Path $projectRoot 'data\run\demo-processes.json'
if(!(Test-Path -LiteralPath $record)){Write-Output 'No owned demo processes recorded.';exit 0}
$owned=Get-Content -LiteralPath $record -Raw | ConvertFrom-Json
foreach($item in $owned){
  $process=Get-CimInstance Win32_Process -Filter "ProcessId=$($item.id)"
  if($process -and $item.createdAt -and $process.CreationDate.ToUniversalTime().Ticks -eq ([datetime]$item.createdAt).ToUniversalTime().Ticks -and $process.ExecutablePath -eq $item.executable -and $process.CommandLine.Contains($item.commandMarker)){
    Stop-Process -Id $item.id -ErrorAction SilentlyContinue
    Write-Output "Stopped demo process $($item.id)."
  }elseif($process){Write-Warning "PID $($item.id) does not match the recorded demo command; left running."}
}
