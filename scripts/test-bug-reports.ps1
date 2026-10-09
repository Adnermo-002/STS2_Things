param([ValidateSet('v107.1','v111')][string]$TargetVersion='v111')
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$taskOut=Join-Path $taskRoot 'build/bug-report-fix-20261009'
$taskData=Join-Path $taskRoot $(if($TargetVersion -eq 'v111'){'.tmp/verified-v111-runtime'}else{'.tmp/things-collision-v107-data'})
$taskRuntime=Join-Path $taskRoot '.tmp/verified-v111-runtime'
$taskImplementation=Join-Path $taskOut "$TargetVersion/STS2_Things.dll"
& 'C:/Program Files/dotnet/dotnet.exe' build (Join-Path $taskRoot 'STS2_Things.csproj') -c Release --nologo -o (Split-Path $taskImplementation) "/p:Sts2TargetVersion=$TargetVersion" "/p:Sts2DataDir=$taskData"
if($LASTEXITCODE -ne 0){throw 'Report implementation build failed'}
& 'C:/Program Files/dotnet/dotnet.exe' build (Join-Path $taskRoot 'tools/BugReportProbe/BugReportProbe.csproj') --nologo "/p:Sts2TargetVersion=$TargetVersion" "/p:Sts2DataDir=$taskData" "/p:RuntimeDependencyDir=$taskRuntime" "/p:ImplementationDll=$taskImplementation"
if($LASTEXITCODE -ne 0){throw 'Report native probe build failed'}
$env:DOTNET_ROOT=Join-Path $taskRoot '.tmp/dotnet9'
$env:DOTNET_MULTILEVEL_LOOKUP='0'
$env:PATH=$env:DOTNET_ROOT+';'+$env:PATH
$taskGodot='D:/Download/Godot_v4.5.1-stable_mono_win64/Godot_v4.5.1-stable_mono_win64/Godot_v4.5.1-stable_mono_win64_console.exe'
$taskStdout=Join-Path $taskOut "native-$TargetVersion.log"
$taskStderr=Join-Path $taskOut "native-$TargetVersion.stderr.log"
$taskProcess=Start-Process -FilePath $taskGodot -ArgumentList @('--headless','--path',('"'+(Join-Path $taskRoot 'tools/BugReportProbe')+'"')) -WindowStyle Hidden -PassThru -RedirectStandardOutput $taskStdout -RedirectStandardError $taskStderr
try{
  if(-not $taskProcess.WaitForExit(30000)){throw 'Report native probe exceeded 30 seconds'}
  if($taskProcess.ExitCode -ne 0){Get-Content -LiteralPath $taskStderr -Tail 15;throw 'Report native probe failed'}
}finally{if(-not $taskProcess.HasExited){Stop-Process -InputObject $taskProcess};$taskProcess.Dispose()}
if(Select-String -LiteralPath $taskStderr -Pattern '^ERROR:|SCRIPT ERROR' -Quiet){Get-Content -LiteralPath $taskStderr -Tail 15;throw 'Report native engine errors'}
if(-not(Select-String -LiteralPath $taskStdout -Pattern 'BugReport native probe: PASS' -Quiet)){Get-Content -LiteralPath $taskStdout -Tail 10;throw 'Native report PASS marker missing'}
Get-Content -LiteralPath $taskStdout -Tail 3
