[CmdletBinding()]
param(
    [ValidateSet('Debug', 'Release')]
    [string]$Configuration = 'Release',

    [string]$PythonExe = $env:STS2_PYTHON,

    [string]$GameDir = $env:STS2_GAME_DIR,

    [Parameter(Mandatory)]
    [string]$DataDirV1071,

    [Parameter(Mandatory)]
    [string]$DataDirV109,

    [switch]$Install
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$BuildDir = Join-Path $Root 'build\unified'
$BootstrapProject = Join-Path $Root 'bootstrap\STS2_Things.Bootstrap.csproj'
$ImplementationV1071 = Join-Path $Root 'build\v107.1\STS2_Things.dll'
$ImplementationV109 = Join-Path $Root 'build\v109\STS2_Things.dll'
$SharedPck = Join-Path $Root 'build\v109\STS2_Things.pck'
$Manifest = Join-Path $Root 'STS2_Things.json'

if ([string]::IsNullOrWhiteSpace($GameDir)) {
    $GameDir = 'D:\Steam\steamapps\common\Slay the Spire 2'
}
$GameDir = [IO.Path]::GetFullPath($GameDir)
$DataDirV1071 = [IO.Path]::GetFullPath($DataDirV1071)
$DataDirV109 = [IO.Path]::GetFullPath($DataDirV109)

foreach ($path in @(
    $BootstrapProject,
    $ImplementationV1071,
    $ImplementationV109,
    $SharedPck,
    $Manifest,
    (Join-Path $DataDirV1071 'sts2.dll'),
    (Join-Path $DataDirV1071 '0Harmony.dll'),
    (Join-Path $DataDirV109 'sts2.dll'),
    (Join-Path $DataDirV109 '0Harmony.dll')
)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Unified build input was not found: $path"
    }
}

New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null

Write-Host 'Building unified STS2_Things bootstrap...'
& dotnet build $BootstrapProject -c $Configuration --nologo `
    "/p:Sts2DataDir=$DataDirV1071" `
    "/p:ImplementationV1071=$ImplementationV1071" `
    "/p:ImplementationV109=$ImplementationV109"
if ($LASTEXITCODE -ne 0) {
    throw "Unified bootstrap build failed with exit code $LASTEXITCODE"
}

$BootstrapDll = Join-Path $Root "bootstrap\bin\$Configuration\net9.0\STS2_Things.Bootstrap.dll"
if (-not (Test-Path -LiteralPath $BootstrapDll -PathType Leaf)) {
    throw "Unified bootstrap DLL was not found: $BootstrapDll"
}

Copy-Item -LiteralPath $BootstrapDll -Destination (Join-Path $BuildDir 'STS2_Things.dll') -Force
Copy-Item -LiteralPath $SharedPck -Destination (Join-Path $BuildDir 'STS2_Things.pck') -Force
Copy-Item -LiteralPath $Manifest -Destination (Join-Path $BuildDir 'STS2_Things.json') -Force

$packageProbe = Join-Path $PSScriptRoot 'verify-unified-package.ps1'
& $packageProbe `
    -DataDirV1071 $DataDirV1071 `
    -DataDirV109 $DataDirV109 `
    -BootstrapDll (Join-Path $BuildDir 'STS2_Things.dll') `
    -ImplementationV1071 $ImplementationV1071 `
    -ImplementationV109 $ImplementationV109
if ($LASTEXITCODE -ne 0) {
    throw "Unified package probe failed with exit code $LASTEXITCODE"
}

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $PythonExe = Join-Path $env:USERPROFILE `
        '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
}
$validator = Join-Path $env:USERPROFILE '.codex\skills\sts2-mod-master\scripts\validate_mod.py'
if ((Test-Path -LiteralPath $PythonExe -PathType Leaf) -and
    (Test-Path -LiteralPath $validator -PathType Leaf)) {
    & $PythonExe -X utf8 $validator `
        (Join-Path $BuildDir 'STS2_Things.json') `
        --source-root (Join-Path (Split-Path $Root -Parent) 'STS2-V109') `
        --require-artifacts --strict
    if ($LASTEXITCODE -ne 0) {
        throw "Unified package validation failed with exit code $LASTEXITCODE"
    }
}

if ($Install) {
    $modsDir = Join-Path $GameDir 'mods'
    if (-not (Test-Path -LiteralPath $modsDir -PathType Container)) {
        New-Item -ItemType Directory -Path $modsDir | Out-Null
    }
    $modsDir = (Resolve-Path -LiteralPath $modsDir).Path
    $installDir = Join-Path $modsDir 'STS2_Things'
    if ((Split-Path -Parent $installDir) -ne $modsDir) {
        throw "Unsafe install path: $installDir"
    }
    if (-not (Test-Path -LiteralPath $installDir -PathType Container)) {
        New-Item -ItemType Directory -Path $installDir | Out-Null
    }
    $unexpectedJson = Get-ChildItem -LiteralPath $installDir -File -Filter '*.json' |
        Where-Object Name -ne 'STS2_Things.json'
    if ($unexpectedJson) {
        throw "Refusing to install beside extra JSON manifests: $($unexpectedJson.Name -join ', ')"
    }
    foreach ($name in 'STS2_Things.json', 'STS2_Things.dll', 'STS2_Things.pck') {
        Copy-Item -LiteralPath (Join-Path $BuildDir $name) `
            -Destination (Join-Path $installDir $name) -Force
    }
    Write-Host "Installed unified package to $installDir"
}

Write-Host 'Unified artifacts:'
foreach ($name in 'STS2_Things.json', 'STS2_Things.dll', 'STS2_Things.pck') {
    $path = Join-Path $BuildDir $name
    $item = Get-Item -LiteralPath $path
    $hash = (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash
    Write-Host ("  {0,-18} {1,10} bytes  SHA256 {2}" -f $name, $item.Length, $hash)
}
