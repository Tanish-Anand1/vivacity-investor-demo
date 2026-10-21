param()
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$audio=Join-Path $repo 'artifacts/isabella-cinema-audio.wav'
$output=Join-Path $repo 'frontend/public/vivacity'
$grade='eq=contrast=1.08:brightness=-0.025:saturation=0.88,vignette=PI/6,fade=t=in:st=0:d=0.45'
if(-not (Test-Path -LiteralPath $audio)){throw "Missing authored soundtrack: $audio"}
foreach($format in @('landscape','portrait')){
 $frames=Join-Path $repo "artifacts/isabella-cinema-film-$format/%04d.jpg"
 if(-not (Test-Path -LiteralPath (Join-Path $repo "artifacts/isabella-cinema-film-$format/0000.jpg"))){throw "Missing rendered frames: $format"}
 $high=Join-Path $output "isabella-impossible-$format.mp4"
 $lite=Join-Path $output "isabella-impossible-$format-lite.mp4"
 $crf=if($format -eq 'landscape'){19}else{20}
 & ffmpeg -hide_banner -loglevel error -framerate 60 -i $frames -i $audio -vf $grade -c:v libx264 -preset medium -crf $crf -pix_fmt yuv420p -r 60 -c:a aac -b:a 128k -t 7.5 -movflags +faststart -y $high
 if($LASTEXITCODE -ne 0){throw "High-quality encode failed: $format"}
 $size=if($format -eq 'landscape'){'960:540'}else{'540:960'}
 & ffmpeg -hide_banner -loglevel error -i $high -vf "scale=${size}:flags=lanczos" -r 30 -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p -c:a copy -t 7.5 -movflags +faststart -y $lite
 if($LASTEXITCODE -ne 0){throw "Lightweight encode failed: $format"}
}
Get-Item (Join-Path $output 'isabella-impossible-*.mp4') | Select-Object Name,Length
