[CmdletBinding()]
param(
    [ValidateSet('Debug', 'Release')]
    [string]$Configuration = 'Release',

    [string]$PythonExe = $env:STS2_PYTHON,

    [string]$GameDir = $env:STS2_GAME_DIR,

    [string]$DataDirV1071 = $env:STS2_DATA_DIR_V107_1,

    [string]$DataDirV111 = $env:STS2_DATA_DIR_V111,

    [string]$SourceRootV1071 = $env:STS2_SOURCE_ROOT_V107_1,

    [string]$SourceRootV111 = $env:STS2_SOURCE_ROOT_V111,

    [string]$BaseLibRef = $env:STS2_BASELIB_REF,

    [string]$RitsuLibRef = $env:STS2_RITSULIB_REF,

    [string]$GodotExe = $env:GODOT_4_5_1_MONO,

    [switch]$SkipPck,

    [switch]$SkipBehaviorProbe,

    [switch]$SkipVisualProbe,

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
    if (-not [string]::IsNullOrWhiteSpace($BaseLibRef)) {
        $arguments.BaseLibRef = $BaseLibRef
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

    if (-not $SkipBehaviorProbe) {
        $probeScript = Join-Path $PSScriptRoot 'test-quirky-hopper.ps1'
        $probeArguments = @{
            TargetVersion = $TargetVersion
            DataDir = $DataDir
            RuntimeDependencyDir = $DataDirV111
            ImplementationDll = Join-Path (Split-Path $PSScriptRoot -Parent) "build\$TargetVersion\STS2_Things.dll"
        }
        if (-not [string]::IsNullOrWhiteSpace($GodotExe)) {
            $probeArguments.GodotExe = $GodotExe
        }
        & $probeScript @probeArguments
        if ($LASTEXITCODE -ne 0) {
            throw "$TargetVersion Quirky Hopper probe failed with exit code $LASTEXITCODE"
        }

        $splitProbeScript = Join-Path $PSScriptRoot 'test-things-split.ps1'
        $splitProbeArguments = @{
            TargetVersion = $TargetVersion
            DataDir = $DataDir
            RuntimeDependencyDir = $DataDirV111
            ImplementationDll = Join-Path (Split-Path $PSScriptRoot -Parent) "build\$TargetVersion\STS2_Things.dll"
        }
        if (-not [string]::IsNullOrWhiteSpace($GodotExe)) {
            $splitProbeArguments.GodotExe = $GodotExe
        }
        & $splitProbeScript @splitProbeArguments
        if ($LASTEXITCODE -ne 0) {
            throw "$TargetVersion Things Split probe failed with exit code $LASTEXITCODE"
        }

        $collisionProbeScript = Join-Path $PSScriptRoot 'test-things-collision.ps1'
        $collisionProbeArguments = @{
            TargetVersion = $TargetVersion
            DataDir = $DataDir
            RuntimeDependencyDir = $DataDirV111
            ImplementationDll = Join-Path (Split-Path $PSScriptRoot -Parent) "build\$TargetVersion\STS2_Things.dll"
        }
        if (-not [string]::IsNullOrWhiteSpace($GodotExe)) {
            $collisionProbeArguments.GodotExe = $GodotExe
        }
        & $collisionProbeScript @collisionProbeArguments
        if ($LASTEXITCODE -ne 0) {
            throw "$TargetVersion Things Collision probe failed with exit code $LASTEXITCODE"
        }

        $modelIdProbeScript = Join-Path $PSScriptRoot 'test-model-id-namespace.ps1'
        $modelIdProbeArguments = @{
            TargetVersion = $TargetVersion
            DataDir = $DataDir
            RuntimeDependencyDir = $DataDirV111
            ImplementationDll = Join-Path (Split-Path $PSScriptRoot -Parent) "build\$TargetVersion\STS2_Things.dll"
            Pck = Join-Path (Split-Path $PSScriptRoot -Parent) "build\$TargetVersion\STS2_Things.pck"
        }
        if (-not [string]::IsNullOrWhiteSpace($GodotExe)) {
            $modelIdProbeArguments.GodotExe = $GodotExe
        }
        & $modelIdProbeScript @modelIdProbeArguments
        if ($LASTEXITCODE -ne 0) {
            throw "$TargetVersion ModelId namespace probe failed with exit code $LASTEXITCODE"
        }

        $configProbeScript = Join-Path $PSScriptRoot 'test-things-config.ps1'
        $configProbeArguments = @{
            TargetVersion = $TargetVersion
            DataDir = $DataDir
            RuntimeDependencyDir = $DataDirV111
            ImplementationDll = Join-Path (Split-Path $PSScriptRoot -Parent) "build\$TargetVersion\STS2_Things.dll"
            Pck = Join-Path (Split-Path $PSScriptRoot -Parent) "build\$TargetVersion\STS2_Things.pck"
        }
        if (-not [string]::IsNullOrWhiteSpace($GodotExe)) {
            $configProbeArguments.GodotExe = $GodotExe
        }
        & $configProbeScript @configProbeArguments
        if ($LASTEXITCODE -ne 0) {
            throw "$TargetVersion config probe failed with exit code $LASTEXITCODE"
        }

        $gravetideProbeScript = Join-Path $PSScriptRoot 'test-gravetide-slug.ps1'
        $gravetideProbeArguments = @{
            TargetVersion = $TargetVersion
            DataDir = $DataDir
            RuntimeDependencyDir = $DataDirV111
            ImplementationDll = Join-Path (Split-Path $PSScriptRoot -Parent) "build\$TargetVersion\STS2_Things.dll"
        }
        if (-not [string]::IsNullOrWhiteSpace($GodotExe)) {
            $gravetideProbeArguments.GodotExe = $GodotExe
        }
        & $gravetideProbeScript @gravetideProbeArguments
        if ($LASTEXITCODE -ne 0) {
            throw "$TargetVersion Gravetide Slug probe failed with exit code $LASTEXITCODE"
        }

        if ($TargetVersion -eq 'v111') {
            $merchantProbeScript = Join-Path $PSScriptRoot 'test-merchant-bargain.ps1'
            $merchantProbeArguments = @{
                DataDir = $DataDir
                RuntimeDependencyDir = $DataDirV111
                ImplementationDll = Join-Path (Split-Path $PSScriptRoot -Parent) "build\$TargetVersion\STS2_Things.dll"
            }
            if (-not [string]::IsNullOrWhiteSpace($GodotExe)) {
                $merchantProbeArguments.GodotExe = $GodotExe
            }
            & $merchantProbeScript @merchantProbeArguments
            if ($LASTEXITCODE -ne 0) {
                throw "V111 Merchant Bargain probe failed with exit code $LASTEXITCODE"
            }
        }
    }

    if ($TargetVersion -eq 'v111' -and -not $SkipVisualProbe) {
        $visualProbeScript = Join-Path $PSScriptRoot 'test-quirky-hopper-visual.ps1'
        $visualProbeArguments = @{}
        if (-not [string]::IsNullOrWhiteSpace($PythonExe)) {
            $visualProbeArguments.PythonExe = $PythonExe
        }
        if (-not [string]::IsNullOrWhiteSpace($GodotExe)) {
            $visualProbeArguments.GodotExe = $GodotExe
        }
        & $visualProbeScript @visualProbeArguments
        if ($LASTEXITCODE -ne 0) {
            throw "Quirky Hopper visual probe failed with exit code $LASTEXITCODE"
        }
    }
}

if ([string]::IsNullOrWhiteSpace($DataDirV1071)) {
    throw 'V107.1 reference directory is required. Pass -DataDirV1071 or set STS2_DATA_DIR_V107_1.'
}

if ([string]::IsNullOrWhiteSpace($GameDir)) {
    $GameDir = 'D:\Steam\steamapps\common\Slay the Spire 2'
}
if ([string]::IsNullOrWhiteSpace($DataDirV111)) {
    $DataDirV111 = Join-Path $GameDir 'data_sts2_windows_x86_64'
}

if ($SkipPck) {
    Invoke-VersionBuild 'v107.1' $DataDirV1071 $SourceRootV1071 $true ''
    Invoke-VersionBuild 'v111' $DataDirV111 $SourceRootV111 $true ''
}
else {
    Invoke-VersionBuild 'v111' $DataDirV111 $SourceRootV111 $false ''
    $sharedPck = Join-Path (Split-Path $PSScriptRoot -Parent) 'build\v111\STS2_Things.pck'
    Invoke-VersionBuild 'v107.1' $DataDirV1071 $SourceRootV1071 $false $sharedPck

    $unifiedBuild = Join-Path $PSScriptRoot 'build-unified.ps1'
    $unifiedArguments = @{
        Configuration = $Configuration
        GameDir = $GameDir
        DataDirV1071 = $DataDirV1071
        DataDirV111 = $DataDirV111
        Install = $Install
    }
    if (-not [string]::IsNullOrWhiteSpace($PythonExe)) {
        $unifiedArguments.PythonExe = $PythonExe
    }
    & $unifiedBuild @unifiedArguments
    if ($LASTEXITCODE -ne 0) {
        throw "Unified package build failed with exit code $LASTEXITCODE"
    }

    # 可选配置页集成探针（真实 Workshop BaseLib/RitsuLib DLL；两库不是前置依赖）。
    if (-not $SkipBehaviorProbe) {
        $baseLibDll = $BaseLibRef
        if ([string]::IsNullOrWhiteSpace($baseLibDll)) {
            $baseLibDll = 'D:\Steam\steamapps\workshop\content\2868840\3737335127\BaseLib\BaseLib.dll'
        }
        $bridgeDll = Join-Path (Split-Path $PSScriptRoot -Parent) 'build\v111\STS2_Things.BaseLibBridge.dll'
        if ((Test-Path -LiteralPath $baseLibDll -PathType Leaf) -and
            (Test-Path -LiteralPath $bridgeDll -PathType Leaf)) {
            Write-Host 'Running the BaseLib config bridge probe...'
            & (Join-Path $PSScriptRoot 'test-baselib-bridge.ps1') `
                -DataDir $DataDirV111 `
                -ImplementationDll (Join-Path (Split-Path $PSScriptRoot -Parent) 'build\v111\STS2_Things.dll') `
                -RuntimeDependencyDir $DataDirV111 `
                -BaseLibDll $baseLibDll `
                -BridgeDll $bridgeDll
            if ($LASTEXITCODE -ne 0) {
                throw "BaseLib config bridge probe failed with exit code $LASTEXITCODE"
            }
        }
        else {
            Write-Warning "BaseLib config bridge probe skipped: BaseLib.dll or the bridge DLL is missing."
        }

        $ritsuLibDll = $RitsuLibRef
        if ([string]::IsNullOrWhiteSpace($ritsuLibDll)) {
            $ritsuLibDll = 'D:\Steam\steamapps\workshop\content\2868840\3747602295\lib\0.111.0\STS2-RitsuLib.dll'
        }
        if (Test-Path -LiteralPath $ritsuLibDll -PathType Leaf) {
            Write-Host 'Running the RitsuLib interop probe...'
            & (Join-Path $PSScriptRoot 'test-ritsulib-interop.ps1') `
                -DataDir $DataDirV111 `
                -ImplementationDll (Join-Path (Split-Path $PSScriptRoot -Parent) 'build\v111\STS2_Things.dll') `
                -RuntimeDependencyDir $DataDirV111 `
                -RitsuLibDll $ritsuLibDll
            if ($LASTEXITCODE -ne 0) {
                throw "RitsuLib interop probe failed with exit code $LASTEXITCODE"
            }
        }
        else {
            Write-Warning "RitsuLib interop probe skipped: STS2-RitsuLib.dll was not found at '$ritsuLibDll'."
        }
    }
}

if ($SkipPck) {
    Write-Host 'Version-specific implementation artifacts are under build\v107.1 and build\v111.'
}
else {
    Write-Host 'Unified subscription artifacts are under build\unified.'
}
