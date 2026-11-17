$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$projectPython = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $projectPython)) { throw 'Create .venv and install requirements.txt first.' }
& $projectPython -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed' }
& $projectPython tools\collect_licenses.py
if ($LASTEXITCODE -ne 0) { throw 'License collection failed' }
& $projectPython -m PyInstaller --noconfirm app.spec
if ($LASTEXITCODE -ne 0) { throw 'Build failed' }
Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'README.md') -Destination (Join-Path $PSScriptRoot 'dist\DJIVirtualGasFixer\README.md') -Force
Write-Output (Join-Path $PSScriptRoot 'dist\DJIVirtualGasFixer\DJIVirtualGasFixer.exe')
