# Demo mode: replays the demo clips with cached detections. No RTSP, no model inference,
# no network. Incidents are rebuilt live from the cached detections, so the queue fills in
# sync with the video and the demo cannot stutter on a busy CPU.
#   powershell -ExecutionPolicy Bypass -File scripts\demo.ps1
param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')
Assert-Setup
if (-not (Test-Path (Join-Path $Root 'data\demo\cache\cam1.json'))) {
    throw 'Demo cache missing. Build it once with: backend\.venv\Scripts\python training\prepare_demo.py'
}
& (Join-Path $PSScriptRoot 'stop.ps1')
$s = Start-Backend @{ DRISHTI_DEMO = '1'; DRISHTI_SEED = '' }
Write-Host "demo backend up: $($s.cameras_total) cameras, $($s.inference)"
if (-not $NoBrowser) { Open-Dashboard }
Write-Host 'Stop with scripts\stop.ps1'
