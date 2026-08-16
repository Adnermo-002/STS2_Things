[CmdletBinding()]
param(
    [string]$PythonExe = $env:STS2_PYTHON,

    [string]$GodotExe = $env:GODOT_4_5_1_MONO,

    [string]$OutputDir
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$RenderScript = Join-Path $PSScriptRoot 'render_quirky_hopper_visual_probe.gd'
$VerifyScript = Join-Path $PSScriptRoot 'verify_quirky_hopper_visual_probe.py'

function Resolve-PythonExecutable([string]$Requested) {
    $candidates = @()
    if (-not [string]::IsNullOrWhiteSpace($Requested)) {
        $candidates += $Requested
    }
    $candidates += Join-Path $env:USERPROFILE `
        '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    foreach ($candidate in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            continue
        }
        & $candidate -X utf8 -c 'import PIL, numpy' 2>$null
        if ($LASTEXITCODE -eq 0) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    throw 'Python with Pillow and NumPy was not found. Pass -PythonExe or set STS2_PYTHON.'
}

function Resolve-GodotExecutables([string]$Requested) {
    $candidates = @()
    if (-not [string]::IsNullOrWhiteSpace($Requested)) {
        $candidates += $Requested
    }
    $candidates += @(
        'D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe',
        'D:\Godot\Godot_v4.5.1-stable_mono_win64_console.exe'
    )

    foreach ($candidate in ($candidates | Where-Object { $_ } | Select-Object -Unique)) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            continue
        }
        $resolved = (Resolve-Path -LiteralPath $candidate).Path
        $directory = Split-Path -Parent $resolved
        $name = [IO.Path]::GetFileNameWithoutExtension($resolved)
        if ($name.EndsWith('_console', [StringComparison]::OrdinalIgnoreCase)) {
            $console = $resolved
            $gui = Join-Path $directory ($name.Substring(0, $name.Length - 8) + '.exe')
        }
        else {
            $gui = $resolved
            $console = Join-Path $directory ($name + '_console.exe')
        }
        if ((Test-Path -LiteralPath $gui -PathType Leaf) -and
            (Test-Path -LiteralPath $console -PathType Leaf)) {
            return @($gui, $console)
        }
    }
    throw 'Godot 4.5.1 Mono GUI/console executables were not found.'
}

function Quote-ProcessArgument([string]$Value) {
    return '"' + $Value.Replace('"', '\"') + '"'
}

foreach ($path in @($RenderScript, $VerifyScript)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Quirky Hopper visual probe input was not found: $path"
    }
}
if ([string]::IsNullOrWhiteSpace($OutputDir)) {
    $OutputDir = Join-Path $Root 'build\quirky_hopper_visual_probe'
}
$OutputDir = [IO.Path]::GetFullPath($OutputDir)
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$PythonExe = Resolve-PythonExecutable $PythonExe
$godotExecutables = Resolve-GodotExecutables $GodotExe
$godotGui = $godotExecutables[0]
$godotConsole = $godotExecutables[1]
$godotVersion = (& $godotConsole --version | Out-String).Trim()
if ($LASTEXITCODE -ne 0 -or
    -not $godotVersion.StartsWith('4.5.1.stable.mono', [StringComparison]::OrdinalIgnoreCase)) {
    throw "Expected Godot 4.5.1 Mono, got '$godotVersion'."
}

$logPath = Join-Path $Root 'build\quirky-hopper-visual-render.log'
if (Test-Path -LiteralPath $logPath -PathType Leaf) {
    Remove-Item -LiteralPath $logPath -Force
}
$arguments = @(
    '--path', (Quote-ProcessArgument $Root),
    '--script', 'res://scripts/render_quirky_hopper_visual_probe.gd',
    '--log-file', (Quote-ProcessArgument $logPath),
    '--', (Quote-ProcessArgument $OutputDir)
)

Write-Host 'Rendering Quirky Hopper animation contract...'
$process = Start-Process `
    -FilePath $godotGui `
    -ArgumentList $arguments `
    -WindowStyle Hidden `
    -PassThru
if (-not $process.WaitForExit(60000)) {
    Stop-Process -Id $process.Id -Force
    throw 'Quirky Hopper visual renderer timed out after 60 seconds.'
}
$process.Refresh()
if ($process.ExitCode -ne 0) {
    $tail = if (Test-Path -LiteralPath $logPath) {
        (Get-Content -LiteralPath $logPath -Tail 80) -join [System.Environment]::NewLine
    }
    else {
        '<missing log>'
    }
    throw "Quirky Hopper visual renderer exited with $($process.ExitCode):`n$tail"
}
if (-not (Test-Path -LiteralPath $logPath -PathType Leaf)) {
    throw "Quirky Hopper visual renderer log was not created: $logPath"
}
$renderErrors = Select-String -LiteralPath $logPath `
    -Pattern '(^|\s)(SCRIPT ERROR|ERROR:|WARNING:)|Failed loading resource' `
    -CaseSensitive:$false
if ($renderErrors) {
    $preview = ($renderErrors | Select-Object -First 12 | ForEach-Object Line) `
        -join [System.Environment]::NewLine
    throw "Quirky Hopper visual renderer reported errors:`n$preview"
}

& $PythonExe -X utf8 $VerifyScript $OutputDir
if ($LASTEXITCODE -ne 0) {
    throw "Quirky Hopper visual pixel probe failed with exit code $LASTEXITCODE"
}

Write-Host "Quirky Hopper visual probe passed: $OutputDir"

