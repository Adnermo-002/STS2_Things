[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$DataDir,

    [Parameter(Mandatory = $true)]
    [string]$ImplementationDll,

    [Parameter(Mandatory = $true)]
    [string]$RuntimeDependencyDir,

    [Parameter(Mandatory = $true)]
    [string]$RitsuLibDll,

    [string]$GodotExe = $env:GODOT_4_5_1_MONO
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$ProbeRoot = Join-Path $Root 'tools\RitsuLibInteropProbe'
$ProbeProject = Join-Path $ProbeRoot 'RitsuLibInteropProbe.csproj'

if ([string]::IsNullOrWhiteSpace($GodotExe)) {
    $GodotExe = 'D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe'
}

foreach ($requiredPath in @($ProbeProject, $ImplementationDll, $RitsuLibDll, (Join-Path $DataDir 'sts2.dll'))) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required RitsuLib interop probe input was not found: $requiredPath"
    }
}
if (-not (Test-Path -LiteralPath $RuntimeDependencyDir -PathType Container)) {
    throw "Probe runtime dependency directory was not found: $RuntimeDependencyDir"
}

$DataDir = [IO.Path]::GetFullPath($DataDir)
$ImplementationDll = [IO.Path]::GetFullPath($ImplementationDll)
$RuntimeDependencyDir = [IO.Path]::GetFullPath($RuntimeDependencyDir)
$RitsuLibDll = [IO.Path]::GetFullPath($RitsuLibDll)
$GodotExe = [IO.Path]::GetFullPath($GodotExe)

$portableDotnet = Join-Path $Root '.tmp\dotnet9'
if (Test-Path -LiteralPath (Join-Path $portableDotnet 'dotnet.exe') -PathType Leaf) {
    $env:DOTNET_ROOT = $portableDotnet
    $env:DOTNET_MULTILEVEL_LOOKUP = '0'
    $env:DOTNET_ROLL_FORWARD = 'Major'
}

Write-Host 'Building RitsuLib interop probe...'
& dotnet build $ProbeProject -t:Rebuild -c Debug --nologo `
    "/p:Sts2DataDir=$DataDir" `
    "/p:RuntimeDependencyDir=$RuntimeDependencyDir" `
    "/p:ImplementationDll=$ImplementationDll"
if ($LASTEXITCODE -ne 0) {
    throw "RitsuLib interop probe build failed with exit code $LASTEXITCODE"
}

$logPath = Join-Path $ProbeRoot 'probe.log'
if (Test-Path -LiteralPath $logPath -PathType Leaf) {
    Remove-Item -LiteralPath $logPath -Force
}

Write-Host 'Running RitsuLib interop probe...'
& $GodotExe --headless --path $ProbeRoot --log-file $logPath -- @($RitsuLibDll)
if ($LASTEXITCODE -ne 0) {
    throw "RitsuLib interop probe failed with exit code $LASTEXITCODE"
}
$logText = Get-Content -LiteralPath $logPath -Raw -ErrorAction Stop
if ($logText.IndexOf('RitsuLib interop probe: PASS', [StringComparison]::Ordinal) -lt 0) {
    throw 'RitsuLib interop probe did not report PASS.'
}

Write-Host 'RitsuLib interop probe passed.'
