[CmdletBinding()]
param(
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
$ProbeRoot = Join-Path $Root 'tools\MerchantBargainProbe'
$ProbeProject = Join-Path $ProbeRoot 'MerchantBargainProbe.csproj'

if ([string]::IsNullOrWhiteSpace($GodotExe)) {
    $GodotExe = 'D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe'
}

foreach ($requiredPath in @(
    $ProbeProject,
    $ImplementationDll,
    (Join-Path $DataDir 'sts2.dll'),
    (Join-Path $RuntimeDependencyDir 'Sentry.Godot.dll'),
    $GodotExe
)) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required Merchant Bargain probe input was not found: $requiredPath"
    }
}

$DataDir = [IO.Path]::GetFullPath($DataDir)
$ImplementationDll = [IO.Path]::GetFullPath($ImplementationDll)
$RuntimeDependencyDir = [IO.Path]::GetFullPath($RuntimeDependencyDir)
$GodotExe = [IO.Path]::GetFullPath($GodotExe)

$portableDotnet = Join-Path $Root '.tmp\dotnet9'
if (Test-Path -LiteralPath (Join-Path $portableDotnet 'dotnet.exe') -PathType Leaf) {
    $env:DOTNET_ROOT = $portableDotnet
    $env:DOTNET_MULTILEVEL_LOOKUP = '0'
    $env:DOTNET_ROLL_FORWARD = 'Major'
}

Write-Host 'Building Merchant Bargain behavior probe for v110...'
& dotnet build $ProbeProject -t:Rebuild -c Debug --nologo `
    "/p:Sts2DataDir=$DataDir" `
    "/p:RuntimeDependencyDir=$RuntimeDependencyDir" `
    "/p:ImplementationDll=$ImplementationDll"
if ($LASTEXITCODE -ne 0) {
    throw "Merchant Bargain probe build failed with exit code $LASTEXITCODE"
}

$logPath = Join-Path $ProbeRoot 'probe-v110.log'
if (Test-Path -LiteralPath $logPath -PathType Leaf) {
    Remove-Item -LiteralPath $logPath -Force
}

Write-Host 'Running Merchant Bargain behavior probe for v110...'
& $GodotExe --headless --path $ProbeRoot --log-file $logPath
if ($LASTEXITCODE -ne 0) {
    throw "Merchant Bargain behavior probe failed with exit code $LASTEXITCODE"
}
if (-not (Test-Path -LiteralPath $logPath -PathType Leaf)) {
    throw "Merchant Bargain probe log was not created: $logPath"
}

$logText = Get-Content -LiteralPath $logPath -Raw
$errors = Select-String -LiteralPath $logPath `
    -Pattern '(^|\s)(SCRIPT ERROR|ERROR:|WARNING:)|Failed loading resource' `
    -CaseSensitive:$false
if ($errors) {
    $preview = ($errors | Select-Object -First 12 | ForEach-Object Line) -join [Environment]::NewLine
    throw "Merchant Bargain probe reported errors:`n$preview"
}
if ($logText.IndexOf('Merchant bargain behavior probe: PASS', [StringComparison]::Ordinal) -lt 0) {
    throw 'Merchant Bargain probe did not report PASS.'
}

Write-Host 'Merchant Bargain behavior probe passed for v110.'
