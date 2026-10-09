[CmdletBinding()]
param(
    [ValidateSet('v107.1','v111')][string]$TargetVersion='v111',
    [Parameter(Mandatory)][string]$ImplementationDll,
    [Parameter(Mandatory)][string]$PackagePck,
    [Parameter(Mandatory)][string]$OutputDir,
    [string]$DataDir='',
    [switch]$Visual,
    [switch]$HostMode,
    [switch]$Matrix,
    [switch]$Loopback
)
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskProbe=Join-Path $taskRoot 'tools/PetDeathProbe'
$taskOut=[IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Path $taskOut -Force | Out-Null
if(-not $DataDir){$DataDir=if($TargetVersion -eq 'v111'){'D:/Steam/steamapps/common/Slay the Spire 2/data_sts2_windows_x86_64'}else{Join-Path $taskRoot '.tmp/things-collision-v107-data'}}
$env:PATH='C:/Program Files/dotnet;'+$env:PATH
& dotnet build (Join-Path $taskProbe 'PetDeathProbe.csproj') -c Debug --nologo "/p:Sts2TargetVersion=$TargetVersion" "/p:Sts2DataDir=$([IO.Path]::GetFullPath($DataDir))" "/p:ImplementationDll=$([IO.Path]::GetFullPath($ImplementationDll))"
if($LASTEXITCODE -ne 0){throw 'Pet death probe build failed'}
$env:DOTNET_ROOT=Join-Path $taskRoot '.tmp/dotnet9';$env:DOTNET_MULTILEVEL_LOOKUP='0'
$env:THINGS_PROBE_PCK=[IO.Path]::GetFullPath($PackagePck)
$env:THINGS_PROBE_OUTPUT=$taskOut
$argsList=@('--path',('"'+$taskProbe+'"'),'--rendering-method','gl_compatibility')
if(-not $Visual){$argsList+='--headless'}
if($Visual -or $HostMode -or $Matrix -or $Loopback){$argsList+='--';if($Visual){$argsList+='--visual'};if($HostMode){$argsList+='--host'};if($Matrix){$argsList+='--matrix'};if($Loopback){$argsList+='--loopback'}}
$taskExe='D:/Download/Godot_v4.5.1-stable_mono_win64/Godot_v4.5.1-stable_mono_win64/Godot_v4.5.1-stable_mono_win64_console.exe'
$taskProcess=Start-Process -FilePath $taskExe -ArgumentList $argsList -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskOut 'probe.stdout.log') -RedirectStandardError (Join-Path $taskOut 'probe.stderr.log')
try {
    if(-not $taskProcess.WaitForExit(45000)){throw 'Pet death probe timed out'}
    Get-Content -LiteralPath (Join-Path $taskOut 'probe.stdout.log') -Tail 10
    if($taskProcess.ExitCode -ne 0 -or (Select-String -LiteralPath (Join-Path $taskOut 'probe.stderr.log') -Pattern '^ERROR:|SCRIPT ERROR:' -Quiet)){
        Get-Content -LiteralPath (Join-Path $taskOut 'probe.stderr.log') -TotalCount 22
        throw 'Pet death probe failed; inspect the captured exception'
    }
    if(-not (Select-String -LiteralPath (Join-Path $taskOut 'probe.stdout.log') -Pattern 'Pet death probe: PASS' -Quiet)){throw 'Missing pass marker'}
} finally {
    if(-not $taskProcess.HasExited){Stop-Process -InputObject $taskProcess}
    $taskProcess.Dispose()
}
