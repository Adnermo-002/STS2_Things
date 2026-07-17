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

    [switch]$SkipPck
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

if ($SkipPck) {
    Invoke-VersionBuild 'v107.1' $DataDirV1071 $SourceRootV1071 $true ''
    Invoke-VersionBuild 'v109' $DataDirV109 $SourceRootV109 $true ''
}
else {
    Invoke-VersionBuild 'v109' $DataDirV109 $SourceRootV109 $false ''
    $sharedPck = Join-Path (Split-Path $PSScriptRoot -Parent) 'build\v109\STS2_Things.pck'
    Invoke-VersionBuild 'v107.1' $DataDirV1071 $SourceRootV1071 $false $sharedPck
}

Write-Host 'Dual-version artifacts are under build\v107.1 and build\v109.'
