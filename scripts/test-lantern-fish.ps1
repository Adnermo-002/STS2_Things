[CmdletBinding()]
param(
    [ValidateSet('v107.1','v111')][string]$TargetVersion='v111',
    [string]$DataDir='D:\Steam\steamapps\common\Slay the Spire 2\data_sts2_windows_x86_64',
    [string]$RuntimeDependencyDir='D:\Steam\steamapps\common\Slay the Spire 2\data_sts2_windows_x86_64',
    [string]$GodotExe='D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe',
    [switch]$Visual
)
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$taskDll=Join-Path $taskRoot "build\lantern_fish\$TargetVersion\STS2_Things.dll"
$taskProbe=Join-Path $taskRoot 'tools\LanternFishProbe'
$taskLogs=Join-Path $taskRoot 'build\lantern_fish'
$DataDir=[IO.Path]::GetFullPath($DataDir)
$RuntimeDependencyDir=[IO.Path]::GetFullPath($RuntimeDependencyDir)
$env:PATH='C:\Program Files\dotnet;'+$env:PATH
& dotnet build (Join-Path $taskProbe 'LanternFishProbe.csproj') -c Debug --nologo "/p:Sts2DataDir=$DataDir" "/p:RuntimeDependencyDir=$RuntimeDependencyDir" "/p:ImplementationDll=$taskDll"
if($LASTEXITCODE -ne 0){throw 'Native probe compilation failed.'}
if(Test-Path (Join-Path $taskRoot '.tmp\dotnet9')){
    $env:DOTNET_ROOT=Join-Path $taskRoot '.tmp\dotnet9'
    $env:DOTNET_MULTILEVEL_LOOKUP='0'
}
if($Visual){
    if($TargetVersion -ne 'v111'){throw 'Visual fixture uses the V111 game PCK.'}
    $taskStdout=Join-Path $taskLogs 'visual.stdout.log'
    $taskStderr=Join-Path $taskLogs 'visual.stderr.log'
    $taskProcess=Start-Process -FilePath $GodotExe -ArgumentList @('--path',('"'+$taskProbe+'"'),'--rendering-method','gl_compatibility','--','--visual') -WindowStyle Hidden -PassThru -RedirectStandardOutput $taskStdout -RedirectStandardError $taskStderr
    try{
        $taskStarted=Get-Date
        while(-not $taskProcess.WaitForExit(45000)){
            Write-Host 'Native visual capture is running...'
            if(((Get-Date)-$taskStarted).TotalSeconds -gt 300){throw 'Visual capture timed out.'}
        }
        if($taskProcess.ExitCode -ne 0){throw 'Visual capture failed.'}
    }finally{
        if(-not $taskProcess.HasExited){Stop-Process -InputObject $taskProcess}
        $taskProcess.Dispose()
    }
    if(Select-String $taskStderr -Pattern '^ERROR:|SCRIPT ERROR' -Quiet){throw 'Visual capture logged an engine error.'}
    if(-not (Select-String $taskStdout -Pattern 'Lantern Fish visual probe: PASS' -Quiet)){throw 'No visual PASS marker.'}
    Get-Content $taskStdout -Tail 3
}else{
    $taskLog=Join-Path $taskLogs "behavior-$TargetVersion.log"
    & $GodotExe --headless --path $taskProbe --log-file $taskLog
    if($LASTEXITCODE -ne 0){throw 'Native behavior probe failed.'}
    if(-not (Select-String $taskLog -Pattern 'Lantern Fish behavior probe: PASS' -Quiet)){throw 'No behavior PASS marker.'}
}
