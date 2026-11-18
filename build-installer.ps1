param([switch]$RebuildApp)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if ($RebuildApp) { & (Join-Path $PSScriptRoot 'build.ps1') }
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
$compiler = Join-Path $PSScriptRoot '.tools\nsis-3.13\makensis.exe'
if (-not (Test-Path -LiteralPath $compiler)) {
    $installedCompiler = Get-Command makensis.exe -ErrorAction SilentlyContinue
    if (-not $installedCompiler) { throw 'NSIS 3.13 compiler not found in .tools or PATH.' }
    $compiler = $installedCompiler.Source
}
& $projectPython tools\installer_manifest.py
if ($LASTEXITCODE -ne 0) { throw 'Installer manifest failed' }
& $compiler /V2 installer\setup.nsi
if ($LASTEXITCODE -ne 0) { throw 'Installer compilation failed' }
Write-Output (Join-Path $PSScriptRoot 'dist\VirtualGasFixer-Setup-1.0.1.exe')
