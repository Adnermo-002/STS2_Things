[CmdletBinding()]
param(
    [ValidateSet('v107.1','v111')][string]$TargetVersion='v107.1',
    [string]$ImplementationDll='',
    [string]$PackagePck='',
    [string]$OutputDir='build/human-face-column-update-20261007/native'
)
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$dataDir=if($TargetVersion -eq 'v111'){'D:\Steam\steamapps\common\Slay the Spire 2\data_sts2_windows_x86_64'}else{Join-Path $taskRoot '.tmp/things-collision-v107-data'}
$taskProbe=Join-Path $taskRoot ('.tmp/column-rules-'+$TargetVersion.Replace('.','-'))
$taskOut=[IO.Path]::GetFullPath((Join-Path $taskRoot $OutputDir))
if(-not $ImplementationDll){$ImplementationDll=Join-Path $taskRoot "build/$TargetVersion/STS2_Things.dll"}
if(-not $PackagePck){$PackagePck=Join-Path $taskRoot 'build/unified/STS2_Things.pck'}
New-Item -ItemType Directory -Path $taskProbe,$taskOut -Force | Out-Null
Get-ChildItem -LiteralPath (Join-Path $taskRoot 'tools/DepthsProbe') -File |
    Where-Object {$_.Extension -in '.cs','.csproj','.tscn' -or $_.Name -eq 'project.godot'} |
    ForEach-Object {Copy-Item -LiteralPath $_.FullName -Destination (Join-Path $taskProbe $_.Name)}
$assemblyName='ColumnRulesProbe'+$TargetVersion.Replace('.','').Replace('-','')
$taskProject=Join-Path $taskProbe 'DepthsProbe.csproj'
$text=Get-Content -LiteralPath $taskProject -Raw
Set-Content -LiteralPath $taskProject -Value $text.Replace('<AssemblyName>DepthsProbe</AssemblyName>',"<AssemblyName>$assemblyName</AssemblyName>") -Encoding utf8
$taskGodotProject=Join-Path $taskProbe 'project.godot'
$text=Get-Content -LiteralPath $taskGodotProject -Raw
Set-Content -LiteralPath $taskGodotProject -Value $text.Replace('project/assembly_name="DepthsProbe"',('project/assembly_name="'+$assemblyName+'"')) -Encoding utf8
$env:PATH='C:\Program Files\dotnet;'+$env:PATH
& dotnet build $taskProject -t:Rebuild -c Debug --nologo "/p:Sts2TargetVersion=$TargetVersion" "/p:Sts2DataDir=$dataDir" "/p:RuntimeDependencyDir=D:\Steam\steamapps\common\Slay the Spire 2\data_sts2_windows_x86_64" "/p:ImplementationDll=$([IO.Path]::GetFullPath($ImplementationDll))"
if($LASTEXITCODE -ne 0){throw 'Isolated column probe failed to compile.'}
$env:DOTNET_ROOT=Join-Path $taskRoot '.tmp/dotnet9'
$env:DOTNET_MULTILEVEL_LOOKUP='0'
$env:THINGS_PROBE_OUTPUT=$taskOut
$env:THINGS_PROBE_PCK=[IO.Path]::GetFullPath($PackagePck)
$taskLog=Join-Path $taskOut 'column-rules.log'
& 'D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe' --headless --path $taskProbe --rendering-method gl_compatibility --log-file $taskLog -- --column-rules-only
if($LASTEXITCODE -ne 0){throw 'Native column rules failed.'}
$text=Get-Content -LiteralPath $taskLog -Raw
if($text -match '(?m)^ERROR:|SCRIPT ERROR:' -or $text -notmatch 'Depths column rules probe: PASS'){throw 'Native column log did not pass cleanly.'}
