Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$DistDir = Join-Path $RootDir "dist/windows"
$BuildDir = Join-Path $RootDir "build/pyinstaller-windows"
$VenvPython = Join-Path $RootDir ".venv\\Scripts\\python.exe"

Set-Location $RootDir

if (-not (Test-Path $VenvPython)) {
    Write-Error "Missing .venv. Create a virtualenv first."
}

try {
    & $VenvPython -m pip --version | Out-Null
}
catch {
    & $VenvPython -m ensurepip --upgrade
}

& $VenvPython -m pip install -U pyinstaller

if (Test-Path $DistDir) {
    Remove-Item $DistDir -Recurse -Force
}
if (Test-Path $BuildDir) {
    Remove-Item $BuildDir -Recurse -Force
}

& $VenvPython -m PyInstaller `
    --noconfirm `
    --clean `
    --windowed `
    --name TradingAgentsDesktop `
    --distpath $DistDir `
    --workpath $BuildDir `
    --specpath $BuildDir `
    --paths $RootDir `
    --collect-all tradingagents `
    --collect-all cli `
    --collect-all akshare `
    --collect-all stockstats `
    --hidden-import tradingagents.desktop.app `
    --add-data "$RootDir\\assets;assets" `
    tradingagents/desktop/app.py

Write-Host ""
Write-Host "Build complete:"
Write-Host "  $DistDir\\TradingAgentsDesktop.exe"
Write-Host "  $DistDir\\TradingAgentsDesktop\\"
