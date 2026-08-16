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
$ProbeRoot = Join-Path $Root 'tools\QuirkyHopperProbe'
$ProbeProject = Join-Path $ProbeRoot 'QuirkyHopperProbe.csproj'

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
        throw "Required Quirky Hopper probe input was not found: $requiredPath"
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

Write-Host "Building Quirky Hopper behavior probe for $TargetVersion..."
& dotnet build $ProbeProject -t:Rebuild -c Debug --nologo `
    "/p:Sts2DataDir=$DataDir" `
    "/p:RuntimeDependencyDir=$RuntimeDependencyDir" `
    "/p:ImplementationDll=$ImplementationDll"
if ($LASTEXITCODE -ne 0) {
    throw "Quirky Hopper probe build failed for $TargetVersion with exit code $LASTEXITCODE"
}

$logPath = Join-Path $ProbeRoot "probe-$TargetVersion.log"
if (Test-Path -LiteralPath $logPath -PathType Leaf) {
    Remove-Item -LiteralPath $logPath -Force
}

Write-Host "Running Quirky Hopper behavior probe for $TargetVersion..."
& $GodotExe --headless --path $ProbeRoot --log-file $logPath
if ($LASTEXITCODE -ne 0) {
    throw "Quirky Hopper behavior probe failed for $TargetVersion with exit code $LASTEXITCODE"
}
if (-not (Test-Path -LiteralPath $logPath -PathType Leaf)) {
    throw "Quirky Hopper probe log was not created: $logPath"
}

$logText = Get-Content -LiteralPath $logPath -Raw
$errors = Select-String -LiteralPath $logPath `
    -Pattern '(^|\s)(SCRIPT ERROR|ERROR:|WARNING:)|Failed loading resource' `
    -CaseSensitive:$false
if ($errors) {
    $preview = ($errors | Select-Object -First 12 | ForEach-Object Line) -join [System.Environment]::NewLine
    throw "Quirky Hopper probe reported errors for ${TargetVersion}:`n$preview"
}
if ($logText.IndexOf('Quirky Hopper behavior probe: PASS', [StringComparison]::Ordinal) -lt 0) {
    throw "Quirky Hopper probe did not report PASS for $TargetVersion."
}

Write-Host "Quirky Hopper behavior probe passed for $TargetVersion."
