$ErrorActionPreference='Stop'
$projectRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$record=Join-Path $projectRoot 'data\public\processes.json'
if(!(Test-Path -LiteralPath $record)){Write-Output 'No owned public processes recorded.';exit 0}
$owned=Get-Content -LiteralPath $record -Raw | ConvertFrom-Json
foreach($item in $owned){$p=Get-CimInstance Win32_Process -Filter "ProcessId=$($item.id)";if($p -and $item.createdAt -and $p.CreationDate.ToUniversalTime().Ticks -eq ([datetime]$item.createdAt).ToUniversalTime().Ticks -and $p.ExecutablePath -eq $item.executable -and $p.CommandLine.Contains($item.commandMarker)){Stop-Process -Id $item.id;Write-Output "Stopped owned public process $($item.id)."}elseif($p){Write-Warning "PID $($item.id) no longer matches the owned service; left running."}}
