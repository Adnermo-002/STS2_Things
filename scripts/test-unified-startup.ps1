[CmdletBinding()]
param(
    [Parameter(Mandatory)][ValidateSet('v107.1', 'v111')][string]$TargetVersion,
    [Parameter(Mandatory)][string]$DataDir,
    [Parameter(Mandatory)][string]$RuntimeDependencyDir,
    [Parameter(Mandatory)][string]$Package,
    [Parameter(Mandatory)][string]$NativePck,
    [string]$LogPath,
    [switch]$LoadOnly,
    [string]$GodotExe = 'D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe'
)
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$probe = Join-Path $root 'tools\UnifiedStartupProbe'
$env:DOTNET_ROOT = Join-Path $root '.tmp\dotnet9'
$env:DOTNET_MULTILEVEL_LOOKUP = '0'
$env:DOTNET_ROLL_FORWARD = 'Major'
& dotnet build (Join-Path $probe 'UnifiedStartupProbe.csproj') -t:Rebuild -c Debug --nologo `
    "/p:Sts2DataDir=$([IO.Path]::GetFullPath($DataDir))" `
    "/p:RuntimeDependencyDir=$([IO.Path]::GetFullPath($RuntimeDependencyDir))"
if ($LASTEXITCODE -ne 0) { throw 'Unified startup probe build failed.' }
$log = if ($LogPath) { [IO.Path]::GetFullPath($LogPath) } else { Join-Path $root "build\unified-startup\startup-$TargetVersion.log" }
New-Item -ItemType Directory -Path (Split-Path -Parent $log) -Force | Out-Null
$arguments = @([IO.Path]::GetFullPath($Package), [IO.Path]::GetFullPath($NativePck), $TargetVersion)
if ($LoadOnly) { $arguments += '--load-only' }
& $GodotExe --headless --path $probe --log-file $log -- @arguments
if ($LASTEXITCODE -ne 0) { throw "Unified startup probe failed for $TargetVersion." }
$logText = Get-Content -Raw -LiteralPath $log
if ($logText -notmatch 'Unified startup probe: PASS' -or $logText -match '(?m)^ERROR:|SCRIPT ERROR:') {
    throw "Unified startup probe did not pass cleanly for $TargetVersion."
}
