[CmdletBinding()]
param([string]$LogDirectory = 'build\reverse_salamander')
$ErrorActionPreference='Stop'
$taskRoot=(Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskLog=Join-Path $taskRoot $LogDirectory
$taskDotnet='C:\Program Files\dotnet\dotnet.exe'
$taskGodot='D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe'
$taskCurrentData='D:\Steam\steamapps\common\Slay the Spire 2\data_sts2_windows_x86_64'
$taskLegacyData=Join-Path $taskRoot '.tmp\things-collision-v107-data'
$env:PATH='C:\Program Files\dotnet;'+$env:PATH
$env:DOTNET_ROOT='C:\Program Files\dotnet'
New-Item -ItemType Directory -Path $taskLog,(Join-Path $taskRoot 'build\v107.1'),(Join-Path $taskRoot 'build\v111'),(Join-Path $taskRoot 'build\unified') -Force | Out-Null

# This request explicitly excludes tests and live probes. These steps only
# compile the deliverable, import assets, and export the distributable package.
& $taskDotnet build (Join-Path $taskRoot 'STS2_Things.csproj') -c Release --nologo -o (Join-Path $taskLog 'v107.1') '/p:Sts2TargetVersion=v107.1' "/p:Sts2DataDir=$taskLegacyData" *> (Join-Path $taskLog 'compile-v107.log')
if($LASTEXITCODE -ne 0){throw 'Legacy compilation failed; see compile-v107.log'}
Copy-Item -LiteralPath (Join-Path $taskLog 'v107.1\STS2_Things.dll') -Destination (Join-Path $taskRoot 'build\v107.1\STS2_Things.dll') -Force
Copy-Item -LiteralPath (Join-Path $taskRoot 'manifests\v107.1\STS2_Things.json') -Destination (Join-Path $taskRoot 'build\v107.1\STS2_Things.json') -Force

& $taskDotnet build (Join-Path $taskRoot 'STS2_Things.csproj') -c Release --nologo '/p:Sts2TargetVersion=v111' "/p:Sts2DataDir=$taskCurrentData" *> (Join-Path $taskLog 'compile-v111.log')
if($LASTEXITCODE -ne 0){throw 'Current compilation failed; see compile-v111.log'}
Copy-Item -LiteralPath (Join-Path $taskRoot '.godot\mono\temp\bin\Release\STS2_Things.dll') -Destination (Join-Path $taskRoot 'build\v111\STS2_Things.dll') -Force
Copy-Item -LiteralPath (Join-Path $taskRoot 'manifests\v111\STS2_Things.json') -Destination (Join-Path $taskRoot 'build\v111\STS2_Things.json') -Force

& $taskGodot --headless --editor --path $taskRoot --import --quit --log-file (Join-Path $taskLog 'import.log') *> (Join-Path $taskLog 'import-console.log')
if($LASTEXITCODE -ne 0){throw 'Godot asset import failed'}
if(Select-String -LiteralPath (Join-Path $taskLog 'import.log') -Pattern '^ERROR:|SCRIPT ERROR:' -Quiet){throw 'Godot asset import reported errors'}
& $taskGodot --headless --editor --path $taskRoot --export-pack 'STS2 PCK' (Join-Path $taskRoot 'build\v111\STS2_Things.pck') --quit --log-file (Join-Path $taskLog 'export.log') *> (Join-Path $taskLog 'export-console.log')
if($LASTEXITCODE -ne 0){throw 'Godot package export failed'}
if(Select-String -LiteralPath (Join-Path $taskLog 'export.log') -Pattern '^ERROR:|SCRIPT ERROR:' -Quiet){throw 'Godot package export reported errors'}
Copy-Item -LiteralPath (Join-Path $taskRoot 'build\v111\STS2_Things.pck') -Destination (Join-Path $taskRoot 'build\v107.1\STS2_Things.pck') -Force

& $taskDotnet build (Join-Path $taskRoot 'bootstrap\STS2_Things.Bootstrap.csproj') -c Release --nologo "/p:Sts2DataDir=$taskLegacyData" "/p:ImplementationV1071=$(Join-Path $taskRoot 'build\v107.1\STS2_Things.dll')" "/p:ImplementationV111=$(Join-Path $taskRoot 'build\v111\STS2_Things.dll')" *> (Join-Path $taskLog 'compile-bootstrap.log')
if($LASTEXITCODE -ne 0){throw 'Bootstrap compilation failed'}
Copy-Item -LiteralPath (Join-Path $taskRoot 'bootstrap\bin\Release\net9.0\STS2_Things.Bootstrap.dll') -Destination (Join-Path $taskRoot 'build\unified\STS2_Things.dll') -Force
Copy-Item -LiteralPath (Join-Path $taskRoot 'build\v111\STS2_Things.pck'),(Join-Path $taskRoot 'STS2_Things.json') -Destination (Join-Path $taskRoot 'build\unified') -Force

$taskBridgeRef='D:\Steam\steamapps\workshop\content\2868840\3737335127\BaseLib\BaseLib.dll'
if(Test-Path -LiteralPath $taskBridgeRef){
 & $taskDotnet build (Join-Path $taskRoot 'bridges\STS2_Things.BaseLibBridge\STS2_Things.BaseLibBridge.csproj') -c Release --nologo "/p:BaseLibRef=$taskBridgeRef" "/p:Sts2DataDir=$taskCurrentData" *> (Join-Path $taskLog 'compile-bridge.log')
 if($LASTEXITCODE -ne 0){throw 'Optional bridge compilation failed'}
 Copy-Item -LiteralPath (Join-Path $taskRoot 'bridges\STS2_Things.BaseLibBridge\.godot\mono\temp\bin\Release\STS2_Things.BaseLibBridge.dll') -Destination (Join-Path $taskRoot 'build\unified\STS2_Things.BaseLibBridge.dll') -Force
}
Write-Output 'Compilation and export complete. No tests, probes, or game interactions were run.'
