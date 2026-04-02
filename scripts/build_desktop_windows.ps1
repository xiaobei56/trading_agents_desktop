Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$RootDir = Split-Path -Parent $PSScriptRoot
$DistDir = Join-Path $RootDir "dist/windows"
$BuildDir = Join-Path $RootDir "build/pyinstaller-windows"
$VenvPython = Join-Path $RootDir ".venv\\Scripts\\python.exe"
$PythonExe = $null

Set-Location $RootDir

if (Test-Path $VenvPython) {
    $PythonExe = $VenvPython
}
elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $PythonExe = "python"
}
elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $PythonExe = "py"
}
else {
    Write-Error "Python is required but was not found in PATH."
}

try {
    & $PythonExe -m pip --version | Out-Null
}
catch {
    & $PythonExe -m ensurepip --upgrade
}

& $PythonExe -m pip install -U pyinstaller

if (Test-Path $DistDir) {
    Remove-Item $DistDir -Recurse -Force
}
if (Test-Path $BuildDir) {
    Remove-Item $BuildDir -Recurse -Force
}

& $PythonExe -m PyInstaller `
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
