[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$InstallRoot
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $InstallRoot).Path
$required = @(
    'SFC3.exe',
    'ddraw.dll',
    'x3d8.dll',
    'dxcfg.exe',
    'dxcfg.ini',
    'sfc.ini',
    'Assets\CommonSettings\WeaponItems.gf'
)

$files = foreach ($relativePath in $required) {
    $path = Join-Path $root $relativePath
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        [pscustomobject]@{
            Path = $relativePath
            Present = $false
            Length = $null
            SHA256 = $null
            Version = $null
        }
        continue
    }
    $item = Get-Item -LiteralPath $path
    [pscustomobject]@{
        Path = $relativePath
        Present = $true
        Length = $item.Length
        SHA256 = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
        Version = $item.VersionInfo.FileVersion
    }
}

$registryPath = 'HKLM:\SOFTWARE\WOW6432Node\Activision\Star Trek Starfleet Command III'
$registry = if (Test-Path -LiteralPath $registryPath) {
    $values = Get-ItemProperty -LiteralPath $registryPath
    [pscustomobject]@{
        Present = $true
        InstallPath = $values.InstallPath
        InstallDrive = $values.InstallDrive
        CD = $values.CD
        Version = $values.Version
        HasKey = -not [string]::IsNullOrWhiteSpace([string]$values.KEY)
    }
} else {
    [pscustomobject]@{
        Present = $false
        InstallPath = $null
        InstallDrive = $null
        CD = $null
        Version = $null
        HasKey = $false
    }
}

$wrapperConfig = Get-Content -LiteralPath (Join-Path $root 'dxcfg.ini') -Raw
$crashLogPath = Join-Path $root 'UnhandledException.log'
$latestCrash = if (Test-Path -LiteralPath $crashLogPath) {
    Get-Content -LiteralPath $crashLogPath -Raw
} else {
    $null
}

[pscustomobject]@{
    InstallRoot = $root
    Files = $files
    Registry = $registry
    RegistryMatchesInstallRoot = (
        $registry.Present -and
        ([string]$registry.InstallPath).TrimEnd('\') -ieq $root.TrimEnd('\')
    )
    WrapperConfig = $wrapperConfig
    LatestCrash = $latestCrash
}
