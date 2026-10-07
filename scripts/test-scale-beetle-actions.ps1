[CmdletBinding()]
param(
    [string]$ImplementationDll = 'build\v111\STS2_Things.dll',
    [string]$OutputDir = 'build\scale-beetle-impact-20261003',
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
if ($LASTEXITCODE -ne 0) { throw 'ScaleBeetle action probe compile failed.' }
$env:DOTNET_ROOT = Join-Path $taskRoot '.tmp\dotnet9'
$env:DOTNET_MULTILEVEL_LOOKUP = '0'
$taskArgs = @('--path',('"{0}"' -f $taskProbe),'--rendering-method','gl_compatibility','--','--scale-beetle-actions')
$taskArgs += @('--scale-beetle-output', ('"{0}"' -f $taskOutput))
$taskProcess = Start-Process -FilePath $GodotExe -ArgumentList $taskArgs -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskOutput 'probe.stdout.log') -RedirectStandardError (Join-Path $taskOutput 'probe.stderr.log')
try {
    $taskTimeout = 90000
    if (-not $taskProcess.WaitForExit($taskTimeout)) { throw 'ScaleBeetle action probe timed out.' }
    Get-Content -LiteralPath (Join-Path $taskOutput 'probe.stdout.log') -Tail 12
    if ($taskProcess.ExitCode -ne 0) {
        Get-Content -LiteralPath (Join-Path $taskOutput 'probe.stderr.log') -TotalCount 16
        throw "ScaleBeetle action probe failed: $($taskProcess.ExitCode)"
    }
    $taskErrors = Select-String -LiteralPath (Join-Path $taskOutput 'probe.stderr.log') -Pattern '^ERROR:|SCRIPT ERROR'
    if ($taskErrors) {
        $taskErrors | Select-Object -First 6 | ForEach-Object { Write-Output $_.Line }
        throw "ScaleBeetle probe logged $($taskErrors.Count) errors; see $taskOutput\probe.stderr.log"
    }
    $taskPass = 'ThingsScaleBeetle action regression: PASS'
    if (-not (Select-String -LiteralPath (Join-Path $taskOutput 'probe.stdout.log') -Pattern $taskPass -Quiet)) { throw 'ScaleBeetle probe did not report PASS.' }
}
finally {
    if (-not $taskProcess.HasExited) { Stop-Process -InputObject $taskProcess }
    $taskProcess.Dispose()
}
