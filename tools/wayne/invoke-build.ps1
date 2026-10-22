param(
    [ValidateSet('setup', 'baseline', 'prepare-6.12', 'dtbs-6.12', 'image-6.12', 'open-linux', 'rom-setup', 'rom-sync', 'rom-build')]
    [string]$Mode = 'baseline',
    [string]$Distribution = 'Ubuntu-24.04'
)
$ErrorActionPreference = 'Stop'
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..'))
$linuxRepo = (& wsl.exe -d $Distribution -- wslpath -u $repo | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or -not $linuxRepo.StartsWith('/')) {
    throw 'WSL is not ready. Install Ubuntu-24.04 and finish its first launch before building.'
}
if ($Mode -eq 'open-linux') {
    $linuxUser = (& wsl.exe -d $Distribution -- id -un | Out-String).Trim()
    $linuxHome = (& wsl.exe -d $Distribution -- printenv HOME | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $linuxUser -or -not $linuxHome.StartsWith('/')) {
        throw 'Cannot resolve the Linux user and home directory.'
    }
    & code --new-window --remote "wsl+$Distribution" "$linuxHome/wayne-kernel/vendor"
} elseif ($Mode.StartsWith('rom-')) {
    if ($Mode -in @('rom-sync', 'rom-build')) {
        $distroRegistry = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Lxss'
        $registered = Get-ChildItem $distroRegistry -ErrorAction Stop | Get-ItemProperty |
            Where-Object { $_.DistributionName -eq $Distribution } | Select-Object -First 1
        if (-not $registered) { throw 'Cannot identify the WSL distribution storage location.' }
        $basePath = ([string]$registered.BasePath) -replace '^\\\\\?\\', ''
        $storageRoot = [IO.Path]::GetPathRoot($basePath)
        $storageDrive = [IO.DriveInfo]::new($storageRoot)
        $requiredGiB = if ($Mode -eq 'rom-sync') { 400 } else { 100 }
        if ($storageDrive.AvailableFreeSpace -lt $requiredGiB * 1GB) {
            throw "WSL is stored on $storageRoot, which has insufficient space. Move this distribution to D: before syncing/building the ROM."
        }
    }
    if ($Mode -eq 'rom-setup') {
        & wsl.exe -d $Distribution -u root -- bash "$linuxRepo/tools/wayne/rom.sh" dependencies
        if ($LASTEXITCODE -ne 0) { throw 'ROM dependency installation failed.' }
    }
    & wsl.exe -d $Distribution -- bash "$linuxRepo/tools/wayne/rom.sh" $Mode.Substring(4)
} else {
    if ($Mode -eq 'setup') {
        & wsl.exe -d $Distribution -u root -- bash "$linuxRepo/tools/wayne/build.sh" dependencies
        if ($LASTEXITCODE -ne 0) { throw 'Kernel dependency installation failed.' }
    }
    & wsl.exe -d $Distribution -- bash "$linuxRepo/tools/wayne/build.sh" $Mode
}
if ($LASTEXITCODE -ne 0) { throw "Task '$Mode' failed with exit code $LASTEXITCODE." }
