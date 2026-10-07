$ErrorActionPreference = 'Stop'

$GodotExe = 'D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe'
$Root = 'D:\Things\Things-Workspace\STS2_Things'
$PckBuild = 'D:\Things\Things-Workspace\STS2_Things\build\v111\STS2_Things.pck'
$ModDir = 'D:\Steam\steamapps\common\Slay the Spire 2\mods\STS2_Things'

Write-Host "1. Re-importing Godot assets in $Root..."
& $GodotExe --headless --editor --path $Root --import --quit
if ($LASTEXITCODE -ne 0) { throw "Godot import failed: $LASTEXITCODE" }

Write-Host "2. Exporting PCK to $PckBuild..."
New-Item -ItemType Directory -Path (Split-Path $PckBuild -Parent) -Force | Out-Null
& $GodotExe --headless --editor --path $Root --export-pack "STS2 PCK" $PckBuild --quit
if ($LASTEXITCODE -ne 0) { throw "Godot export failed: $LASTEXITCODE" }

Write-Host "PCK build successful! Size: $((Get-Item $PckBuild).Length) bytes"

if (Test-Path $ModDir) {
    Write-Host "3. Installing PCK to $ModDir..."
    Copy-Item -LiteralPath $PckBuild -Destination (Join-Path $ModDir "STS2_Things.pck") -Force
    Write-Host "Installed PCK to game directory!"
}
