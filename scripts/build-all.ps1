[CmdletBinding()]
param(
    [ValidateSet('Debug', 'Release')]
    [string]$Configuration = 'Release',

    [string]$PythonExe = $env:STS2_PYTHON,

    [string]$GameDir = $env:STS2_GAME_DIR,

    [string]$DataDirV1071 = $env:STS2_DATA_DIR_V107_1,

    [string]$DataDirV109 = $env:STS2_DATA_DIR_V109,

    [string]$SourceRootV1071 = $env:STS2_SOURCE_ROOT_V107_1,

    [string]$SourceRootV109 = $env:STS2_SOURCE_ROOT_V109,

    [string]$GodotExe = $env:GODOT_4_5_1_MONO,

    [switch]$SkipPck,

    [switch]$Install
)

$ErrorActionPreference = 'Stop'
$buildScript = Join-Path $PSScriptRoot 'build.ps1'

function Invoke-VersionBuild(
    [string]$TargetVersion,
    [string]$DataDir,
    [string]$SourceRoot,
    [bool]$SkipTargetPck,
    [string]$ReusePck
) {
    $arguments = @{
        Configuration = $Configuration
        TargetVersion = $TargetVersion
        SkipPck = $SkipTargetPck
    }
    if (-not [string]::IsNullOrWhiteSpace($PythonExe)) {
        $arguments.PythonExe = $PythonExe
    }
    if (-not [string]::IsNullOrWhiteSpace($GameDir)) {
        $arguments.GameDir = $GameDir
    }
    if (-not [string]::IsNullOrWhiteSpace($DataDir)) {
        $arguments.DataDir = $DataDir
    }
    if (-not [string]::IsNullOrWhiteSpace($SourceRoot)) {
        $arguments.SourceRoot = $SourceRoot
    }
    if (-not [string]::IsNullOrWhiteSpace($GodotExe)) {
        $arguments.GodotExe = $GodotExe
    }
    if (-not [string]::IsNullOrWhiteSpace($ReusePck)) {
        $arguments.ReusePck = $ReusePck
        [void]$arguments.Remove('SkipPck')
    }

    & $buildScript @arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$TargetVersion build failed with exit code $LASTEXITCODE"
    }
}

if ([string]::IsNullOrWhiteSpace($DataDirV1071)) {
    throw 'V107.1 reference directory is required. Pass -DataDirV1071 or set STS2_DATA_DIR_V107_1.'
}

if ([string]::IsNullOrWhiteSpace($GameDir)) {
    $GameDir = 'D:\Steam\steamapps\common\Slay the Spire 2'
}
if ([string]::IsNullOrWhiteSpace($DataDirV109)) {
    $DataDirV109 = Join-Path $GameDir 'data_sts2_windows_x86_64'
}

if ($SkipPck) {
    Invoke-VersionBuild 'v107.1' $DataDirV1071 $SourceRootV1071 $true ''
    Invoke-VersionBuild 'v109' $DataDirV109 $SourceRootV109 $true ''
}
else {
    Invoke-VersionBuild 'v109' $DataDirV109 $SourceRootV109 $false ''
    $sharedPck = Join-Path (Split-Path $PSScriptRoot -Parent) 'build\v109\STS2_Things.pck'
    Invoke-VersionBuild 'v107.1' $DataDirV1071 $SourceRootV1071 $false $sharedPck

    $unifiedBuild = Join-Path $PSScriptRoot 'build-unified.ps1'
    $unifiedArguments = @{
        Configuration = $Configuration
        GameDir = $GameDir
        DataDirV1071 = $DataDirV1071
        DataDirV109 = $DataDirV109
        Install = $Install
    }
    if (-not [string]::IsNullOrWhiteSpace($PythonExe)) {
        $unifiedArguments.PythonExe = $PythonExe
    }
    & $unifiedBuild @unifiedArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Unified package build failed with exit code $LASTEXITCODE"
    }
}

if ($SkipPck) {
    Write-Host 'Version-specific implementation artifacts are under build\v107.1 and build\v109.'
}
else {
    Write-Host 'Unified subscription artifacts are under build\unified.'
}
