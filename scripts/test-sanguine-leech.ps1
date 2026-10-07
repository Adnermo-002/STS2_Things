[CmdletBinding()]
param(
    [ValidateSet('v107.1','v111')][string]$TargetVersion='v111',
    [string]$GodotExe='D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe',
    [string]$ImplementationDll='',
    [string]$PackagePck='',
    [string]$OutputDir='',
    [switch]$Visual
)
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$taskBuild=Join-Path $taskRoot 'build\sanguine_leech'
if($OutputDir){$taskBuild=[IO.Path]::GetFullPath($OutputDir)}
New-Item -ItemType Directory -Path $taskBuild -Force | Out-Null
$env:THINGS_PROBE_OUTPUT=$taskBuild
if($PackagePck){$env:THINGS_PROBE_PCK=[IO.Path]::GetFullPath($PackagePck)}
$taskData=if($TargetVersion -eq 'v107.1'){Join-Path $taskRoot '.tmp\things-collision-v107-data'}else{'D:\Steam\steamapps\common\Slay the Spire 2\data_sts2_windows_x86_64'}
$taskProbe=Join-Path $taskRoot 'tools\SanguineLeechProbe'
$env:PATH='C:\Program Files\dotnet;'+$env:PATH
$env:DOTNET_CLI_UI_LANGUAGE='en'
if(-not $ImplementationDll){
    & dotnet build (Join-Path $taskRoot 'STS2_Things.csproj') -c Debug --nologo -o (Join-Path $taskBuild $TargetVersion) "/p:Sts2TargetVersion=$TargetVersion" "/p:Sts2DataDir=$taskData"
    if($LASTEXITCODE -ne 0){throw 'Leech implementation compile failed'}
    $ImplementationDll=Join-Path $taskBuild "$TargetVersion\STS2_Things.dll"
}
$ImplementationDll=[IO.Path]::GetFullPath($ImplementationDll)
& dotnet build (Join-Path $taskProbe 'SanguineLeechProbe.csproj') --nologo "/p:Sts2DataDir=$taskData" "/p:ImplementationDll=$ImplementationDll"
if($LASTEXITCODE -ne 0){throw 'Leech probe compile failed'}
$env:DOTNET_ROOT=Join-Path $taskRoot '.tmp\dotnet9'
$env:DOTNET_MULTILEVEL_LOOKUP='0'
$taskMode=if($Visual){'visual'}else{"behavior-$TargetVersion"}
$taskStdout=Join-Path $taskBuild "$taskMode.stdout.log"
$taskStderr=Join-Path $taskBuild "$taskMode.stderr.log"
$taskArgs=@('--path',('"'+$taskProbe+'"'),'--rendering-method','gl_compatibility')
if($Visual){
    if($TargetVersion -ne 'v111'){throw 'Visual fixture uses the v111 game PCK'}
    $taskArgs+=@('--','--visual')
}else{$taskArgs+=@('--headless')}
$taskProcess=Start-Process -FilePath $GodotExe -ArgumentList $taskArgs -WindowStyle Hidden -PassThru -RedirectStandardOutput $taskStdout -RedirectStandardError $taskStderr
try{
    $taskStarted=Get-Date
    while(-not $taskProcess.WaitForExit(30000)){
        Write-Host 'Sanguine Leech native checks are running...'
        if(((Get-Date)-$taskStarted).TotalSeconds -gt 240){throw 'Leech probe timed out'}
    }
    if($taskProcess.ExitCode -ne 0){throw "Leech probe failed: $taskStderr"}
}finally{
    if(-not $taskProcess.HasExited){Stop-Process -InputObject $taskProcess}
    $taskProcess.Dispose()
}
Get-Content $taskStdout -Tail 8
if(Select-String $taskStderr -Pattern '^ERROR:|SCRIPT ERROR' -Quiet){throw "Native engine errors: $taskStderr"}
if(-not(Select-String $taskStdout -Pattern 'Sanguine Leech probe: PASS' -Quiet)){throw 'Probe has no PASS marker'}
