[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('v107.1', 'v110')]
    [string]$TargetVersion,

    [Parameter(Mandatory = $true)]
    [string]$DataDir,

    [Parameter(Mandatory = $true)]
    [string]$ImplementationDll,

    [Parameter(Mandatory = $true)]
    [string]$RuntimeDependencyDir,

    [string]$GodotExe = $env:GODOT_4_5_1_MONO
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$ProbeRoot = Join-Path $Root 'tools\GravetideSlugProbe'
$ProbeProject = Join-Path $ProbeRoot 'GravetideSlugProbe.csproj'

function Resolve-GodotConsoleExecutable([string]$Requested) {
    $candidates = @()
    if (-not [string]::IsNullOrWhiteSpace($Requested)) {
        $candidates += $Requested
        $requestedDirectory = Split-Path -Parent $Requested
        $requestedName = [IO.Path]::GetFileNameWithoutExtension($Requested)
        if (-not $requestedName.EndsWith('_console', [StringComparison]::OrdinalIgnoreCase)) {
            $candidates += Join-Path $requestedDirectory ($requestedName + '_console.exe')
        }
    }
    $candidates += @(
        'D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe',
        'D:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe'
    )
    foreach ($candidate in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
        if (Test-Path -LiteralPath $candidate -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    throw 'Godot 4.5.1 Mono console executable was not found. Pass -GodotExe or set GODOT_4_5_1_MONO.'
}

foreach ($requiredPath in @($ProbeProject, $ImplementationDll, (Join-Path $DataDir 'sts2.dll'))) {
    if (-not (Test-Path -LiteralPath $requiredPath -PathType Leaf)) {
        throw "Required Gravetide Slug probe input was not found: $requiredPath"
    }
}
if (-not (Test-Path -LiteralPath $RuntimeDependencyDir -PathType Container)) {
    throw "Probe runtime dependency directory was not found: $RuntimeDependencyDir"
}

$DataDir = [IO.Path]::GetFullPath($DataDir)
$ImplementationDll = [IO.Path]::GetFullPath($ImplementationDll)
$RuntimeDependencyDir = [IO.Path]::GetFullPath($RuntimeDependencyDir)
$GodotExe = Resolve-GodotConsoleExecutable $GodotExe
$godotVersion = (& $GodotExe --version | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or
    -not $godotVersion.StartsWith('4.5.1.stable.mono', [StringComparison]::OrdinalIgnoreCase)) {
    throw "Expected Godot 4.5.1 Mono, got '$godotVersion'."
}

$portableDotnet = Join-Path $Root '.tmp\dotnet9'
if (Test-Path -LiteralPath (Join-Path $portableDotnet 'dotnet.exe') -PathType Leaf) {
    $env:DOTNET_ROOT = $portableDotnet
    $env:DOTNET_MULTILEVEL_LOOKUP = '0'
    $env:DOTNET_ROLL_FORWARD = 'Major'
}

Write-Host "Building Gravetide Slug behavior probe for $TargetVersion..."
& dotnet build $ProbeProject -c Debug --nologo `
    "/p:Sts2DataDir=$DataDir" `
    "/p:RuntimeDependencyDir=$RuntimeDependencyDir" `
    "/p:ImplementationDll=$ImplementationDll"
if ($LASTEXITCODE -ne 0) {
    throw "Gravetide Slug probe build failed for $TargetVersion with exit code $LASTEXITCODE"
}

# Both implementation assemblies intentionally share the same name and version.
# MSBuild's incremental copy can therefore retain the previously tested target
# when this project switches between v107.1 and v110. Overwrite the three target
# binaries after every build so the Godot process always loads a coherent set.
$probeBin = Join-Path $ProbeRoot '.godot\mono\temp\bin\Debug'
foreach ($binary in @(
    @{ Source = (Join-Path $DataDir 'sts2.dll'); Name = 'sts2.dll' },
    @{ Source = (Join-Path $DataDir '0Harmony.dll'); Name = '0Harmony.dll' },
    @{ Source = $ImplementationDll; Name = 'STS2_Things.dll' }
)) {
    Copy-Item -LiteralPath $binary.Source `
        -Destination (Join-Path $probeBin $binary.Name) -Force
}

$logPath = Join-Path $ProbeRoot "probe-$TargetVersion.log"
if (Test-Path -LiteralPath $logPath -PathType Leaf) {
    Remove-Item -LiteralPath $logPath -Force
}

Write-Host "Running Gravetide Slug behavior probe for $TargetVersion..."
& $GodotExe --headless --path $ProbeRoot --log-file $logPath
if ($LASTEXITCODE -ne 0) {
    throw "Gravetide Slug behavior probe failed for $TargetVersion with exit code $LASTEXITCODE"
}
if (-not (Test-Path -LiteralPath $logPath -PathType Leaf)) {
    throw "Gravetide Slug probe log was not created: $logPath"
}

$logText = Get-Content -LiteralPath $logPath -Raw
$errors = Select-String -LiteralPath $logPath `
    -Pattern '(^|\s)(SCRIPT ERROR|ERROR:|WARNING:)|Failed loading resource' `
    -CaseSensitive:$false
if ($errors) {
    $preview = ($errors | Select-Object -First 12 | ForEach-Object Line) -join [Environment]::NewLine
    throw "Gravetide Slug probe reported errors for ${TargetVersion}:`n$preview"
}
if ($logText.IndexOf('Gravetide Slug behavior probe: PASS', [StringComparison]::Ordinal) -lt 0) {
    throw "Gravetide Slug probe did not report PASS for $TargetVersion."
}

Write-Host "Gravetide Slug behavior probe passed for $TargetVersion."
