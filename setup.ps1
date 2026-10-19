$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

function Find-Python {
    foreach ($candidate in @('py -3.13', 'py -3.12', 'py -3.11', 'python', 'python3')) {
        $parts = $candidate.Split(' ')
        try {
            $version = & $parts[0] @($parts[1..9] | Where-Object { $_ }) -c 'import sys; print("%d.%d" % sys.version_info[:2])' 2>$null
            if ($LASTEXITCODE -eq 0 -and [version]$version -ge [version]'3.11') { return $parts }
        } catch {}
    }
    throw 'Python 3.11 or newer was not found. Install it from https://www.python.org/downloads/ and run setup again.'
}

if (-not (Test-Path '.venv\Scripts\python.exe')) {
    $python = Find-Python
    & $python[0] @($python[1..9] | Where-Object { $_ }) -m venv .venv
}
$venv = "$PSScriptRoot\.venv\Scripts\python.exe"

# Some Python installs create a venv without pip; ensurepip repairs that.
& $venv -m pip --version *> $null
if ($LASTEXITCODE -ne 0) { & $venv -m ensurepip --upgrade }
& $venv -m pip install --upgrade --disable-pip-version-check -r backend\requirements.txt
if ($LASTEXITCODE -ne 0) { throw 'Python dependency installation failed.' }

if ((Test-Path 'frontend\package.json') -and (Get-Command npm -ErrorAction SilentlyContinue)) {
    Push-Location frontend
    npm ci
    if ($LASTEXITCODE -ne 0) { throw 'Frontend dependency installation failed.' }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw 'Frontend build failed.' }
    Pop-Location
} elseif (-not (Test-Path 'frontend\out\index.html')) {
    throw 'Node.js 22+ is needed to build the web interface. Install it from https://nodejs.org and run setup again.'
}

& $venv -m scripts.sample
Write-Host 'Setup complete. Run .\start.ps1'
