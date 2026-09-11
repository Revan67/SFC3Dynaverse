[CmdletBinding(DefaultParameterSetName = 'Install')]
param(
    [Parameter(Mandatory)]
    [string]$InstallRoot,

    [Parameter(ParameterSetName = 'Restore')]
    [switch]$Restore,

    [Parameter(ParameterSetName = 'Status')]
    [switch]$Status
)

$ErrorActionPreference = 'Stop'

$retailExeHash = '1717552A3033356BB3BAE095F9CBD358658BEE8839FA94895EE06B4A33A274ED'
$patchedExeHash = '418BBC17C044096C5727307E14AC5302211EAA4834065B6324891FAFACCD04D3'
$gogEngineHash = '064ACB22EF62876F2A19B215E5872F40D68233A60C935A64900C155445A1902D'
$patchedEngineHash = '44CBAB768106CE68BA8AA780533F14C274EE8E3864EE13337665B93905D80DCE'
$gogDdrawHash = '20C3FA4A1B23B6C287DBF04E92C0364F2088D0F605148F365937AE3429702F6F'
$gogX3d8Hash = '120880B76BAB31DF02790E76E74E33D719DA465D66ED3730125079A88E7C9CE0'
$rendererHashes = [ordered]@{
    'ddraw.dll' = '838EE34F17309CA4CD515407883A247DB5FA90FE58261C6615FF5CC74FE71E4D'
    'D3D8.dll' = '4E17A6C7DB146B13A873C09BF56C74DC5D92C252A2A122F01C1FA1B327BC1396'
    'D3DImm.dll' = '5F93B9FB7A77ACAFC259A57D3294A0EE70125A8AF8A0A1975AF4CBA818229947'
    'dgVoodoo.conf' = '145C41683B6E5B52CA739993629BDB5A8703153B9025A7277E4B2481AB6BA140'
}

$root = (Resolve-Path -LiteralPath $InstallRoot).Path
$exe = Join-Path $root 'SFC3.exe'
$engine = Join-Path $root 'Components\TAL3DEngineR.dll'
$exeBackup = "$exe.sfc3compat-retail"
$engineBackup = "$engine.sfc3compat-gog"
$ddraw = Join-Path $root 'ddraw.dll'
$x3d8 = Join-Path $root 'x3d8.dll'
$ddrawBackup = "$ddraw.sfc3compat-gog"
$x3d8Backup = "$x3d8.sfc3compat-gog"
$rendererSource = Join-Path $PSScriptRoot 'Renderer'

function Get-Hash([string]$Path) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $null }
    (Get-FileHash -LiteralPath $Path -Algorithm SHA256).Hash
}

function Convert-HexBytes([string]$Text) {
    [byte[]]($Text -split '\s+' | ForEach-Object { [Convert]::ToByte($_, 16) })
}

function Apply-VerifiedPatches([string]$Path, [object[]]$Patches) {
    $bytes = [IO.File]::ReadAllBytes($Path)
    foreach ($patch in $Patches) {
        $before = Convert-HexBytes $patch.Before
        $after = Convert-HexBytes $patch.After
        if ($before.Length -ne $after.Length) {
            throw "Patch length mismatch at offset 0x$($patch.Offset.ToString('X'))."
        }
        for ($index = 0; $index -lt $before.Length; $index++) {
            if ($bytes[$patch.Offset + $index] -ne $before[$index]) {
                throw "Unexpected byte at file offset 0x$(($patch.Offset + $index).ToString('X')) in $Path."
            }
        }
        [Array]::Copy($after, 0, $bytes, $patch.Offset, $after.Length)
    }
    [IO.File]::WriteAllBytes($Path, $bytes)
}

$exePatches = @(
    # StartupDimensions
    @{ Offset = 0x52a7; Before = 'B8 00 03 00 00'; After = 'E8 B4 D4 22 00' }
    @{ Offset = 0x52b2; Before = 'B8 00 04 00 00'; After = 'E8 79 D4 22 00' }
    # DisplayModeTransition
    @{ Offset = 0x691b; Before = '90 90 90 90 90 90'; After = '55 55 6A 00 6A 00' }
    @{ Offset = 0x694d; Before = '90 90 90 90 90 90 90'; After = 'FF 34 85 2C D4 93 00' }
    @{ Offset = 0x6960; Before = '90'; After = '50' }
    @{ Offset = 0x6963; Before = '90 90 90'; After = 'FF 53 1C' }
    @{ Offset = 0x6a32; Before = 'E9 39 01 00 00 90'; After = '0F 8E 38 01 00 00' }
)

$enginePatches = @(
    @{ Offset = 0x552c2; Before = '90 90 90 90 90 90'; After = '89 86 80 A4 02 00' }
    @{ Offset = 0x55330; Before = '90 90 BA 00 04 00 00 90'; After = '74 31 8B 96 C0 A5 02 00' }
    @{ Offset = 0x55344; Before = '90 90 B8 00 03 00 00 90'; After = '2B D0 8B 86 C4 A5 02 00' }
    @{ Offset = 0x5534f; Before = '90 90'; After = '2B C1' }
    @{ Offset = 0x5535c; Before = '57 08 90 90 90'; After = '91 38 04 00 00' }
    @{ Offset = 0x55864; Before = '90 90 90 90 90 90'; After = '89 86 80 A4 02 00' }
    @{ Offset = 0x558a5; Before = '90 90 B8 00 04 00 00 90'; After = '74 30 8B 86 C0 A5 02 00' }
    @{ Offset = 0x558b3; Before = '90 90'; After = '2B C1' }
    @{ Offset = 0x558c1; Before = 'B9 00 03 00 00 90 90 90'; After = '8B 86 BC A5 02 00 2B C8' }
    @{ Offset = 0x558d0; Before = '55 08 90 90 90'; After = '93 38 04 00 00' }
    @{ Offset = 0x97a4e; Before = '78'; After = '64' }
)

if ($Status) {
    [pscustomobject]@{ File = $exe; Hash = Get-Hash $exe; ExpectedPatched = $patchedExeHash }
    [pscustomobject]@{ File = $engine; Hash = Get-Hash $engine; ExpectedPatched = $patchedEngineHash }
    foreach ($entry in $rendererHashes.GetEnumerator()) {
        $path = Join-Path $root $entry.Key
        [pscustomobject]@{ File = $path; Hash = Get-Hash $path; ExpectedPatched = $entry.Value }
    }
    [pscustomobject]@{ File = $x3d8; Hash = Get-Hash $x3d8; ExpectedPatched = '(disabled)' }
    exit
}

if ($Restore) {
    if ((Get-Hash $exeBackup) -ne $retailExeHash) { throw "Verified executable backup is missing: $exeBackup" }
    if ((Get-Hash $engineBackup) -ne $gogEngineHash) { throw "Verified engine backup is missing: $engineBackup" }
    Copy-Item -LiteralPath $exeBackup -Destination $exe -Force
    Copy-Item -LiteralPath $engineBackup -Destination $engine -Force
    if ((Get-Hash $ddrawBackup) -ne $gogDdrawHash) { throw "Verified GOG ddraw backup is missing: $ddrawBackup" }
    if ((Get-Hash $x3d8Backup) -ne $gogX3d8Hash) { throw "Verified GOG x3d8 backup is missing: $x3d8Backup" }
    Copy-Item -LiteralPath $ddrawBackup -Destination $ddraw -Force
    Copy-Item -LiteralPath $x3d8Backup -Destination $x3d8 -Force
    foreach ($name in @('D3D8.dll', 'D3DImm.dll', 'dgVoodoo.conf')) {
        $path = Join-Path $root $name
        if (Test-Path -LiteralPath $path) {
            if ((Get-Hash $path) -ne $rendererHashes[$name]) {
                throw "Refusing to remove an unrecognized file during restore: $path"
            }
            Remove-Item -LiteralPath $path -Force
        }
    }
    Write-Host 'Restored the verified GOG executable, engine DLL, and wrapper files.'
    exit
}

$runningTarget = Get-Process SFC3 -ErrorAction SilentlyContinue | Where-Object {
    try { [IO.Path]::GetFullPath($_.Path) -eq [IO.Path]::GetFullPath($exe) } catch { $false }
}
if ($runningTarget) {
    throw 'Close SFC3 from the target installation before installing the compatibility patch.'
}

$alreadyPatched = (Get-Hash $exe) -eq $patchedExeHash -and (Get-Hash $engine) -eq $patchedEngineHash
if (-not $alreadyPatched) {
    if ((Get-Hash $exe) -ne $retailExeHash) { throw 'SFC3.exe does not match the supported GOG retail file.' }
    if ((Get-Hash $engine) -ne $gogEngineHash) { throw 'TAL3DEngineR.dll does not match the supported GOG retail file.' }
}

foreach ($entry in $rendererHashes.GetEnumerator()) {
    $sourcePath = Join-Path $rendererSource $entry.Key
    if ((Get-Hash $sourcePath) -ne $entry.Value) { throw "Bundled renderer file failed verification: $sourcePath" }
}
if (-not (Test-Path -LiteralPath $ddrawBackup)) {
    if ((Get-Hash $ddraw) -ne $gogDdrawHash) { throw 'ddraw.dll does not match the supported GOG wrapper.' }
    Copy-Item -LiteralPath $ddraw -Destination $ddrawBackup
}
if (-not (Test-Path -LiteralPath $x3d8Backup)) {
    if ((Get-Hash $x3d8) -ne $gogX3d8Hash) { throw 'x3d8.dll does not match the supported GOG wrapper.' }
    Copy-Item -LiteralPath $x3d8 -Destination $x3d8Backup
}
if ((Get-Hash $ddrawBackup) -ne $gogDdrawHash) { throw 'Existing ddraw backup is not the verified GOG file.' }
if ((Get-Hash $x3d8Backup) -ne $gogX3d8Hash) { throw 'Existing x3d8 backup is not the verified GOG file.' }

if (-not (Test-Path -LiteralPath $exeBackup)) { Copy-Item -LiteralPath $exe -Destination $exeBackup }
if (-not (Test-Path -LiteralPath $engineBackup)) { Copy-Item -LiteralPath $engine -Destination $engineBackup }
if ((Get-Hash $exeBackup) -ne $retailExeHash) { throw 'Existing executable backup is not the verified retail file.' }
if ((Get-Hash $engineBackup) -ne $gogEngineHash) { throw 'Existing engine backup is not the verified GOG file.' }

if (-not $alreadyPatched) {
    Apply-VerifiedPatches -Path $exe -Patches $exePatches
    Apply-VerifiedPatches -Path $engine -Patches $enginePatches
}

foreach ($entry in $rendererHashes.GetEnumerator()) {
    Copy-Item -LiteralPath (Join-Path $rendererSource $entry.Key) -Destination (Join-Path $root $entry.Key) -Force
}
if (Test-Path -LiteralPath $x3d8) { Remove-Item -LiteralPath $x3d8 -Force }

if ((Get-Hash $exe) -ne $patchedExeHash) { throw 'Patched executable failed its final hash check.' }
if ((Get-Hash $engine) -ne $patchedEngineHash) { throw 'Patched engine DLL failed its final hash check.' }
foreach ($entry in $rendererHashes.GetEnumerator()) {
    if ((Get-Hash (Join-Path $root $entry.Key)) -ne $entry.Value) { throw "Installed renderer failed verification: $($entry.Key)" }
}
if (Test-Path -LiteralPath $x3d8) { throw 'GOG x3d8.dll could not be disabled.' }

Write-Host 'SFC3 compatibility patch installed and verified.'
Write-Host "Original files preserved as:`n  $exeBackup`n  $engineBackup`n  $ddrawBackup`n  $x3d8Backup"
