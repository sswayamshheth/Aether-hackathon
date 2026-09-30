# One command: RTSP simulation (MediaMTX + ffmpeg), backend with live inference, dashboard in Chrome.
#   powershell -ExecutionPolicy Bypass -File scripts\start.ps1
# -NoRtsp     read the demo clips as files instead of publishing RTSP
# -NoBrowser  do not open Chrome
param([switch]$NoBrowser, [switch]$NoRtsp)
$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '_common.ps1')
Assert-Setup
& (Join-Path $PSScriptRoot 'stop.ps1')
$seed = 'rtsp'
if ($NoRtsp) {
    $seed = 'file'
} else {
    try {
        & (Join-Path $PSScriptRoot 'simulate_rtsp.ps1')
    } catch {
        Write-Warning "RTSP simulation failed ($_). Falling back to reading the clips as files."
        $seed = 'file'
    }
}
$s = Start-Backend @{ DRISHTI_DEMO = '0'; DRISHTI_SEED = $seed }
Write-Host "backend up: $($s.cameras_total) cameras, inference: $($s.inference)"
if (-not $NoBrowser) { Open-Dashboard }
Write-Host 'Stop everything with scripts\stop.ps1'
