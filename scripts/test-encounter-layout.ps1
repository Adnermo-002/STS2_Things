[CmdletBinding()]
param(
    [ValidateSet('v107.1', 'v111')][string]$TargetVersion = 'v107.1',
    [Parameter(Mandatory)][string]$DataDir,
    [Parameter(Mandatory)][string]$ImplementationDll,
    [Parameter(Mandatory)][string]$PackagePck,
    [Parameter(Mandatory)][string]$OutputDir,
    [string]$GamePck = 'D:\Steam\steamapps\common\Slay the Spire 2\SlayTheSpire2.pck',
    [string]$GodotExe = 'D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe',
    [string]$Encounter = '',
    [switch]$SourceScenes
)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$taskOut = [IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Force -Path $taskOut | Out-Null
$taskProbe = Join-Path $taskOut 'probe'
New-Item -ItemType Directory -Force -Path $taskProbe | Out-Null
Get-ChildItem -LiteralPath (Join-Path $taskRoot 'tools\DepthsProbe') -File |
    Where-Object Extension -In '.cs', '.csproj', '.godot', '.tscn' |
    ForEach-Object { Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $taskProbe $_.Name) -Force }
$env:THINGS_PROBE_ROOT = $taskRoot
$env:THINGS_PROBE_OUTPUT = $taskOut
$env:THINGS_PROBE_PCK = [IO.Path]::GetFullPath($PackagePck)
$env:THINGS_PROBE_GAME_PCK = [IO.Path]::GetFullPath($GamePck)
$env:THINGS_LAYOUT_SOURCE_SCENES = if ($SourceScenes) { '1' } else { '0' }
$env:THINGS_LAYOUT_ENCOUNTER = $Encounter
& 'C:\Program Files\dotnet\dotnet.exe' build (Join-Path $taskProbe 'DepthsProbe.csproj') -c Debug --nologo "/p:Sts2TargetVersion=$TargetVersion" "/p:Sts2DataDir=$DataDir" "/p:RuntimeDependencyDir=$DataDir" "/p:ImplementationDll=$ImplementationDll"
if ($LASTEXITCODE -ne 0) { throw 'Layout probe compilation failed.' }
$env:DOTNET_ROOT = Join-Path $taskRoot '.tmp\dotnet9'
$env:DOTNET_MULTILEVEL_LOOKUP = '0'
$taskProcess = Start-Process -FilePath $GodotExe -WindowStyle Hidden -PassThru `
    -ArgumentList @('--path', ('"' + $taskProbe + '"'), '--rendering-method', 'gl_compatibility', '--', '--layout-only') `
    -RedirectStandardOutput (Join-Path $taskOut 'stdout.log') -RedirectStandardError (Join-Path $taskOut 'stderr.log')
try {
    $taskStarted = Get-Date
    while (-not $taskProcess.WaitForExit(30000)) {
        Write-Host 'Checking native creature HUD placement...'
        if (((Get-Date) - $taskStarted).TotalSeconds -gt 180) { throw 'Layout probe timed out.' }
    }
    Get-Content -LiteralPath (Join-Path $taskOut 'stdout.log') -Tail 18
    if ($taskProcess.ExitCode -ne 0) {
        Get-Content -LiteralPath (Join-Path $taskOut 'stderr.log') -Tail 12
        throw 'Layout probe failed; see measurements and render captures.'
    }
    if (Select-String -LiteralPath (Join-Path $taskOut 'stderr.log') -Pattern '^ERROR:|SCRIPT ERROR' -Quiet) { throw 'Native rendering logged errors.' }
    if (-not (Select-String -LiteralPath (Join-Path $taskOut 'stdout.log') -Pattern 'Depths encounter layout probe: PASS' -Quiet)) { throw 'Missing layout PASS marker.' }
} finally {
    if (-not $taskProcess.HasExited) { Stop-Process -InputObject $taskProcess }
    $taskProcess.Dispose()
}
