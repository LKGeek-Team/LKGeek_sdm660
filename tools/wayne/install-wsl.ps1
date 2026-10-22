# Run once from an elevated PowerShell terminal. This script never restarts Windows.
$ErrorActionPreference = 'Stop'
$principal = [Security.Principal.WindowsPrincipal]::new([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Open PowerShell as Administrator, then run this script again.'
}
& wsl.exe --install --distribution Ubuntu-24.04 --no-launch
if ($LASTEXITCODE -notin @(0, 3010)) {
    throw "WSL installation exited with code $LASTEXITCODE."
}
Write-Host 'If Windows requests a restart, restart manually. Then open Ubuntu-24.04 and finish creating your Linux user.'
