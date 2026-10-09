[CmdletBinding()]
param(
    [ValidateSet('v107.1','v111')][string]$TargetVersion='v111',
    [string]$ImplementationDll='',
    [string]$PackagePck='',
    [string]$OutputDir='',
    [string]$GodotExe='D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe'
)
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$taskOut=if($OutputDir){[IO.Path]::GetFullPath($OutputDir)}else{Join-Path $taskRoot 'build/leech_mother'}
New-Item -ItemType Directory -Force -Path $taskOut|Out-Null
$taskData=if($TargetVersion -eq 'v107.1'){Join-Path $taskRoot '.tmp/things-collision-v107-data'}else{Join-Path $taskRoot '.tmp/verified-v111-runtime'}
if(-not $ImplementationDll){$ImplementationDll=Join-Path $taskRoot "build/leech_mother/$TargetVersion/STS2_Things.dll"}
$env:PATH='C:/Program Files/dotnet;'+$env:PATH
& dotnet build (Join-Path $taskRoot 'tools/LeechMotherProbe/LeechMotherProbe.csproj') --nologo "/p:Sts2TargetVersion=$TargetVersion" "/p:Sts2DataDir=$taskData" "/p:ImplementationDll=$([IO.Path]::GetFullPath($ImplementationDll))"
if($LASTEXITCODE -ne 0){throw 'Leech Mother probe compile failed'}
if($PackagePck){$env:THINGS_PROBE_PCK=[IO.Path]::GetFullPath($PackagePck)}
$env:DOTNET_ROOT=Join-Path $taskRoot '.tmp/dotnet9';$env:DOTNET_MULTILEVEL_LOOKUP='0'
$taskLog=Join-Path $taskOut "probe-$TargetVersion.stdout.log"
$taskErr=Join-Path $taskOut "probe-$TargetVersion.stderr.log"
$taskProc=Start-Process -FilePath $GodotExe -ArgumentList @('--headless','--path',('"'+(Join-Path $taskRoot 'tools/LeechMotherProbe')+'"'),'--rendering-method','gl_compatibility') -WindowStyle Hidden -PassThru -RedirectStandardOutput $taskLog -RedirectStandardError $taskErr
try{
    $taskStart=Get-Date
    while(-not $taskProc.WaitForExit(30000)){
        Write-Output 'Native mother checks are running...'
        if(((Get-Date)-$taskStart).TotalSeconds -gt 120){throw 'Leech Mother probe timed out'}
    }
    if($taskProc.ExitCode -ne 0){Get-Content -LiteralPath $taskErr -TotalCount 12;throw 'Leech Mother native probe failed'}
}finally{if(-not $taskProc.HasExited){Stop-Process -InputObject $taskProc};$taskProc.Dispose()}
if(Select-String -LiteralPath $taskErr -Pattern '^ERROR:|SCRIPT ERROR' -Quiet){throw 'Leech Mother engine errors'}
if(-not(Select-String -LiteralPath $taskLog -Pattern 'Leech Mother probe: PASS' -Quiet)){throw 'Missing native PASS marker'}
Get-Content -LiteralPath $taskLog -Tail 3
