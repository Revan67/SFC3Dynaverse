[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$InstallRoot,

    [Parameter(Mandatory = $false)]
    [switch]$Wait,

    [Parameter(Mandatory = $false)]
    [switch]$UseShellStart,

    [Parameter(Mandatory = $false)]
    [switch]$WindowedCompatibility,

    [Parameter(Mandatory = $false)]
    [switch]$WindowedOnly,

    [Parameter(Mandatory = $false)]
    [switch]$RestoreSettings
)

$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath $InstallRoot).Path
$executable = Join-Path $root 'SFC3.exe'
$spriteArchive = Join-Path $root 'Assets\Sprites\sprites.q3'

foreach ($requiredPath in @($executable, $spriteArchive)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required SFC3 file is missing: $requiredPath"
    }
}

if (@($WindowedCompatibility, $WindowedOnly, $RestoreSettings).Where({ $_ }).Count -gt 1) {
    throw 'Choose only one settings mode.'
}

$iniPath = Join-Path $root 'sfc.ini'
$backupPath = Join-Path $root 'sfc.ini.pre-wrapper-test'
if ($RestoreSettings) {
    if (-not (Test-Path -LiteralPath $backupPath)) {
        throw "Settings backup is missing: $backupPath"
    }
    Copy-Item -LiteralPath $backupPath -Destination $iniPath -Force
    Write-Host "Restored original settings from: $backupPath"
}

if ($WindowedCompatibility -or $WindowedOnly) {
    if (-not (Test-Path -LiteralPath $backupPath)) {
        Copy-Item -LiteralPath $iniPath -Destination $backupPath
        Write-Host "Preserved original settings: $backupPath"
    }
    if ($WindowedOnly) {
        Copy-Item -LiteralPath $backupPath -Destination $iniPath -Force
        Write-Host 'Reset to the original settings before the isolated windowed test.'
    }
    $ini = Get-Content -LiteralPath $iniPath -Raw
    $rendererSettings = if ($WindowedOnly) {
        [ordered]@{ windowed = '1' }
    } else {
        [ordered]@{
            BlueLight = '1'
            windowed = '1'
            resmode = '1'
            driver = '1'
            Specularity = '0'
        }
    }
    foreach ($entry in $rendererSettings.GetEnumerator()) {
        $pattern = "(?im)^$([regex]::Escape($entry.Key))=.*$"
        if ($ini -match $pattern) {
            $ini = [regex]::Replace($ini, $pattern, "$($entry.Key)=$($entry.Value)")
        } else {
            $ini = [regex]::Replace(
                $ini,
                '(?im)^\[3D\]\s*$',
                "[3D]`r`n$($entry.Key)=$($entry.Value)",
                1
            )
        }
    }
    Set-Content -LiteralPath $iniPath -Value $ini -Encoding ascii -NoNewline
    Write-Host $(if ($WindowedOnly) {
        'Applied windowed mode only.'
    } else {
        'Applied Windows 8.1/10 fix renderer settings.'
    })
}

$logPath = Join-Path $root 'UnhandledException.log'
$logBefore = if (Test-Path -LiteralPath $logPath) {
    (Get-Item -LiteralPath $logPath).LastWriteTimeUtc
} else {
    $null
}

Write-Host "Launching: $executable"
Write-Host "Working directory: $root"
if (-not $UseShellStart) {
    # SFC3 can fault in USER32!DispatchMessageW when invoked through the
    # Windows shell on current Windows versions. FadedSpark's launcher avoids
    # that path by using direct process creation with an explicit working
    # directory; live testing confirmed that these semantics reach the menu.
    $startInfo = [System.Diagnostics.ProcessStartInfo]::new()
    $startInfo.FileName = $executable
    $startInfo.WorkingDirectory = $root
    $startInfo.UseShellExecute = $false

    $process = [System.Diagnostics.Process]::new()
    $process.StartInfo = $startInfo
    if (-not $process.Start()) {
        throw 'SFC3 process creation returned false.'
    }
    Write-Host 'Start method: launcher-compatible direct process creation'
} else {
    $process = Start-Process -FilePath $executable -WorkingDirectory $root -PassThru
    Write-Host 'Start method: Windows shell (diagnostic fallback)'
}
Write-Host "SFC3 process ID: $($process.Id)"

if ($Wait) {
    $process.WaitForExit()
    Write-Host "SFC3 exit code: $($process.ExitCode)"
    $logAfter = if (Test-Path -LiteralPath $logPath) {
        (Get-Item -LiteralPath $logPath).LastWriteTimeUtc
    } else {
        $null
    }
    if ($logAfter -and $logAfter -ne $logBefore) {
        Write-Warning "SFC3 wrote a new exception log: $logPath"
    }
}
