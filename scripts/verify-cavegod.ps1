[CmdletBinding()]
param(
    [string]$DotnetExe = 'C:\Program Files\dotnet\dotnet.exe',
    [string]$GodotExe = 'D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe',
    [string]$OutputDirectory = 'build/cavegod-refactor-20260919',
    [switch]$Render
)

$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$outputRoot = [IO.Path]::GetFullPath((Join-Path $projectRoot $OutputDirectory))
$implementation = Join-Path $outputRoot 'candidate/STS2_Things.dll'
$probeRoot = Join-Path $projectRoot 'tools/CaveGodProbe'
New-Item -ItemType Directory -Path $outputRoot -Force | Out-Null

& $DotnetExe build (Join-Path $projectRoot 'STS2_Things.csproj') -c Release --nologo `
    -p:Sts2TargetVersion=v111 -o (Join-Path $outputRoot 'candidate') |
    Tee-Object -FilePath (Join-Path $outputRoot 'release-build.log')
if ($LASTEXITCODE -ne 0) { throw "Release build failed: $LASTEXITCODE" }

& $DotnetExe build (Join-Path $probeRoot 'CaveGodProbe.csproj') -c Debug --nologo `
    "-p:ImplementationDll=$implementation"
if ($LASTEXITCODE -ne 0) { throw "Probe build failed: $LASTEXITCODE" }

& $GodotExe --headless --path $probeRoot --log-file (Join-Path $outputRoot 'probe.log')
if ($LASTEXITCODE -ne 0) { throw "CaveGod behavior probe failed: $LASTEXITCODE" }

if ($Render) {
    # Start-Process arguments require quoting because the project path may contain spaces.
    $arguments = @('--path', ('"{0}"' -f $probeRoot), '--rendering-method', 'gl_compatibility',
        '--resolution', '1920x1080', '--log-file', ('"{0}"' -f (Join-Path $outputRoot 'visual-probe.log')),
        '--', '--visual')
    $process = Start-Process -FilePath $GodotExe -ArgumentList $arguments -WindowStyle Hidden -PassThru
    if (-not $process.WaitForExit(60000)) { throw "Renderer did not finish; inspect process $($process.Id)." }
    if ($process.ExitCode -ne 0) { throw "CaveGod renderer failed: $($process.ExitCode)" }
}

Write-Host "CaveGod verification complete: $outputRoot"
