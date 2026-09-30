# One-time setup on Windows for a fresh clone. Run from the project folder:
#   powershell -ExecutionPolicy Bypass -File scripts\setup.ps1
# Needs: Python 3.12 or 3.13, Node 20+, Google Chrome, internet. Takes 10-20 minutes.
# -Gpu  install PyTorch with NVIDIA CUDA support instead of the CPU build
param([switch]$Gpu)
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $PSScriptRoot
Set-Location $root
$env:PIP_DISABLE_PIP_VERSION_CHECK = '1'
$env:HF_HOME = Join-Path $root '.cache\hf'
$env:YOLO_CONFIG_DIR = Join-Path $root '.cache\ultralytics'
New-Item -ItemType Directory -Force .cache, tools | Out-Null

foreach ($t in 'python', 'node', 'npm') {
    if (-not (Get-Command $t -ErrorAction SilentlyContinue)) { throw "$t not found on PATH. Install it first." }
}

# 1. Python environment (pinned)
Write-Host '== Python environment'
if (-not (Test-Path 'backend\.venv\Scripts\python.exe')) { & python -m venv backend\.venv }
$py = Join-Path $root 'backend\.venv\Scripts\python.exe'
& $py -m pip install -q --upgrade pip
$index = if ($Gpu) { 'https://download.pytorch.org/whl/cu126' } else { 'https://download.pytorch.org/whl/cpu' }
& $py -m pip install -q torch==2.14.0 torchvision==0.29.0 --index-url $index
# the pinned list names the CPU build of torch; it is installed already, so skip those two lines
Get-Content backend\requirements.txt | Where-Object { $_ -notmatch '^(torch|torchvision)==' } |
    Set-Content -Encoding ascii .cache\requirements-rest.txt
& $py -m pip install -q -r .cache\requirements-rest.txt
& $py -c "import torch; print('torch', torch.__version__, '| CUDA GPU:', torch.cuda.is_available())"

# 2. Tools: ffmpeg (evidence clips, RTSP publishing) and MediaMTX (RTSP server)
Write-Host '== Tools'
if (-not (Test-Path 'tools\ffmpeg\bin\ffmpeg.exe')) {
    Invoke-WebRequest -UseBasicParsing -OutFile .cache\ffmpeg.zip `
        'https://github.com/GyanD/codexffmpeg/releases/download/9.0.2/ffmpeg-9.0.2-essentials_build.zip'
    Expand-Archive -Force .cache\ffmpeg.zip .cache\ffmpeg_unzip
    Move-Item (Get-ChildItem .cache\ffmpeg_unzip -Directory | Select-Object -First 1).FullName tools\ffmpeg
    Remove-Item -Recurse -Force .cache\ffmpeg.zip, .cache\ffmpeg_unzip
}
if (-not (Test-Path 'tools\mediamtx\mediamtx.exe')) {
    Invoke-WebRequest -UseBasicParsing -OutFile .cache\mediamtx.zip `
        'https://github.com/bluenviron/mediamtx/releases/download/v1.21.1/mediamtx_v1.21.1_windows_amd64.zip'
    Expand-Archive -Force .cache\mediamtx.zip tools\mediamtx
    Remove-Item -Force .cache\mediamtx.zip
}

# 3. Model weights (public, pinned revisions; about 1.8 GB)
Write-Host '== Models'
& $py training\get_models.py

# 4. Dashboard
Write-Host '== Dashboard'
Push-Location frontend
$env:CI = 'true'
& npm ci --no-audit --no-fund
& npm run build
Pop-Location

Write-Host ''
Write-Host 'Setup done. Live mode with the three dataset videos:'
Write-Host '  powershell -ExecutionPolicy Bypass -File scripts\start.ps1 -Cams 3'
