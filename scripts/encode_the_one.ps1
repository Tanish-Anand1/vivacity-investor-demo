param(
 [ValidateSet('landscape','portrait','both')]
 [string]$Format='both'
)
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$audio=Join-Path $repo 'artifacts/the-one-audio.wav'
$output=Join-Path $repo 'frontend/public/vivacity'
if(-not (Get-Command ffmpeg -ErrorAction SilentlyContinue)){throw 'ffmpeg must be available on PATH.'}
if(-not (Get-Command ffprobe -ErrorAction SilentlyContinue)){throw 'ffprobe must be available on PATH.'}
if(-not (Test-Path -LiteralPath $audio)){throw "Missing authored soundtrack: $audio"}
$formats=if($Format -eq 'both'){@('landscape','portrait')}else{@($Format)}
New-Item -ItemType Directory -Path $output -Force | Out-Null

function Assert-Film([string]$Path,[int]$ExpectedFrames,[int]$ExpectedRate){
 $raw=& ffprobe -v error -select_streams v:0 -show_entries stream=nb_frames,r_frame_rate,duration,width,height -of json $Path
 if($LASTEXITCODE -ne 0){throw "ffprobe failed: $Path"}
 $video=($raw -join "`n" | ConvertFrom-Json).streams[0]
 if([int]$video.nb_frames -ne $ExpectedFrames){throw "Unexpected frame count in ${Path}: $($video.nb_frames)"}
 if($video.r_frame_rate -ne "$ExpectedRate/1"){throw "Unexpected frame rate in ${Path}: $($video.r_frame_rate)"}
 if([Math]::Abs([double]$video.duration-7.5) -gt 0.001){throw "Unexpected duration in ${Path}: $($video.duration)"}
}

foreach($aspect in $formats){
 $frameDirectory=Join-Path $repo "artifacts/the-one-film-$aspect"
 # Validate every frame before writing either deliverable. An interrupted
 # render must not silently produce a shorter opening or repeat stale frames.
 foreach($index in 0..449){
  $frame=Join-Path $frameDirectory ('{0:D4}.jpg' -f $index)
  if(-not (Test-Path -LiteralPath $frame)){throw "Missing rendered frame: $frame"}
 }
 $frames=Join-Path $frameDirectory '%04d.jpg'
 $high=Join-Path $output "the-one-isabella-$aspect.mp4"
 $lite=Join-Path $output "the-one-isabella-$aspect-lite.mp4"
 $crf=if($aspect -eq 'landscape'){19}else{20}
 # The renderer owns exposure, materials and the grade. Preserve its light;
 # no darkening, contrast filter, vignette or artificial fade is added here.
 & ffmpeg -hide_banner -loglevel error -framerate 60 -start_number 0 -i $frames -i $audio -frames:v 450 -c:v libx264 -preset medium -crf $crf -pix_fmt yuv420p -r 60 -c:a aac -b:a 128k -t 7.5 -movflags +faststart -y $high
 if($LASTEXITCODE -ne 0){throw "High-quality encode failed: $aspect"}
 Assert-Film $high 450 60
 $size=if($aspect -eq 'landscape'){'960:540'}else{'540:960'}
 & ffmpeg -hide_banner -loglevel error -i $high -vf "fps=30,scale=${size}:flags=lanczos" -frames:v 225 -c:v libx264 -preset medium -crf 23 -pix_fmt yuv420p -r 30 -c:a copy -t 7.5 -movflags +faststart -y $lite
 if($LASTEXITCODE -ne 0){throw "Lightweight encode failed: $aspect"}
 Assert-Film $lite 225 30
 Get-Item -LiteralPath $high,$lite | Select-Object Name,Length
}
