[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('v107.1', 'v110')]
    [string]$TargetVersion,

    [Parameter(Mandatory = $true)]
    [string]$DataDir,

    [Parameter(Mandatory = $true)]
    [string]$ImplementationDll,

    [Parameter(Mandatory = $true)]
    [string]$RuntimeDependencyDir,

    [string]$GodotExe = $env:GODOT_4_5_1_MONO
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$ProbeRoot = Join-Path $Root 'tools\ThingsCollisionProbe'
$ProbeProject = Join-Path $ProbeRoot 'ThingsCollisionProbe.csproj'

function Resolve-GodotConsoleExecutable([string]$Requested) {
    $candidates = @()
    if (-not [string]::IsNullOrWhiteSpace($Requested)) {
        $candidates += $Requested
    }
    $candidates += @(
        'D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe',
        'D:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe'
    )
    foreach ($candidate in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    throw 'Godot 4.5.1 Mono console executable was not found.'
}

foreach ($requiredPath in @($ProbeProject, $ImplementationDll, (Join-Path $DataDir 'sts2.dll'))) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required Things Collision probe input was not found: $requiredPath"
    }
}

$DataDir = [IO.Path]::GetFullPath($DataDir)
$ImplementationDll = [IO.Path]::GetFullPath($ImplementationDll)
$RuntimeDependencyDir = [IO.Path]::GetFullPath($RuntimeDependencyDir)
$GodotExe = Resolve-GodotConsoleExecutable $GodotExe

$portableDotnet = Join-Path $Root '.tmp\dotnet9'
if (Test-Path -LiteralPath (Join-Path $portableDotnet 'dotnet.exe') -PathType Leaf) {
    $env:DOTNET_ROOT = $portableDotnet
    $env:DOTNET_MULTILEVEL_LOOKUP = '0'
    $env:DOTNET_ROLL_FORWARD = 'Major'
}

Write-Host "Building Things Collision behavior probe for $TargetVersion..."
& dotnet build $ProbeProject -t:Rebuild -c Debug --nologo `
    "/p:Sts2DataDir=$DataDir" `
    "/p:RuntimeDependencyDir=$RuntimeDependencyDir" `
    "/p:ImplementationDll=$ImplementationDll"
if ($LASTEXITCODE -ne 0) {
    throw "Things Collision probe build failed for $TargetVersion with exit code $LASTEXITCODE"
}

$logPath = Join-Path $ProbeRoot "probe-$TargetVersion.log"
if (Test-Path -LiteralPath $logPath -PathType Leaf) {
    Remove-Item -LiteralPath $logPath -Force
}

Write-Host "Running Things Collision behavior probe for $TargetVersion..."
& $GodotExe --headless --path $ProbeRoot --log-file $logPath
if ($LASTEXITCODE -ne 0) {
    throw "Things Collision behavior probe failed for $TargetVersion with exit code $LASTEXITCODE"
}

$logText = Get-Content -LiteralPath $logPath -Raw
$errors = Select-String -LiteralPath $logPath `
    -Pattern '(^|\s)(SCRIPT ERROR|ERROR:|WARNING:)|Failed loading resource' `
    -CaseSensitive:$false
if ($errors) {
    $preview = ($errors | Select-Object -First 12 | ForEach-Object Line) -join [Environment]::NewLine
    throw "Things Collision probe reported errors for ${TargetVersion}:`n$preview"
}
if ($logText.IndexOf('Things Collision behavior probe: PASS', [StringComparison]::Ordinal) -lt 0) {
    throw "Things Collision probe did not report PASS for $TargetVersion."
}

Write-Host "Things Collision behavior probe passed for $TargetVersion."
