# Runs once from the installer: makes sure Python 3.11+ exists, then sets up Frame's Python environment.
$ErrorActionPreference = 'Stop'
$app = Split-Path $PSScriptRoot -Parent
Set-Location $app
Write-Host 'Setting up Frame. This downloads Python packages once and can take a few minutes.'

function Test-Python {
    foreach ($candidate in @('py -3.13', 'py -3.12', 'py -3.11', 'python')) {
        $parts = $candidate.Split(' ')
        try {
            $ok = & $parts[0] @($parts[1..9] | Where-Object { $_ }) -c 'import sys; print(sys.version_info >= (3, 11))' 2>$null
            if ($LASTEXITCODE -eq 0 -and $ok -eq 'True') { return $true }
        } catch {}
    }
    return $false
}

if (-not (Test-Python)) {
    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        Write-Host 'Python 3.11+ is required. Install it from https://www.python.org/downloads/ and run this installer again.' -ForegroundColor Yellow
        Read-Host 'Press Enter to close'
        exit 1
    }
    Write-Host 'Installing Python 3.12 for this user with winget...'
    winget install --id Python.Python.3.12 --scope user --silent --accept-package-agreements --accept-source-agreements
    # winget updates PATH for new processes only.
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'User') + ';' + [Environment]::GetEnvironmentVariable('Path', 'Machine')
}

try {
    & "$app\setup.ps1"
} catch {
    Write-Host "Setup failed: $_" -ForegroundColor Red
    Write-Host 'You can run setup again later from the install folder: setup.ps1'
    Read-Host 'Press Enter to close'
    exit 1
}
