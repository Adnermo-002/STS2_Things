[CmdletBinding()]
param(
    [string]$ImplementationDll = 'build\v111\STS2_Things.dll',
    [switch]$Ui,
    [string]$GodotExe = 'D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe'
)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskOutput = Join-Path $taskRoot 'build\crossroads-20261003'
$taskProbe = Join-Path $taskRoot 'tools\CaveGodProbe'
New-Item -ItemType Directory -Path $taskOutput -Force | Out-Null
$taskImplementation = [IO.Path]::GetFullPath($ImplementationDll)
& 'C:\Program Files\dotnet\dotnet.exe' build (Join-Path $taskProbe 'CaveGodProbe.csproj') -c Debug --nologo "/p:ImplementationDll=$taskImplementation"
if ($LASTEXITCODE -ne 0) { throw 'Crossroad probe compilation failed.' }
$env:DOTNET_ROOT = Join-Path $taskRoot '.tmp\dotnet9'
$env:DOTNET_MULTILEVEL_LOOKUP = '0'
$taskMode = if ($Ui) { 'ui' } else { 'rules' }
$taskFlag = if ($Ui) { '--crossroads-ui' } else { '--crossroads' }
$taskArgs = @('--path', ('"{0}"' -f $taskProbe), '--rendering-method', 'gl_compatibility', '--fixed-fps', '60', '--', $taskFlag)
if (-not $Ui) { $taskArgs = @('--headless') + $taskArgs }
$taskStdout = Join-Path $taskOutput "$taskMode.stdout.log"
$taskStderr = Join-Path $taskOutput "$taskMode.stderr.log"
$taskProcess = Start-Process -FilePath $GodotExe -ArgumentList $taskArgs -WindowStyle Hidden -PassThru -RedirectStandardOutput $taskStdout -RedirectStandardError $taskStderr
try {
    if (-not $taskProcess.WaitForExit(60000)) { throw 'Crossroad probe timed out.' }
    Get-Content -LiteralPath $taskStdout -Tail 5
    $taskErrors = Select-String -LiteralPath $taskStderr -Pattern 'ERROR:|SCRIPT ERROR'
    if ($taskProcess.ExitCode -ne 0 -or $taskErrors) {
        Get-Content -LiteralPath $taskStderr -First 12
        throw 'Crossroad probe failed; see the evidence logs.'
    }
    $taskPass = if ($Ui) { 'CROSSROADS_UI_PASS' } else { 'CROSSROADS_RULES_PASS' }
    if (-not (Select-String -LiteralPath $taskStdout -Pattern $taskPass -Quiet)) { throw 'Crossroad probe did not report PASS.' }
}
finally {
    if (-not $taskProcess.HasExited) { Stop-Process -InputObject $taskProcess }
    $taskProcess.Dispose()
}
