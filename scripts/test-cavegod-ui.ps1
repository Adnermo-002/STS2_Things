[CmdletBinding()]
param(
    [string]$ImplementationDll = 'build\v111\STS2_Things.dll',
    [string]$GodotExe = 'D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe'
)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskProbe = Join-Path $taskRoot 'tools\CaveGodProbe'
$taskOutput = Join-Path $taskRoot 'build\cavegod-ui-20261002'
New-Item -ItemType Directory -Path $taskOutput -Force | Out-Null
$taskImplementation = [IO.Path]::GetFullPath($ImplementationDll)
& 'C:\Program Files\dotnet\dotnet.exe' build (Join-Path $taskProbe 'CaveGodProbe.csproj') -c Debug --nologo "/p:ImplementationDll=$taskImplementation"
if ($LASTEXITCODE -ne 0) { throw 'CaveGod UI probe compile failed.' }
$env:DOTNET_ROOT = Join-Path $taskRoot '.tmp\dotnet9'
$env:DOTNET_MULTILEVEL_LOOKUP = '0'
$taskArgs = @('--path',('"{0}"' -f $taskProbe),'--rendering-method','gl_compatibility','--resolution','1920x1080','--','--ui-regression')
$taskProcess = Start-Process -FilePath $GodotExe -ArgumentList $taskArgs -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskOutput 'probe.stdout.log') -RedirectStandardError (Join-Path $taskOutput 'probe.stderr.log')
try {
    if (-not $taskProcess.WaitForExit(45000)) { throw 'CaveGod UI probe timed out.' }
    Get-Content -LiteralPath (Join-Path $taskOutput 'probe.stdout.log') -Tail 8
    if ($taskProcess.ExitCode -ne 0) {
        Get-Content -LiteralPath (Join-Path $taskOutput 'probe.stderr.log') -Tail 18
        throw "CaveGod UI probe failed: $($taskProcess.ExitCode)"
    }
    $taskErrors = Select-String -LiteralPath (Join-Path $taskOutput 'probe.stderr.log') -Pattern '^ERROR:|SCRIPT ERROR'
    if ($taskErrors) { throw ($taskErrors.Line -join [Environment]::NewLine) }
    if (-not (Select-String -LiteralPath (Join-Path $taskOutput 'probe.stdout.log') -Pattern 'CaveGod UI regression: PASS' -Quiet)) { throw 'CaveGod UI probe did not report PASS.' }
}
finally {
    if (-not $taskProcess.HasExited) { Stop-Process -InputObject $taskProcess }
    $taskProcess.Dispose()
}
