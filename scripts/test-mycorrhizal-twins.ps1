[CmdletBinding()]
param(
    [ValidateSet('v107.1','v111')][string]$TargetVersion='v111',
    [string]$ImplementationDll='',
    [string]$PackagePck='',
    [string]$OutputDir='',
    [switch]$Visual,
    [switch]$Motion,
    [switch]$CardVfx
)
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskBuild=Join-Path $taskRoot 'build\mycorrhizal_twins'
if($OutputDir){$taskBuild=[IO.Path]::GetFullPath($OutputDir)}
$env:THINGS_PROBE_OUTPUT=$taskBuild
$taskProbe=Join-Path $taskRoot 'tools\MycorrhizalTwinsProbe'
$taskData=if($TargetVersion -eq 'v107.1'){Join-Path $taskRoot '.tmp\things-collision-v107-data'}else{'D:\Steam\steamapps\common\Slay the Spire 2\data_sts2_windows_x86_64'}
$taskGodot='D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe'
$env:PATH='C:\Program Files\dotnet;'+$env:PATH
New-Item -ItemType Directory -Path $taskBuild -Force | Out-Null
if(-not $ImplementationDll){
    & dotnet build (Join-Path $taskRoot 'STS2_Things.csproj') -c Release --nologo -o (Join-Path $taskBuild $TargetVersion) "/p:Sts2TargetVersion=$TargetVersion" "/p:Sts2DataDir=$taskData"
    if($LASTEXITCODE -ne 0){throw 'Twins implementation compile failed'}
    $ImplementationDll=Join-Path $taskBuild "$TargetVersion\STS2_Things.dll"
}
$ImplementationDll=[IO.Path]::GetFullPath($ImplementationDll)
if($PackagePck){$env:THINGS_PROBE_PCK=[IO.Path]::GetFullPath($PackagePck)}
& dotnet build (Join-Path $taskProbe 'MycorrhizalTwinsProbe.csproj') -c Debug --nologo "/p:Sts2TargetVersion=$TargetVersion" "/p:Sts2DataDir=$taskData" "/p:ImplementationDll=$ImplementationDll"
if($LASTEXITCODE -ne 0){throw 'Twins probe compile failed'}
$env:DOTNET_ROOT=Join-Path $taskRoot '.tmp\dotnet9';$env:DOTNET_MULTILEVEL_LOOKUP='0'
$taskMode=if($Visual){'visual'}else{"behavior-$TargetVersion"}
$taskStdout=Join-Path $taskBuild "$taskMode.stdout.log";$taskStderr=Join-Path $taskBuild "$taskMode.stderr.log"
$taskArgs=@('--path',('"'+$taskProbe+'"'),'--rendering-method','gl_compatibility')
if($Visual -or $Motion -or $CardVfx){if($TargetVersion -ne 'v111'){throw 'Visual fixture requires v111'};$taskArgs+=@('--','--visual');if($Motion){$taskArgs+='--motion'};if($CardVfx){$taskArgs+='--card-vfx'}}else{$taskArgs+=@('--headless')}
$taskProcess=Start-Process -FilePath $taskGodot -ArgumentList $taskArgs -WindowStyle Hidden -PassThru -RedirectStandardOutput $taskStdout -RedirectStandardError $taskStderr
try{
    $taskStart=Get-Date
    while(-not $taskProcess.WaitForExit(30000)){
        Write-Output 'Native twins checks are running...'
        $taskTimeout=if($Motion){900}else{240}
        if(((Get-Date)-$taskStart).TotalSeconds -gt $taskTimeout){throw 'Twins probe timed out'}
    }
    if($taskProcess.ExitCode -ne 0){Get-Content -LiteralPath $taskStderr -Tail 22;throw 'Twins probe failed'}
}finally{if(-not $taskProcess.HasExited){Stop-Process -InputObject $taskProcess};$taskProcess.Dispose()}
Get-Content -LiteralPath $taskStdout -Tail 7
if(Select-String -LiteralPath $taskStderr -Pattern '^ERROR:|SCRIPT ERROR' -Quiet){throw "Engine errors: $taskStderr"}
if(-not(Select-String -LiteralPath $taskStdout -Pattern 'Mycorrhizal Twins probe: PASS' -Quiet)){throw 'Missing native PASS marker'}
