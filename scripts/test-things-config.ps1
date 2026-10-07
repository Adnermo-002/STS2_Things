[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('v107.1', 'v111')]
    [string]$TargetVersion,

    [Parameter(Mandatory = $true)]
    [string]$DataDir,

    [Parameter(Mandatory = $true)]
    [string]$ImplementationDll,

    [Parameter(Mandatory = $true)]
    [string]$RuntimeDependencyDir,

    [Parameter(Mandatory = $true)]
    [string]$Pck,

    [string]$NativePck,

    [switch]$NeowOnly,

    [string]$GodotExe = $env:GODOT_4_5_1_MONO
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$ProbeRoot = Join-Path $Root 'tools\ThingsConfigProbe'
$ProbeProject = Join-Path $ProbeRoot 'ThingsConfigProbe.csproj'

if ([string]::IsNullOrWhiteSpace($GodotExe)) {
    $GodotExe = 'D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe'
}

foreach ($requiredPath in @($ProbeProject, $ImplementationDll, $Pck, (Join-Path $DataDir 'sts2.dll'))) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required config probe input was not found: $requiredPath"
    }
}
if (-not (Test-Path -LiteralPath $RuntimeDependencyDir -PathType Container)) {
    throw "Probe runtime dependency directory was not found: $RuntimeDependencyDir"
}
if (-not (Test-Path -LiteralPath $GodotExe -PathType Leaf)) {
    throw "Godot 4.5.1 Mono console executable was not found: $GodotExe"
}

$DataDir = [IO.Path]::GetFullPath($DataDir)
$ImplementationDll = [IO.Path]::GetFullPath($ImplementationDll)
$RuntimeDependencyDir = [IO.Path]::GetFullPath($RuntimeDependencyDir)
$Pck = [IO.Path]::GetFullPath($Pck)
$GodotExe = [IO.Path]::GetFullPath($GodotExe)
if ([string]::IsNullOrWhiteSpace($NativePck)) {
    $NativePck = Join-Path (Split-Path $RuntimeDependencyDir -Parent) 'SlayTheSpire2.pck'
}
if (-not (Test-Path -LiteralPath $NativePck -PathType Leaf)) {
    throw "Native localization pack was not found: $NativePck"
}
$env:STS2_NEOW_NATIVE_PCK = [IO.Path]::GetFullPath($NativePck)

$portableDotnet = Join-Path $Root '.tmp\dotnet9'
if (Test-Path -LiteralPath (Join-Path $portableDotnet 'dotnet.exe') -PathType Leaf) {
    $env:DOTNET_ROOT = $portableDotnet
    $env:DOTNET_MULTILEVEL_LOOKUP = '0'
    $env:DOTNET_ROLL_FORWARD = 'Major'
}

Write-Host "Building config probe for $TargetVersion..."
& dotnet build $ProbeProject -t:Rebuild -c Debug --nologo `
    "/p:Sts2TargetVersion=$TargetVersion" `
    "/p:Sts2DataDir=$DataDir" `
    "/p:RuntimeDependencyDir=$RuntimeDependencyDir" `
    "/p:ImplementationDll=$ImplementationDll"
if ($LASTEXITCODE -ne 0) {
    throw "Config probe build failed for $TargetVersion with exit code $LASTEXITCODE"
}

$logName = if ($NeowOnly) { "neow-$TargetVersion.log" } else { "probe-$TargetVersion.log" }
$logPath = Join-Path $ProbeRoot $logName
if (Test-Path -LiteralPath $logPath -PathType Leaf) {
    Remove-Item -LiteralPath $logPath -Force
}

Write-Host "Running config probe for $TargetVersion..."
$probeArgs = @($Pck)
if ($NeowOnly) { $probeArgs += '--neow-only' }
& $GodotExe --headless --path $ProbeRoot --log-file $logPath -- @probeArgs
if ($LASTEXITCODE -ne 0) {
    throw "Config probe failed for $TargetVersion with exit code $LASTEXITCODE"
}
if (-not (Test-Path -LiteralPath $logPath -PathType Leaf)) {
    throw "Config probe log was not created: $logPath"
}

$errors = Select-String -LiteralPath $logPath `
    -Pattern '(^|\s)(SCRIPT ERROR|ERROR:|WARNING:)|Failed loading resource' `
    -CaseSensitive:$false
if ($errors) {
    $preview = ($errors | Select-Object -First 16 | ForEach-Object Line) -join [Environment]::NewLine
    throw "Config probe reported errors for ${TargetVersion}:`n$preview"
}
$logText = Get-Content -LiteralPath $logPath -Raw
$successMarker = if ($NeowOnly) { 'Things Neow probe: PASS' } else { 'Things config probe: PASS' }
if ($logText.IndexOf($successMarker, [StringComparison]::Ordinal) -lt 0) {
    throw "Config probe did not report PASS for $TargetVersion."
}

Write-Host "Config probe passed for $TargetVersion."
