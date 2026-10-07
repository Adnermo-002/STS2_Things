[CmdletBinding()]
param(
    [string]$PackagePck='',
    [string]$OutputDir=''
)

$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$taskOutput=Join-Path $taskRoot 'build\depths_stone_map'
if($OutputDir){$taskOutput=[IO.Path]::GetFullPath($OutputDir)}
New-Item -ItemType Directory -Path $taskOutput -Force | Out-Null
$env:THINGS_MAP_OUTPUT=$taskOutput
$env:THINGS_MAP_PCK=if($PackagePck){[IO.Path]::GetFullPath($PackagePck)}else{''}
$taskProbe=Join-Path $taskRoot 'tools\DepthsStoneMapProbe'
$taskGodot='D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe'
$taskStdout=Join-Path $taskOutput 'native.stdout.log'
$taskStderr=Join-Path $taskOutput 'native.stderr.log'
$taskProcess=Start-Process -FilePath $taskGodot -ArgumentList @('--path',('"'+$taskProbe+'"'),'--script','res://preview.gd','--rendering-method','gl_compatibility') -WindowStyle Hidden -PassThru -RedirectStandardOutput $taskStdout -RedirectStandardError $taskStderr
try{
    if(-not $taskProcess.WaitForExit(60000)){throw 'Map texture render timed out'}
    if($taskProcess.ExitCode -ne 0){Get-Content $taskStderr -Tail 24;throw 'Map texture render failed'}
}finally{
    if(-not $taskProcess.HasExited){Stop-Process -InputObject $taskProcess}
    $taskProcess.Dispose()
}
Get-Content $taskStdout -Tail 5
if(Select-String $taskStderr -Pattern '^ERROR:|SCRIPT ERROR' -Quiet){Get-Content $taskStderr -Tail 24;throw 'Map renderer logged errors'}
if(-not(Select-String $taskStdout -Pattern 'Depths stone map render: PASS' -Quiet)){throw 'No map render PASS marker'}
