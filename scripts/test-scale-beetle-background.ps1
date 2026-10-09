[CmdletBinding()]
param(
    [string]$ImplementationDll='build/leech_mother/v111/STS2_Things.dll',
    [string]$PackagePck='build/scale-beetle-background-20261009/package/STS2_Things.pck',
    [string]$OutputDir='build/scale-beetle-background-20261009/native'
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$env:PATH='C:/Program Files/dotnet;'+$env:PATH
& dotnet build (Join-Path $root 'tools/ScaleBeetleBackgroundProbe/ScaleBeetleBackgroundProbe.csproj') -c Debug --nologo "/p:ImplementationDll=$([IO.Path]::GetFullPath($ImplementationDll))" "/p:Sts2TargetVersion=v111"
if($LASTEXITCODE -ne 0){throw 'Background probe build failed'}
$env:DOTNET_ROOT=Join-Path $root '.tmp/dotnet9';$env:DOTNET_MULTILEVEL_LOOKUP='0'
$env:THINGS_PROBE_PCK=[IO.Path]::GetFullPath($PackagePck)
$env:THINGS_PROBE_OUTPUT=[IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Path $env:THINGS_PROBE_OUTPUT -Force | Out-Null
$arguments=@('--path',('"'+(Join-Path $root 'tools/ScaleBeetleBackgroundProbe')+'"'),'--rendering-method','gl_compatibility')
$logRoot=Split-Path -Parent $env:THINGS_PROBE_OUTPUT
$stdout=Join-Path $logRoot 'native.stdout.log';$stderr=Join-Path $logRoot 'native.stderr.log'
$godot='D:/Download/Godot_v4.5.1-stable_mono_win64/Godot_v4.5.1-stable_mono_win64/Godot_v4.5.1-stable_mono_win64_console.exe'
$process=Start-Process -FilePath $godot -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
try {
    if(-not $process.WaitForExit(45000)){throw 'Background probe timed out'}
    if($process.ExitCode -ne 0 -or (Select-String -LiteralPath $stderr -Pattern '^ERROR:|SCRIPT ERROR:' -Quiet)){
        Get-Content -LiteralPath $stderr -TotalCount 20
        throw 'Background native render failed'
    }
    if(-not (Select-String -LiteralPath $stdout -Pattern 'Scale Beetle background probe: PASS' -Quiet)){throw 'Missing result marker'}
    Get-Content -LiteralPath $stdout -Tail 5
} finally {
    if(-not $process.HasExited){Stop-Process -InputObject $process}
    $process.Dispose()
}
