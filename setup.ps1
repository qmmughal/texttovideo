$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Test-Path '.venv\Scripts\python.exe')) {
    python -m venv .venv
}
python -m pip --python .venv\Scripts\python.exe install -r backend\requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }
Push-Location frontend
npm ci
if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
Pop-Location
& .\.venv\Scripts\python.exe -m scripts.sample
Write-Host 'Setup complete. Run .\start.ps1'
