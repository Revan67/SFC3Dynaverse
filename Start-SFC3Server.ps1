[CmdletBinding()]
param(
    [string]$ServerAddress = '192.168.0.55',
    [string]$AssetRoot = 'D:\Games\GOG\Star Trek SFC3\Assets',
    [string]$PythonPath = 'C:\Program Files\Python314\python.exe'
)

$ErrorActionPreference = 'Stop'
$repoRoot = $PSScriptRoot
$serverRoot = Join-Path $repoRoot 'server'
$envPath = Join-Path $serverRoot '.env'
$logRoot = Join-Path $serverRoot 'logs'

if (-not (Test-Path -LiteralPath $PythonPath -PathType Leaf)) {
    throw "Python was not found at '$PythonPath'. Pass -PythonPath with the correct location."
}
if (-not (Test-Path -LiteralPath $envPath -PathType Leaf)) {
    throw "Private configuration is missing: '$envPath'. See server\.env.example."
}
if (-not (Test-Path -LiteralPath (Join-Path $AssetRoot 'Specs\DefaultCore.txt'))) {
    throw "DefaultCore.txt was not found beneath '$AssetRoot'."
}
if (-not (Test-Path -LiteralPath (Join-Path $AssetRoot 'Specs\DefaultLoadOut.txt'))) {
    throw "DefaultLoadOut.txt was not found beneath '$AssetRoot'."
}

# Import only SFC3 variables. Values are never echoed, especially SFC3_GT2_KEY.
foreach ($line in Get-Content -LiteralPath $envPath) {
    if ($line -match '^\s*(SFC3_[A-Z0-9_]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($Matches[1], $Matches[2].Trim(), 'Process')
    }
}
if ([string]::IsNullOrWhiteSpace($env:SFC3_GT2_KEY)) {
    throw 'SFC3_GT2_KEY is missing or empty in server\.env.'
}

$env:SFC3_SERVER_HOST = $ServerAddress
$env:SFC3_BIND_HOSTS = "127.0.0.1,$ServerAddress"
$env:SFC3_ADVERTISE_HOST = $ServerAddress
$env:SFC3_ASSET_ROOT = $AssetRoot

$requiredListeners = @(
    @{ Address = '127.0.0.1'; Port = 29900 },
    @{ Address = '127.0.0.1'; Port = 29901 },
    @{ Address = $ServerAddress; Port = 29900 },
    @{ Address = $ServerAddress; Port = 29901 },
    @{ Address = '127.0.0.1'; Port = 26100 },
    @{ Address = '127.0.0.1'; Port = 27632 },
    @{ Address = '127.0.0.1'; Port = 28900 },
    @{ Address = $ServerAddress; Port = 26100 },
    @{ Address = $ServerAddress; Port = 27632 },
    @{ Address = $ServerAddress; Port = 28900 }
)
foreach ($listener in $requiredListeners) {
    $occupied = Get-NetTCPConnection -State Listen -LocalAddress $listener.Address `
        -LocalPort $listener.Port -ErrorAction SilentlyContinue
    if ($occupied) {
        throw "TCP $($listener.Address):$($listener.Port) is already in use by PID $($occupied.OwningProcess). The server may already be running."
    }
}

New-Item -ItemType Directory -Path $logRoot -Force | Out-Null
$processes = [System.Collections.Generic.List[object]]::new()

function Start-SFC3Component {
    param(
        [string]$Name,
        [string[]]$Arguments,
        [hashtable]$EnvironmentOverrides = @{}
    )

    foreach ($entry in $EnvironmentOverrides.GetEnumerator()) {
        [Environment]::SetEnvironmentVariable($entry.Key, $entry.Value, 'Process')
    }
    $stdout = Join-Path $logRoot "$Name.stdout.log"
    $stderr = Join-Path $logRoot "$Name.stderr.log"
    $process = Start-Process -FilePath $PythonPath -ArgumentList $Arguments `
        -WorkingDirectory $repoRoot -RedirectStandardOutput $stdout `
        -RedirectStandardError $stderr -WindowStyle Hidden -PassThru
    $processes.Add([pscustomobject]@{ Name = $Name; Process = $process })
}

try {
    Start-SFC3Component -Name 'gamespy-loopback' `
        -Arguments @('server\probe.py', '29900', '29901') `
        -EnvironmentOverrides @{ SFC3_SERVER_HOST = '127.0.0.1' }

    if ($ServerAddress -ne '127.0.0.1') {
        Start-SFC3Component -Name 'gamespy-lan' `
            -Arguments @('server\probe.py', '29900', '29901') `
            -EnvironmentOverrides @{ SFC3_SERVER_HOST = $ServerAddress }
    }

    Start-SFC3Component -Name 'dynaverse' `
        -Arguments @('server\server.py') `
        -EnvironmentOverrides @{
            SFC3_SERVER_HOST = $ServerAddress
            SFC3_BIND_HOSTS = "127.0.0.1,$ServerAddress"
            SFC3_ADVERTISE_HOST = $ServerAddress
            SFC3_ASSET_ROOT = $AssetRoot
        }

    Start-Sleep -Seconds 1
    foreach ($component in $processes) {
        if ($component.Process.HasExited) {
            throw "$($component.Name) exited during startup. Check '$logRoot'."
        }
    }
}
catch {
    foreach ($component in $processes) {
        if (-not $component.Process.HasExited) {
            Stop-Process -Id $component.Process.Id -Force -ErrorAction SilentlyContinue
        }
    }
    throw
}

Write-Host 'SFC3 replacement services started:'
foreach ($component in $processes) {
    Write-Host ("  {0,-18} PID {1}" -f $component.Name, $component.Process.Id)
}
Write-Host "Logs: $logRoot"
Write-Host "Advertised Dynaverse address: ${ServerAddress}:27633"
