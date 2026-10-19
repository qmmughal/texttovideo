param(
    # Hot-reloading frontend on port 3000 for development; normal use serves everything from port 8000.
    [switch]$Dev
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = "$PSScriptRoot\.venv\Scripts\python.exe"
if (-not (Test-Path $python)) { throw 'Run setup.ps1 first.' }

if ($Dev) {
    $backend = Start-Process -FilePath $python -ArgumentList '-m uvicorn backend.main:app --host 127.0.0.1 --port 8000' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
    try {
        Set-Location "$PSScriptRoot\frontend"
        Write-Host 'Open http://127.0.0.1:3000 - press Ctrl+C here to stop.'
        npm run dev
    } finally {
        if (-not $backend.HasExited) { Stop-Process -Id $backend.Id }
    }
    return
}

if (-not (Test-Path 'frontend\out\index.html')) { throw 'The web interface is not built. Run setup.ps1 again.' }
$url = 'http://127.0.0.1:8000'
Write-Host "Frame is starting at $url - keep this window open; press Ctrl+C to stop."
# Open the browser once the server answers.
Start-Job -ScriptBlock {
    param($url)
    for ($i = 0; $i -lt 60; $i++) {
        try { Invoke-WebRequest "$url/api/settings" -UseBasicParsing -TimeoutSec 2 | Out-Null; Start-Process $url; return } catch { Start-Sleep 1 }
    }
} -ArgumentList $url | Out-Null
& $python -m uvicorn backend.main:app --host 127.0.0.1 --port 8000
