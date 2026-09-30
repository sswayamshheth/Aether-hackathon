# Shared helpers for start.ps1 and demo.ps1
$script:Root = Split-Path -Parent $PSScriptRoot
$script:Py = Join-Path $Root 'backend\.venv\Scripts\python.exe'
$script:Chrome = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LOCALAPPDATA\Google\Chrome\Application\chrome.exe"
) | Where-Object { Test-Path $_ } | Select-Object -First 1

function Assert-Setup {
    if (-not (Test-Path $Py)) {
        throw 'Python venv missing. See README, section Setup.'
    }
    if (-not (Test-Path (Join-Path $Root 'frontend\dist\index.html'))) {
        Write-Host 'Building the dashboard (first run only)...'
        Push-Location (Join-Path $Root 'frontend')
        $env:CI = 'true'
        if (-not (Test-Path 'node_modules')) { & npm ci --no-audit --no-fund }
        & npm run build
        Pop-Location
        if (-not (Test-Path (Join-Path $Root 'frontend\dist\index.html'))) { throw 'Dashboard build failed.' }
    }
}

function Start-Backend([hashtable]$EnvVars, [int]$Port = 8000) {
    $env:YOLO_CONFIG_DIR = Join-Path $Root '.cache\ultralytics'
    $env:PYTHONIOENCODING = 'utf-8'
    foreach ($k in $EnvVars.Keys) { Set-Item -Path "env:$k" -Value $EnvVars[$k] }
    $log = Join-Path $Root '.cache\backend.log'
    $p = Start-Process -FilePath $Py `
        -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port $Port --log-level warning" `
        -WorkingDirectory (Join-Path $Root 'backend') -WindowStyle Hidden -PassThru `
        -RedirectStandardError $log -RedirectStandardOutput (Join-Path $Root '.cache\backend.out.log')
    $p.Id | Set-Content -Path (Join-Path $Root '.cache\backend_pid.txt') -Encoding ascii
    Write-Host "backend starting (pid $($p.Id)), log: .cache\backend.log"
    for ($i = 0; $i -lt 90; $i++) {
        Start-Sleep -Seconds 1
        try {
            return Invoke-RestMethod "http://127.0.0.1:$Port/api/status" -TimeoutSec 2
        } catch { }
        if ($p.HasExited) { throw 'Backend exited. See .cache\backend.log' }
    }
    throw 'Backend did not answer within 90 s. See .cache\backend.log'
}

function Open-Dashboard([int]$Port = 8000) {
    $url = "http://localhost:$Port"
    if ($Chrome) { Start-Process -FilePath $Chrome -ArgumentList $url }
    else { Write-Warning "Google Chrome not found. Open $url in Chrome yourself." }
    Write-Host "Dashboard: $url"
}
