param([Parameter(Mandatory=$true)][string]$Installer, [string]$PreviousInstaller)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$installerPath = (Resolve-Path -LiteralPath $Installer).Path
$registryPath = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\DJIVirtualGasFixer'
if (Test-Path -LiteralPath $registryPath) { throw 'An installed copy exists; isolated smoke test must not replace its registration.' }
if (Get-Process -Name VirtualGasFixer,DJIVirtualGasFixer -ErrorAction SilentlyContinue) { throw 'Close the application before testing its installer.' }
$menuFolder = Join-Path ([Environment]::GetFolderPath('Programs')) 'VirtualGasFixer'
if (Test-Path -LiteralPath $menuFolder) { throw 'Start menu folder already exists; test must not replace it.' }
$legacyMenu = Join-Path ([Environment]::GetFolderPath('Programs')) 'DJI Virtual Gas Fixer'
if (Test-Path -LiteralPath $legacyMenu) { throw 'Legacy Start menu folder exists; test must not replace it.' }
$testRoot = Join-Path $projectRoot ('build\installer-smoke-' + [guid]::NewGuid().ToString('N'))
$installRoot = Join-Path $testRoot 'app'
if (-not $installRoot.StartsWith(($projectRoot + '\'), [StringComparison]::OrdinalIgnoreCase)) { throw 'Test target escaped the workspace.' }
New-Item -ItemType Directory -Path $testRoot -Force | Out-Null
$settingsPath = Join-Path $env:LOCALAPPDATA 'VirtualGasFixer\settings.json'
$settingsHash = if (Test-Path -LiteralPath $settingsPath) { (Get-FileHash -LiteralPath $settingsPath -Algorithm SHA256).Hash } else { $null }
$legacySettingsPath = Join-Path $env:LOCALAPPDATA 'DJIVirtualGasFixer\settings.json'
$legacySettingsHash = if (Test-Path -LiteralPath $legacySettingsPath) { (Get-FileHash -LiteralPath $legacySettingsPath -Algorithm SHA256).Hash } else { $null }
if ($PreviousInstaller) {
    $oldInstaller = (Resolve-Path -LiteralPath $PreviousInstaller).Path
    $oldProcess = Start-Process -FilePath $oldInstaller -ArgumentList @('/S', ('/D=' + $installRoot)) -WindowStyle Hidden -Wait -PassThru
    if ($oldProcess.ExitCode -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $installRoot 'DJIVirtualGasFixer.exe'))) { throw 'Previous version installation failed' }
    Set-Content -LiteralPath (Join-Path $installRoot 'user-note.txt') -Value 'User-owned file: must survive upgrade.'
}
$process = Start-Process -FilePath $installerPath -ArgumentList @('/S', ('/D=' + $installRoot)) -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) { throw ('Installation failed: ' + $process.ExitCode) }
$payload = Join-Path $projectRoot 'dist\VirtualGasFixer'
$files = @(Get-ChildItem -LiteralPath $payload -File -Recurse)
foreach ($source in $files) {
    $relative = $source.FullName.Substring($payload.Length + 1)
    $installed = Join-Path $installRoot $relative
    if (-not (Test-Path -LiteralPath $installed)) { throw ('Missing installed file: ' + $relative) }
    if ((Get-FileHash -LiteralPath $source.FullName).Hash -ne (Get-FileHash -LiteralPath $installed).Hash) { throw ('Installed file differs: ' + $relative) }
}
$registered = Get-ItemProperty -LiteralPath $registryPath
if ($registered.InstallLocation -ne $installRoot) { throw 'Wrong Windows uninstall registration' }
if ($registered.DisplayName -ne 'VirtualGasFixer' -or $registered.DisplayVersion -ne '1.0.1') { throw 'Wrong product name/version in Windows' }
if (-not (Test-Path -LiteralPath (Join-Path $menuFolder 'VirtualGasFixer.lnk'))) { throw 'Start menu shortcut missing' }
if ($PreviousInstaller) {
    if (Test-Path -LiteralPath (Join-Path $installRoot 'DJIVirtualGasFixer.exe')) { throw 'Legacy executable remains after upgrade' }
    if (Test-Path -LiteralPath $legacyMenu) { throw 'Legacy Start menu shortcuts remain after upgrade' }
    if (-not (Test-Path -LiteralPath (Join-Path $installRoot 'user-note.txt'))) { throw 'Upgrade deleted a user-owned file' }
}
$note = Join-Path $installRoot 'user-note.txt'
Set-Content -LiteralPath $note -Value 'User-owned file: must survive uninstall.'
$uninstaller = Join-Path $installRoot 'Uninstall.exe'
$protectedFile = Join-Path $installRoot 'VirtualGasFixer.exe'
$blockedStream = [IO.File]::Open($protectedFile, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::None)
try {
    $process = Start-Process -FilePath $uninstaller -ArgumentList @('/S', ('_?=' + $installRoot)) -WindowStyle Hidden -Wait -PassThru
} finally {
    $blockedStream.Dispose()
}
if ($process.ExitCode -eq 0) { throw 'Uninstaller reported success despite a protected application file' }
if (-not (Test-Path -LiteralPath $registryPath)) { throw 'Failed uninstall removed its registration' }
if (-not (Test-Path -LiteralPath $uninstaller)) { throw 'Failed uninstall removed its retry mechanism' }
if (-not (Test-Path -LiteralPath (Join-Path $installRoot 'install-id.txt'))) { throw 'Failed uninstall removed its ownership marker' }
$process = Start-Process -FilePath $uninstaller -ArgumentList @('/S') -WindowStyle Hidden -Wait -PassThru
if ($process.ExitCode -ne 0) { throw ('Uninstallation failed: ' + $process.ExitCode) }
if (Test-Path -LiteralPath (Join-Path $installRoot 'VirtualGasFixer.exe')) { throw 'Application was not removed' }
if (Test-Path -LiteralPath (Join-Path $installRoot '_internal')) { throw 'Payload directory was not removed' }
if (-not (Test-Path -LiteralPath $note)) { throw 'Uninstaller deleted an unrelated file' }
if (Test-Path -LiteralPath $registryPath) { throw 'Uninstall registration remains' }
if (Test-Path -LiteralPath $menuFolder) { throw 'Start menu shortcuts remain' }
if ($settingsHash -and (Get-FileHash -LiteralPath $settingsPath).Hash -ne $settingsHash) { throw 'Existing settings changed' }
if ($legacySettingsHash -and (Get-FileHash -LiteralPath $legacySettingsPath).Hash -ne $legacySettingsHash) { throw 'Legacy settings changed' }
Write-Output ('PASS: installed and hash-checked {0} files; registration and Start menu verified; uninstall preserved unrelated files and settings.' -f $files.Count)
