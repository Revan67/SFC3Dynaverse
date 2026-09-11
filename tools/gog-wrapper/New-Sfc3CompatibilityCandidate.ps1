[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$RetailExecutable,

    [Parameter(Mandatory)]
    [string]$OutputExecutable,

    [ValidateSet('DisplayGate', 'StartupDimensions', 'DisplayModeTransition')]
    [string[]]$PatchGroup = @('StartupDimensions', 'DisplayModeTransition')
)

$ErrorActionPreference = 'Stop'

$knownRetailHash = '1717552A3033356BB3BAE095F9CBD358658BEE8839FA94895EE06B4A33A274ED'
$source = (Resolve-Path -LiteralPath $RetailExecutable).Path
$sourceHash = (Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash
if ($sourceHash -ne $knownRetailHash) {
    throw "Refusing to patch an unknown executable. Expected $knownRetailHash; found $sourceHash."
}

$patches = @{
    DisplayGate = @(
        @{ Offset = 0x10ec; Before = '90 90'; After = '75 07' }
    )
    StartupDimensions = @(
        @{ Offset = 0x52a7; Before = 'B8 00 03 00 00'; After = 'E8 B4 D4 22 00' }
        @{ Offset = 0x52b2; Before = 'B8 00 04 00 00'; After = 'E8 79 D4 22 00' }
    )
    DisplayModeTransition = @(
        @{ Offset = 0x691b; Before = '90 90 90 90 90 90'; After = '55 55 6A 00 6A 00' }
        @{ Offset = 0x694d; Before = '90 90 90 90 90 90 90'; After = 'FF 34 85 2C D4 93 00' }
        @{ Offset = 0x6960; Before = '90'; After = '50' }
        @{ Offset = 0x6963; Before = '90 90 90'; After = 'FF 53 1C' }
        @{ Offset = 0x6a32; Before = 'E9 39 01 00 00 90'; After = '0F 8E 38 01 00 00' }
    )
}

function Convert-HexBytes([string]$Text) {
    [byte[]]($Text -split '\s+' | ForEach-Object { [Convert]::ToByte($_, 16) })
}

$bytes = [IO.File]::ReadAllBytes($source)
foreach ($group in $PatchGroup) {
    foreach ($patch in $patches[$group]) {
        $before = Convert-HexBytes $patch.Before
        $after = Convert-HexBytes $patch.After
        if ($before.Length -ne $after.Length) {
            throw "Patch length mismatch in $group at offset 0x$($patch.Offset.ToString('X'))."
        }
        for ($index = 0; $index -lt $before.Length; $index++) {
            $actual = $bytes[$patch.Offset + $index]
            if ($actual -ne $before[$index]) {
                throw "Unexpected byte in $group at file offset 0x$(($patch.Offset + $index).ToString('X'))."
            }
        }
        [Array]::Copy($after, 0, $bytes, $patch.Offset, $after.Length)
    }
}

$destination = [IO.Path]::GetFullPath($OutputExecutable)
[IO.File]::WriteAllBytes($destination, $bytes)
Write-Host "Created compatibility candidate: $destination"
Write-Host "Patch groups: $($PatchGroup -join ', ')"
Write-Host "SHA-256: $((Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash)"
