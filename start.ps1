$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) { throw 'Run setup.ps1 first.' }
$backend = Start-Process -FilePath "$PSScriptRoot\.venv\Scripts\python.exe" -ArgumentList '-m uvicorn backend.main:app --host 127.0.0.1 --port 8000' -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
try {
    Set-Location "$PSScriptRoot\frontend"
    Write-Host 'Open http://127.0.0.1:3000 — press Ctrl+C here to stop.'
    npm run dev
} finally {
    if (-not $backend.HasExited) { Stop-Process -Id $backend.Id }
}
