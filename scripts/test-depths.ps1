[CmdletBinding()]
param(
    [ValidateSet('v107.1','v111')][string]$TargetVersion='v111',
    [string]$DataDir='D:\Steam\steamapps\common\Slay the Spire 2\data_sts2_windows_x86_64',
    [string]$RuntimeDependencyDir='D:\Steam\steamapps\common\Slay the Spire 2\data_sts2_windows_x86_64',
    [string]$GodotExe='D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe',
    [string]$ImplementationDll='',
    [string]$PackagePck='',
    [string]$OutputDir='',
    [switch]$Visual,
    [switch]$VarietyVisual,
    [switch]$EffectsOnly,
    [switch]$ColumnVariantsOnly,
    [switch]$ColumnRulesOnly,
    [switch]$CampOnly,
    [switch]$BalanceOnly,
    [switch]$FleetingEchoOnly
)
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$taskProbe=Join-Path $taskRoot 'tools\DepthsProbe'
$taskOut=Join-Path $taskRoot 'build\depths'
if($OutputDir){$taskOut=[IO.Path]::GetFullPath($OutputDir)}
$env:THINGS_PROBE_OUTPUT=$taskOut
New-Item -ItemType Directory -Force -Path $taskOut | Out-Null
$taskDll=if($ImplementationDll){[IO.Path]::GetFullPath($ImplementationDll)}else{Join-Path $taskRoot "build\depths\$TargetVersion\STS2_Things.dll"}
if($PackagePck){$env:THINGS_PROBE_PCK=[IO.Path]::GetFullPath($PackagePck)}
$DataDir=[IO.Path]::GetFullPath($DataDir)
$RuntimeDependencyDir=[IO.Path]::GetFullPath($RuntimeDependencyDir)
$env:PATH='C:\Program Files\dotnet;'+$env:PATH
& dotnet build (Join-Path $taskProbe 'DepthsProbe.csproj') -c Debug --nologo "/p:Sts2TargetVersion=$TargetVersion" "/p:Sts2DataDir=$DataDir" "/p:RuntimeDependencyDir=$RuntimeDependencyDir" "/p:ImplementationDll=$taskDll"
if($LASTEXITCODE -ne 0){throw 'Depths probe compilation failed.'}
if(Test-Path (Join-Path $taskRoot '.tmp\dotnet9')){$env:DOTNET_ROOT=Join-Path $taskRoot '.tmp\dotnet9';$env:DOTNET_MULTILEVEL_LOOKUP='0'}
$taskMode=if($ColumnRulesOnly){'column-rules'}elseif($BalanceOnly){'balance'}elseif($FleetingEchoOnly){'fleeting-echo'}elseif($ColumnVariantsOnly){'column-variants'}elseif($EffectsOnly){'effects'}elseif($CampOnly){'camp'}elseif($VarietyVisual){'variety-visual'}elseif($Visual){'visual'}else{"probe-$TargetVersion"}
$taskArgs=@('--path',('"'+$taskProbe+'"'),'--rendering-method','gl_compatibility')
if($ColumnRulesOnly){$taskArgs+=@('--','--column-rules-only')}elseif($BalanceOnly){$taskArgs+=@('--','--balance-only')}elseif($FleetingEchoOnly){$taskArgs+=@('--','--fleeting-echo-only')}elseif($ColumnVariantsOnly){$taskArgs+=@('--','--column-variants-only')}elseif($EffectsOnly){$taskArgs+=@('--','--effects-only')}elseif($CampOnly){$taskArgs+=@('--','--camp-only')}elseif($VarietyVisual){$taskArgs+=@('--','--variety-visual')}elseif($Visual){$taskArgs+=@('--','--visual')}
$taskStdout=Join-Path $taskOut "$taskMode.stdout.log"
$taskStderr=Join-Path $taskOut "$taskMode.stderr.log"
$taskProcess=Start-Process -FilePath $GodotExe -ArgumentList $taskArgs -WindowStyle Hidden -PassThru -RedirectStandardOutput $taskStdout -RedirectStandardError $taskStderr
try{
    $taskStarted=Get-Date
    while(-not $taskProcess.WaitForExit(45000)){
        Write-Host 'Native chapter checks are running...'
        if(((Get-Date)-$taskStarted).TotalSeconds -gt 240){throw 'Depths probe timed out.'}
    }
    if($taskProcess.ExitCode -ne 0){throw 'Depths probe failed.'}
}finally{
    if(-not $taskProcess.HasExited){Stop-Process -InputObject $taskProcess}
    $taskProcess.Dispose()
}
Get-Content $taskStdout -Tail 6
if(Select-String $taskStderr -Pattern '^ERROR:|SCRIPT ERROR' -Quiet){throw "Engine error; see $taskStderr"}
if(-not (Select-String $taskStdout -Pattern 'Depths .*probe: PASS' -Quiet)){throw 'Missing PASS marker.'}
