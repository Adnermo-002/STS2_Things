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

    [string]$HoursmodDll,

    [string]$GodotExe = $env:GODOT_4_5_1_MONO
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$ProbeRoot = Join-Path $Root 'tools\ThingsModelIdProbe'
$ProbeProject = Join-Path $ProbeRoot 'ThingsModelIdProbe.csproj'

if ([string]::IsNullOrWhiteSpace($GodotExe)) {
    $GodotExe = 'D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe'
}

foreach ($requiredPath in @($ProbeProject, $ImplementationDll, $Pck, (Join-Path $DataDir 'sts2.dll'))) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required ModelId namespace probe input was not found: $requiredPath"
    }
}
if (-not (Test-Path -LiteralPath $RuntimeDependencyDir -PathType Container)) {
    throw "Probe runtime dependency directory was not found: $RuntimeDependencyDir"
}
if (-not (Test-Path -LiteralPath $GodotExe -PathType Leaf)) {
    throw "Godot 4.5.1 Mono console executable was not found: $GodotExe"
}
if (-not [string]::IsNullOrWhiteSpace($HoursmodDll) -and
    -not (Test-Path -LiteralPath $HoursmodDll -PathType Leaf)) {
    throw "Actual Hoursmod DLL was not found: $HoursmodDll"
}

$DataDir = [IO.Path]::GetFullPath($DataDir)
$ImplementationDll = [IO.Path]::GetFullPath($ImplementationDll)
$RuntimeDependencyDir = [IO.Path]::GetFullPath($RuntimeDependencyDir)
$Pck = [IO.Path]::GetFullPath($Pck)
$GodotExe = [IO.Path]::GetFullPath($GodotExe)
if (-not [string]::IsNullOrWhiteSpace($HoursmodDll)) {
    $HoursmodDll = [IO.Path]::GetFullPath($HoursmodDll)
}

$portableDotnet = Join-Path $Root '.tmp\dotnet9'
if (Test-Path -LiteralPath (Join-Path $portableDotnet 'dotnet.exe') -PathType Leaf) {
    $env:DOTNET_ROOT = $portableDotnet
    $env:DOTNET_MULTILEVEL_LOOKUP = '0'
    $env:DOTNET_ROLL_FORWARD = 'Major'
}

Write-Host "Building ModelId namespace probe for $TargetVersion..."
& dotnet build $ProbeProject -t:Rebuild -c Debug --nologo `
    "/p:Sts2DataDir=$DataDir" `
    "/p:RuntimeDependencyDir=$RuntimeDependencyDir" `
    "/p:ImplementationDll=$ImplementationDll"
if ($LASTEXITCODE -ne 0) {
    throw "ModelId namespace probe build failed for $TargetVersion with exit code $LASTEXITCODE"
}

$logPath = Join-Path $ProbeRoot "probe-$TargetVersion.log"
if (Test-Path -LiteralPath $logPath -PathType Leaf) {
    Remove-Item -LiteralPath $logPath -Force
}

Write-Host "Running ModelId namespace probe for $TargetVersion..."
$probeArgs = @($Pck)
if (-not [string]::IsNullOrWhiteSpace($HoursmodDll)) {
    $probeArgs += $HoursmodDll
}
& $GodotExe --headless --path $ProbeRoot --log-file $logPath -- $probeArgs
if ($LASTEXITCODE -ne 0) {
    throw "ModelId namespace probe failed for $TargetVersion with exit code $LASTEXITCODE"
}
if (-not (Test-Path -LiteralPath $logPath -PathType Leaf)) {
    throw "ModelId namespace probe log was not created: $logPath"
}

$logText = Get-Content -LiteralPath $logPath -Raw
$errors = Select-String -LiteralPath $logPath `
    -Pattern '(^|\s)(SCRIPT ERROR|ERROR:|WARNING:)|Failed loading resource' `
    -CaseSensitive:$false
if ($errors) {
    $preview = ($errors | Select-Object -First 16 | ForEach-Object Line) -join [Environment]::NewLine
    throw "ModelId namespace probe reported errors for ${TargetVersion}:`n$preview"
}
if ($logText.IndexOf('Things ModelId namespace probe: PASS', [StringComparison]::Ordinal) -lt 0) {
    throw "ModelId namespace probe did not report PASS for $TargetVersion."
}

Write-Host "ModelId namespace probe passed for $TargetVersion."
