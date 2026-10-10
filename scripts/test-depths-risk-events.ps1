[CmdletBinding()]
param(
    [ValidateSet('v107.1','v111')][string]$TargetVersion='v111',
    [string]$DataDir='D:/Steam/steamapps/common/Slay the Spire 2/data_sts2_windows_x86_64',
    [string]$RuntimeDependencyDir='D:/Steam/steamapps/common/Slay the Spire 2/data_sts2_windows_x86_64',
    [string]$VanillaPck='D:/Steam/steamapps/common/Slay the Spire 2/SlayTheSpire2.pck',
    [string]$ImplementationDll='build/depths-risk-events-20261010/v111/STS2_Things.dll',
    [string]$PackagePck='build/depths-risk-events-20261010/package/STS2_Things.pck',
    [string]$OutputDir='build/depths-risk-events-20261010/native/v111'
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$env:DOTNET_ROOT='C:/Program Files/dotnet'
$env:PATH='C:/Program Files/dotnet;'+$env:PATH
& 'C:/Program Files/dotnet/dotnet.exe' build (Join-Path $root 'tools/DepthsRiskEventsProbe/DepthsRiskEventsProbe.csproj') -c Debug --nologo "/p:ImplementationDll=$([IO.Path]::GetFullPath($ImplementationDll))" "/p:Sts2TargetVersion=$TargetVersion" "/p:Sts2DataDir=$([IO.Path]::GetFullPath($DataDir))" "/p:RuntimeDependencyDir=$([IO.Path]::GetFullPath($RuntimeDependencyDir))"
if($LASTEXITCODE -ne 0){throw 'Relic art probe build failed'}
$env:DOTNET_ROOT=Join-Path $root '.tmp/dotnet9'
$env:DOTNET_MULTILEVEL_LOOKUP='0'
$env:THINGS_VANILLA_PCK=[IO.Path]::GetFullPath($VanillaPck)
$env:THINGS_PROBE_PCK=[IO.Path]::GetFullPath($PackagePck)
$env:THINGS_PROBE_OUTPUT=[IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Path $env:THINGS_PROBE_OUTPUT -Force | Out-Null
$arguments=@('--path',('"'+(Join-Path $root 'tools/DepthsRiskEventsProbe')+'"'),'--rendering-method','gl_compatibility')
$stdout=Join-Path $env:THINGS_PROBE_OUTPUT 'native.stdout.log'
$stderr=Join-Path $env:THINGS_PROBE_OUTPUT 'native.stderr.log'
$godot='D:/Download/Godot_v4.5.1-stable_mono_win64/Godot_v4.5.1-stable_mono_win64/Godot_v4.5.1-stable_mono_win64_console.exe'
$process=Start-Process -FilePath $godot -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
try {
    if(-not $process.WaitForExit(45000)){throw 'Relic art probe timed out'}
    if($process.ExitCode -ne 0 -or (Select-String -LiteralPath $stderr -Pattern '^ERROR:|SCRIPT ERROR:' -Quiet)){
        Get-Content -LiteralPath $stderr -TotalCount 30
        throw 'Native relic render failed'
    }
    if(-not (Select-String -LiteralPath $stdout -Pattern 'Depths risk events probe: PASS' -Quiet)){throw 'Missing result marker'}
    Get-Content -LiteralPath $stdout -Tail 5
} finally {
    if(-not $process.HasExited){Stop-Process -InputObject $process}
    $process.Dispose()
}
