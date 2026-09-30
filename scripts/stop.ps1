# Stops what start.ps1 / demo.ps1 / simulate_rtsp.ps1 started, by saved PID only, and only
# if that PID still belongs to a program inside this project folder.
$root = Split-Path -Parent $PSScriptRoot
foreach ($name in 'rtsp_pids.txt', 'backend_pid.txt') {
    $f = Join-Path $root ".cache\$name"
    if (-not (Test-Path $f)) { continue }
    foreach ($line in Get-Content $f) {
        if (-not $line) { continue }
        $id = [int]$line
        $proc = Get-Process -Id $id -ErrorAction SilentlyContinue
        if ($proc -and $proc.Path -and $proc.Path.ToLower().StartsWith($root.ToLower())) {
            & taskkill /PID $id /T /F | Out-Null
            Write-Host "stopped $($proc.ProcessName) ($id)"
        }
    }
    Clear-Content $f
}
