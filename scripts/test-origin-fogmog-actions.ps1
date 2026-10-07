[CmdletBinding()]
param(
    [string]$ImplementationDll = 'build\v111\STS2_Things.dll',
    [switch]$Preview,
    [string]$OutputDir = 'build\origin-fogmog-impact-20261003',
    [string]$GodotExe = 'D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe'
)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskProbe = Join-Path $taskRoot 'tools\CaveGodProbe'
$taskEvidence = if ([IO.Path]::IsPathRooted($OutputDir)) { [IO.Path]::GetFullPath($OutputDir) } else { [IO.Path]::GetFullPath((Join-Path $taskRoot $OutputDir)) }
$taskOutput = Join-Path $taskEvidence 'actions'
New-Item -ItemType Directory -Path $taskOutput -Force | Out-Null
$taskImplementation = [IO.Path]::GetFullPath($ImplementationDll)
& 'C:\Program Files\dotnet\dotnet.exe' build (Join-Path $taskProbe 'CaveGodProbe.csproj') -c Debug --nologo "/p:ImplementationDll=$taskImplementation"
if ($LASTEXITCODE -ne 0) { throw 'Fogmog action probe compile failed.' }
$env:DOTNET_ROOT = Join-Path $taskRoot '.tmp\dotnet9'
$env:DOTNET_MULTILEVEL_LOOKUP = '0'
$taskArgs = @('--path',('"{0}"' -f $taskProbe),'--rendering-method','gl_compatibility','--','--fogmog-actions')
if ($Preview) {
    $taskOutput = Join-Path $taskEvidence 'preview'
    New-Item -ItemType Directory -Path $taskOutput -Force | Out-Null
    $taskArgs = @('--path',('"{0}"' -f $taskProbe),'--rendering-method','gl_compatibility','--fixed-fps','30','--','--fogmog-preview')
}
$taskArgs += @('--fogmog-output', ('"{0}"' -f $taskOutput))
$taskProcess = Start-Process -FilePath $GodotExe -ArgumentList $taskArgs -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskOutput 'probe.stdout.log') -RedirectStandardError (Join-Path $taskOutput 'probe.stderr.log')
try {
    $taskTimeout = if ($Preview) { 240000 } else { 60000 }
    if (-not $taskProcess.WaitForExit($taskTimeout)) { throw 'Fogmog action probe timed out.' }
    Get-Content -LiteralPath (Join-Path $taskOutput 'probe.stdout.log') -Tail 12
    if ($taskProcess.ExitCode -ne 0) {
        Get-Content -LiteralPath (Join-Path $taskOutput 'probe.stderr.log') -TotalCount 16
        throw "Fogmog action probe failed: $($taskProcess.ExitCode)"
    }
    $taskErrors = Select-String -LiteralPath (Join-Path $taskOutput 'probe.stderr.log') -Pattern '^ERROR:|SCRIPT ERROR'
    if ($taskErrors) { throw ($taskErrors.Line -join [Environment]::NewLine) }
    $taskPass = if ($Preview) { 'OriginFogmog preview: PASS' } else { 'OriginFogmog action regression: PASS' }
    if (-not (Select-String -LiteralPath (Join-Path $taskOutput 'probe.stdout.log') -Pattern $taskPass -Quiet)) { throw 'Fogmog probe did not report PASS.' }
}
finally {
    if (-not $taskProcess.HasExited) { Stop-Process -InputObject $taskProcess }
    $taskProcess.Dispose()
}
