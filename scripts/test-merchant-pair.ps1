[CmdletBinding()]
param(
    [ValidateSet('v107.1','v111')][string]$TargetVersion='v111',
    [Parameter(Mandatory)][string]$GameRoot,
    [Parameter(Mandatory)][string]$ImplementationDll,
    [string]$PackagePck='build/merchant-pair-attack-split-20261010/package/STS2_Things.pck',
    [string]$OutputDir=''
)
$ErrorActionPreference='Stop'
$root=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$data=Join-Path ([IO.Path]::GetFullPath($GameRoot)) 'data_sts2_windows_x86_64'
$env:PATH='C:/Program Files/dotnet;'+$env:PATH
$env:DOTNET_ROOT='C:/Program Files/dotnet'
& 'C:/Program Files/dotnet/dotnet.exe' build (Join-Path $root 'tools/MerchantPairProbe/MerchantPairProbe.csproj') -c Debug --nologo "/p:Sts2TargetVersion=$TargetVersion" "/p:Sts2DataDir=$data" "/p:RuntimeDependencyDir=$data" "/p:ImplementationDll=$([IO.Path]::GetFullPath($ImplementationDll))"
if($LASTEXITCODE -ne 0){throw 'Merchant probe compilation failed'}
$env:DOTNET_ROOT=Join-Path $root '.tmp/dotnet9'
$env:DOTNET_MULTILEVEL_LOOKUP='0'
$env:THINGS_VANILLA_PCK=Join-Path ([IO.Path]::GetFullPath($GameRoot)) 'SlayTheSpire2.pck'
$env:THINGS_PROBE_PCK=[IO.Path]::GetFullPath($PackagePck)
if(-not $OutputDir){$OutputDir=Join-Path $root "build/merchant-pair-attack-split-20261010/native/$TargetVersion"}
$env:THINGS_PROBE_OUTPUT=[IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Path $env:THINGS_PROBE_OUTPUT -Force | Out-Null
$stdout=Join-Path $env:THINGS_PROBE_OUTPUT 'probe.stdout.log'
$stderr=Join-Path $env:THINGS_PROBE_OUTPUT 'probe.stderr.log'
$godot='D:/Download/Godot_v4.5.1-stable_mono_win64/Godot_v4.5.1-stable_mono_win64/Godot_v4.5.1-stable_mono_win64_console.exe'
$arguments=@('--headless','--path',('"'+(Join-Path $root 'tools/MerchantPairProbe')+'"'))
$process=Start-Process -FilePath $godot -ArgumentList $arguments -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
try {
    if(-not $process.WaitForExit(45000)){throw 'Merchant probe timeout'}
    if($process.ExitCode -ne 0 -or (Select-String -LiteralPath $stderr -Pattern '^ERROR:|SCRIPT ERROR:' -Quiet)){
        Get-Content -LiteralPath $stderr -TotalCount 25
        throw 'Merchant probe failed'
    }
    if(-not (Select-String -LiteralPath $stdout -Pattern 'Merchant pair probe: PASS' -Quiet)){throw 'Missing merchant probe result'}
    Get-Content -LiteralPath $stdout -Tail 4
} finally {
    if(-not $process.HasExited){Stop-Process -InputObject $process}
    $process.Dispose()
}
