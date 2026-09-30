# Publishes the demo clips as looping RTSP streams: rtsp://localhost:8554/cam1 .. cam4
# MediaMTX is the RTSP server, ffmpeg plays the part of the cameras.
# PIDs are saved to .cache\rtsp_pids.txt so scripts\stop.ps1 can stop exactly these.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
$mtx = Join-Path $root 'tools\mediamtx\mediamtx.exe'
$ffmpeg = Join-Path $root 'tools\ffmpeg\bin\ffmpeg.exe'
$pidFile = Join-Path $root '.cache\rtsp_pids.txt'
foreach ($f in $mtx, $ffmpeg) {
    if (-not (Test-Path $f)) { throw "Missing $f. See README, section Setup." }
}

$cams = (Get-Content (Join-Path $root 'scripts\cameras.json') -Raw | ConvertFrom-Json).cameras
$pids = @()
$p = Start-Process -FilePath $mtx -ArgumentList "`"$(Join-Path $root 'tools\mediamtx\mediamtx.yml')`"" `
    -WorkingDirectory (Join-Path $root 'tools\mediamtx') -WindowStyle Hidden -PassThru
$pids += $p.Id
Start-Sleep -Seconds 2
foreach ($c in $cams) {
    $clip = Join-Path $root $c.clip
    if (-not (Test-Path $clip)) {
        Write-Warning "clip missing for $($c.id): $clip (run training\prepare_demo.py)"
        continue
    }
    $ffArgs = "-v error -re -stream_loop -1 -i `"$clip`" -an -c:v libx264 -preset ultrafast -tune zerolatency -g 20 -pix_fmt yuv420p -f rtsp -rtsp_transport tcp $($c.rtsp)"
    $p = Start-Process -FilePath $ffmpeg -ArgumentList $ffArgs -WindowStyle Hidden -PassThru
    $pids += $p.Id
    Write-Host "publishing $($c.rtsp)  <-  $($c.clip)"
}
$pids | Set-Content -Path $pidFile -Encoding ascii
Write-Host "RTSP simulation running ($($pids.Count) processes). Stop with scripts\stop.ps1"
