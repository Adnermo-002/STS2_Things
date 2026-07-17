[CmdletBinding()]
param(
    [ValidateSet('Debug', 'Release')]
    [string]$Configuration = 'Release',

    [ValidateSet('v107.1', 'v108')]
    [string]$TargetVersion = 'v108',

    [string]$PythonExe = $env:STS2_PYTHON,

    [string]$GameDir = $env:STS2_GAME_DIR,

    [string]$DataDir = $env:STS2_DATA_DIR,

    [string]$SourceRoot = $env:STS2_SOURCE_ROOT,

    [string]$GodotExe = $env:GODOT_4_5_1_MONO,

    [switch]$Install,

    [switch]$SkipPck,

    [string]$ReusePck
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$CommonBuildDir = Join-Path $Root 'build'
$BuildDir = Join-Path $CommonBuildDir $TargetVersion
$Project = Join-Path $Root 'STS2_Things.csproj'
$Manifest = Join-Path $Root "manifests\$TargetVersion\STS2_Things.json"
$Pck = Join-Path $BuildDir 'STS2_Things.pck'
$ExportPck = -not $SkipPck -and [string]::IsNullOrWhiteSpace($ReusePck)

function Assert-GodotLogClean([string]$LogPath) {
    if (-not (Test-Path -LiteralPath $LogPath)) {
        throw "Godot log was not created: $LogPath"
    }
    $errors = Select-String -LiteralPath $LogPath `
        -Pattern '(^|\s)(SCRIPT ERROR|ERROR:|WARNING:)|Failed loading resource' `
        -CaseSensitive:$false
    if ($errors) {
        $preview = ($errors | Select-Object -First 12 | ForEach-Object Line) -join [Environment]::NewLine
        throw "Godot reported resource/script errors in '$LogPath':`n$preview"
    }
}

function Resolve-PythonExecutable([string]$Requested) {
    $candidates = @()
    if (-not [string]::IsNullOrWhiteSpace($Requested)) {
        $candidates += $Requested
    }

    # Codex Desktop ships a deterministic Python runtime with Pillow and NumPy.
    # Keep it ahead of PATH so Windows Store aliases cannot steal the build.
    $candidates += (Join-Path $env:USERPROFILE `
        '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')

    foreach ($name in 'python.exe', 'python3.exe', 'python') {
        $command = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue |
            Select-Object -First 1
        if ($null -ne $command) {
            $candidates += $command.Source
        }
    }

    $localPrograms = Join-Path $env:LOCALAPPDATA 'Programs\Python'
    if (Test-Path -LiteralPath $localPrograms) {
        $candidates += Get-ChildItem -LiteralPath $localPrograms -Filter 'python.exe' `
            -File -Recurse -ErrorAction SilentlyContinue |
            Sort-Object FullName -Descending |
            Select-Object -ExpandProperty FullName
    }

    foreach ($candidate in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
        $path = $candidate
        if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
            $command = Get-Command $path -CommandType Application -ErrorAction SilentlyContinue |
                Select-Object -First 1
            if ($null -eq $command) {
                continue
            }
            $path = $command.Source
        }

        $probe = & $path -X utf8 -c `
            'import sys, PIL, numpy; assert sys.version_info >= (3, 10); print(sys.executable)' `
            2>$null | Select-Object -Last 1
        if ($LASTEXITCODE -eq 0 -and -not [string]::IsNullOrWhiteSpace($probe)) {
            return (Resolve-Path -LiteralPath $path).Path
        }
    }

    # The Windows launcher is useful when no python.exe is exposed on PATH.
    $launcher = Get-Command 'py.exe' -CommandType Application -ErrorAction SilentlyContinue |
        Select-Object -First 1
    if ($null -ne $launcher) {
        $launchedPath = & $launcher.Source -3 -X utf8 -c `
            'import sys, PIL, numpy; assert sys.version_info >= (3, 10); print(sys.executable)' `
            2>$null | Select-Object -Last 1
        if ($LASTEXITCODE -eq 0 -and (Test-Path -LiteralPath $launchedPath -PathType Leaf)) {
            return (Resolve-Path -LiteralPath $launchedPath).Path
        }
    }

    throw 'Python 3.10+ with Pillow and NumPy was not found. Pass -PythonExe or set STS2_PYTHON.'
}

if ([string]::IsNullOrWhiteSpace($GameDir)) {
    $GameDir = 'D:\Steam\steamapps\common\Slay the Spire 2'
}
$GameDir = [IO.Path]::GetFullPath($GameDir)
if ([string]::IsNullOrWhiteSpace($DataDir)) {
    if ($TargetVersion -eq 'v107.1') {
        $DataDir = $env:STS2_DATA_DIR_V107_1
    }
    else {
        $DataDir = $env:STS2_DATA_DIR_V108
    }
}
if ([string]::IsNullOrWhiteSpace($DataDir)) {
    $DataDir = Join-Path $GameDir 'data_sts2_windows_x86_64'
}
$DataDir = [IO.Path]::GetFullPath($DataDir)

if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
    if ($TargetVersion -eq 'v107.1') {
        $SourceRoot = $env:STS2_SOURCE_ROOT_V107_1
    }
    else {
        $SourceRoot = $env:STS2_SOURCE_ROOT_V108
        if ([string]::IsNullOrWhiteSpace($SourceRoot)) {
            $SourceRoot = Join-Path (Split-Path $Root -Parent) 'STS2-V108'
        }
    }
}
if (-not [string]::IsNullOrWhiteSpace($SourceRoot)) {
    $SourceRoot = [IO.Path]::GetFullPath($SourceRoot)
}

if (-not (Test-Path -LiteralPath (Join-Path $DataDir 'sts2.dll'))) {
    throw "STS2 assembly not found under '$DataDir'. Pass -DataDir or set the target-specific STS2_DATA_DIR variable."
}
if (-not (Test-Path -LiteralPath (Join-Path $DataDir '0Harmony.dll'))) {
    throw "Harmony assembly not found under '$DataDir'."
}
if (-not (Test-Path -LiteralPath $Manifest -PathType Leaf)) {
    throw "Target manifest not found: $Manifest"
}

$dataGameRoot = Split-Path $DataDir -Parent
$releaseInfoPath = Join-Path $dataGameRoot 'release_info.json'
if (Test-Path -LiteralPath $releaseInfoPath) {
    $releaseInfo = Get-Content -Raw -LiteralPath $releaseInfoPath | ConvertFrom-Json
    $expectedRelease = if ($TargetVersion -eq 'v107.1') { 'v0.107.1' } else { 'v0.108.0' }
    if ($releaseInfo.version -ne $expectedRelease) {
        throw "Target $TargetVersion expects $expectedRelease, but '$GameDir' contains $($releaseInfo.version). Pass the matching -DataDir."
    }
}
if ($Install -and $SkipPck) {
    throw '-Install requires a complete DLL/PCK build.'
}
if ($SkipPck -and -not [string]::IsNullOrWhiteSpace($ReusePck)) {
    throw '-SkipPck and -ReusePck cannot be used together.'
}
if (-not [string]::IsNullOrWhiteSpace($ReusePck)) {
    $ReusePck = [IO.Path]::GetFullPath($ReusePck)
    if (-not (Test-Path -LiteralPath $ReusePck -PathType Leaf)) {
        throw "Reusable PCK not found: $ReusePck"
    }
}

if ([string]::IsNullOrWhiteSpace($GodotExe)) {
    $candidate = 'D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe'
    if (Test-Path -LiteralPath $candidate) {
        $GodotExe = $candidate
    }
}

if ($ExportPck) {
    if ([string]::IsNullOrWhiteSpace($GodotExe) -or -not (Test-Path -LiteralPath $GodotExe)) {
        throw 'Godot 4.5.1 Mono was not found. Pass -GodotExe or set GODOT_4_5_1_MONO.'
    }

    $godotVersion = (& $GodotExe --version | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $godotVersion.StartsWith('4.5.1.stable.mono', [StringComparison]::OrdinalIgnoreCase)) {
        throw "Expected Godot 4.5.1 Mono, got '$godotVersion'."
    }
}

$PythonExe = Resolve-PythonExecutable $PythonExe
Write-Host "Using Python: $PythonExe"

New-Item -ItemType Directory -Path $BuildDir -Force | Out-Null
# Keep previews, logs and fastmp evidence below build/ out of Godot's editor scan.
$godotIgnore = Join-Path $CommonBuildDir '.gdignore'
if (-not (Test-Path -LiteralPath $godotIgnore)) {
    Set-Content -LiteralPath $godotIgnore -Value '' -Encoding ascii
}

$monsterTextureBuild = Join-Path $PSScriptRoot 'stylize_monster_textures.py'
if (Test-Path -LiteralPath $monsterTextureBuild) {
    Write-Host 'Mirroring exact RGBA monster source textures...'
    & $PythonExe -X utf8 $monsterTextureBuild
    if ($LASTEXITCODE -ne 0) {
        throw "Monster texture build failed with exit code $LASTEXITCODE"
    }
}

$staticMonsterBuild = Join-Path $PSScriptRoot 'build_static_monster_scenes.py'
if (-not (Test-Path -LiteralPath $staticMonsterBuild -PathType Leaf)) {
    throw "Static monster scene build script was not found: $staticMonsterBuild"
}
Write-Host 'Restoring full-texture static monster scenes...'
& $PythonExe -X utf8 $staticMonsterBuild
if ($LASTEXITCODE -ne 0) {
    throw "Static monster scene build failed with exit code $LASTEXITCODE"
}

$sourceAudit = Join-Path $PSScriptRoot 'verify_project.py'
if (Test-Path -LiteralPath $sourceAudit) {
    & $PythonExe -X utf8 $sourceAudit
    if ($LASTEXITCODE -ne 0) {
        throw "Source audit failed with exit code $LASTEXITCODE"
    }
}

$fmodAudit = Join-Path $PSScriptRoot 'verify_fmod.py'
if ((Test-Path -LiteralPath $fmodAudit) -and
    -not [string]::IsNullOrWhiteSpace($SourceRoot) -and
    (Test-Path -LiteralPath $SourceRoot)) {
    & $PythonExe -X utf8 $fmodAudit `
        --game-dir $GameDir `
        --source-root $SourceRoot
    if ($LASTEXITCODE -ne 0) {
        throw "FMOD audit failed with exit code $LASTEXITCODE"
    }
}
elseif (Test-Path -LiteralPath $fmodAudit) {
    Write-Warning "Skipping FMOD audit because the $TargetVersion source root was not provided."
}

Write-Host "Building STS2_Things ($Configuration, $TargetVersion) against $DataDir"
& dotnet build $Project -c $Configuration --nologo `
    "/p:Sts2TargetVersion=$TargetVersion" `
    "/p:Sts2DataDir=$DataDir" `
    "/p:Sts2GameDir=$GameDir"
if ($LASTEXITCODE -ne 0) {
    throw "dotnet build failed with exit code $LASTEXITCODE"
}

if ($ExportPck) {
    # Older builds placed the isolated PCK verifier below res://, which makes
    # the next Godot scan warn about a nested project. Remove only that exact,
    # verified child directory before importing the real project.
    $legacyPckVerifyDir = [IO.Path]::GetFullPath((Join-Path $BuildDir 'pck-verify'))
    if ((Split-Path -Parent $legacyPckVerifyDir) -ne [IO.Path]::GetFullPath($BuildDir)) {
        throw "Unsafe legacy PCK verifier path: $legacyPckVerifyDir"
    }
    if (Test-Path -LiteralPath $legacyPckVerifyDir) {
        Remove-Item -LiteralPath $legacyPckVerifyDir -Recurse -Force
    }

    $importLog = Join-Path $BuildDir 'godot-import.log'
    Write-Host 'Importing Godot resources...'
    & $GodotExe --headless --editor --path $Root --import --quit --log-file $importLog
    if ($LASTEXITCODE -ne 0) {
        throw "Godot import failed with exit code $LASTEXITCODE"
    }
    Assert-GodotLogClean $importLog

    $exportLog = Join-Path $BuildDir 'godot-export.log'
    Write-Host 'Exporting STS2_Things.pck...'
    # Run the export in editor mode so Godot initializes EditorSettings before
    # the .NET export plugin queries them. Without --editor, 4.5.1 can complete
    # the pack successfully but still emit a spurious _EDITOR_GET ERROR at exit,
    # which correctly trips the strict log gate below.
    & $GodotExe --headless --editor --path $Root --export-pack 'STS2 PCK' $Pck --log-file $exportLog
    if ($LASTEXITCODE -ne 0 -or -not (Test-Path -LiteralPath $Pck)) {
        throw "Godot PCK export failed with exit code $LASTEXITCODE"
    }
    Assert-GodotLogClean $exportLog

    $forbiddenPackEntries = Select-String -LiteralPath $exportLog `
        -Pattern 'res://(tools|manifests|source_assets|docs|scripts|build|dist)/|res://STS2_Things\.json' `
        -CaseSensitive:$false
    if ($forbiddenPackEntries) {
        $preview = ($forbiddenPackEntries | Select-Object -First 12 | ForEach-Object Line) `
            -join [Environment]::NewLine
        throw "PCK contains build-time or manifest files:`n$preview"
    }

    # BackgroundAssets enumerates layer filenames from the mounted PCK. A normal
    # binary text-resource export exposes *.tscn.remap entries, which are not valid
    # scene paths when enumerated literally. Mount the finished pack in an isolated
    # project and prove the four runtime directories expose loadable *.tscn scenes.
    $tempRoot = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
    $pckVerifyDir = Join-Path $tempRoot ("STS2_Things-pck-verify-" + [Guid]::NewGuid().ToString('N'))
    $pckVerifyDir = [IO.Path]::GetFullPath($pckVerifyDir)
    if (-not $pckVerifyDir.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe temporary PCK verifier path: $pckVerifyDir"
    }
    New-Item -ItemType Directory -Path $pckVerifyDir -Force | Out-Null
    @'
config_version=5

[application]

config/name="STS2_Things PCK Verify"
'@ | Set-Content -LiteralPath (Join-Path $pckVerifyDir 'project.godot') -Encoding utf8
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'verify_pck.gd') `
        -Destination (Join-Path $pckVerifyDir 'verify_pck.gd') -Force
    $pckVerifyLog = Join-Path $BuildDir 'pck-verify.log'
    try {
        Write-Host 'Verifying mounted PCK background paths...'
        & $GodotExe --headless --path $pckVerifyDir `
            --script (Join-Path $pckVerifyDir 'verify_pck.gd') `
            --log-file $pckVerifyLog -- $Pck
        if ($LASTEXITCODE -ne 0) {
            throw "Mounted PCK verification failed with exit code $LASTEXITCODE"
        }
        Assert-GodotLogClean $pckVerifyLog

    }
    finally {
        if (Test-Path -LiteralPath $pckVerifyDir) {
            Remove-Item -LiteralPath $pckVerifyDir -Recurse -Force
        }
    }
}
elseif (-not [string]::IsNullOrWhiteSpace($ReusePck)) {
    Copy-Item -LiteralPath $ReusePck -Destination $Pck -Force
}

$dll = Join-Path $Root ".godot\mono\temp\bin\$Configuration\STS2_Things.dll"
if (-not (Test-Path -LiteralPath $dll)) {
    throw "Built DLL not found: $dll"
}
Copy-Item -LiteralPath $dll -Destination (Join-Path $BuildDir 'STS2_Things.dll') -Force
Copy-Item -LiteralPath $Manifest -Destination (Join-Path $BuildDir 'STS2_Things.json') -Force

$harmonyProbe = Join-Path $PSScriptRoot 'verify-harmony-targets.ps1'
if (Test-Path -LiteralPath $harmonyProbe -PathType Leaf) {
    $dependencyDataDir = Join-Path $GameDir 'data_sts2_windows_x86_64'
    & $harmonyProbe `
        -DataDir $DataDir `
        -ModDll (Join-Path $BuildDir 'STS2_Things.dll') `
        -DependencyDataDir $dependencyDataDir
}

$validator = Join-Path $env:USERPROFILE '.codex\skills\sts2-mod-master\scripts\validate_mod.py'
if (Test-Path -LiteralPath $validator) {
    # Validate the exact packaged manifest.  The build directory intentionally
    # retains fastmp evidence JSON, so passing the directory itself would make a
    # package validator treat those records as additional manifest candidates.
    $validatorArgs = @((Join-Path $BuildDir 'STS2_Things.json'))
    if (-not [string]::IsNullOrWhiteSpace($SourceRoot) -and
        (Test-Path -LiteralPath $SourceRoot)) {
        $validatorArgs += @('--source-root', $SourceRoot)
    }
    if (-not $SkipPck) {
        $validatorArgs += '--require-artifacts'
    }
    & $PythonExe -X utf8 $validator @validatorArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Mod validation failed with exit code $LASTEXITCODE"
    }
}

if ($Install) {
    $modsDir = Join-Path $GameDir 'mods'
    if (-not (Test-Path -LiteralPath $modsDir)) {
        New-Item -ItemType Directory -Path $modsDir | Out-Null
    }
    $modsDir = (Resolve-Path -LiteralPath $modsDir).Path
    $installDir = Join-Path $modsDir 'STS2_Things'
    if ((Split-Path -Parent $installDir) -ne $modsDir) {
        throw "Unsafe install path: $installDir"
    }
    if (-not (Test-Path -LiteralPath $installDir)) {
        New-Item -ItemType Directory -Path $installDir | Out-Null
    }

    $unexpectedJson = Get-ChildItem -LiteralPath $installDir -File -Filter '*.json' |
        Where-Object Name -ne 'STS2_Things.json'
    if ($unexpectedJson) {
        throw "Refusing to install beside extra JSON manifest candidates: $($unexpectedJson.Name -join ', ')"
    }

    foreach ($name in 'STS2_Things.json', 'STS2_Things.dll', 'STS2_Things.pck') {
        $source = Join-Path $BuildDir $name
        if (-not (Test-Path -LiteralPath $source)) {
            throw "Required artifact not found: $source"
        }
        Copy-Item -LiteralPath $source -Destination (Join-Path $installDir $name) -Force
    }
    Write-Host "Installed to $installDir"
}

Write-Host 'Artifacts:'
Get-ChildItem -LiteralPath $BuildDir -File |
    Where-Object Name -in @('STS2_Things.json', 'STS2_Things.dll', 'STS2_Things.pck') |
    Sort-Object Name |
    ForEach-Object {
        $hash = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
        Write-Host ("  {0,-18} {1,10} bytes  SHA256 {2}" -f $_.Name, $_.Length, $hash)
    }
