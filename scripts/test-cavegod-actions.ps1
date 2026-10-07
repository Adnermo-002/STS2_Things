[CmdletBinding()]
param(
    [string]$ImplementationDll = 'build\v111\STS2_Things.dll',
    [switch]$NoImages,
    [switch]$BakeRightGrab,
    [switch]$BakeCardSnatch,
    [switch]$CardSnatch,
    [switch]$SmoothPreview,
    [switch]$ContactReview,
    [switch]$RecoveryReview,
    [string]$RecoveryClip = '',
    [switch]$RecoveryNoAim,
    [string]$PackagePck = '',
    [string]$OverlayPck = '',
    [string]$OutputDirectory = 'build\cavegod-actions-20261002',
    [string]$GodotExe = 'D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe'
)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskProbe = Join-Path $taskRoot 'tools\CaveGodProbe'
$taskOutput = [IO.Path]::GetFullPath((Join-Path $taskRoot $OutputDirectory))
New-Item -ItemType Directory -Path $taskOutput -Force | Out-Null
$taskImplementation = [IO.Path]::GetFullPath($ImplementationDll)
if ($PackagePck) { $env:THINGS_PROBE_PCK = [IO.Path]::GetFullPath($PackagePck) }
$env:THINGS_PROBE_OVERLAY_PCK=if($OverlayPck){[IO.Path]::GetFullPath($OverlayPck)}else{$null}
& 'C:\Program Files\dotnet\dotnet.exe' build (Join-Path $taskProbe 'CaveGodProbe.csproj') -c Debug --nologo "/p:ImplementationDll=$taskImplementation"
if ($LASTEXITCODE -ne 0) { throw 'CaveGod action probe compile failed.' }
$env:DOTNET_ROOT = Join-Path $taskRoot '.tmp\dotnet9'
$env:DOTNET_MULTILEVEL_LOOKUP = '0'
$taskArgs = @('--path',('"{0}"' -f $taskProbe),'--rendering-method','gl_compatibility','--resolution','1920x1080','--','--action-regression','--action-output',('"{0}"' -f $taskOutput))
if ($NoImages) { $taskArgs += '--no-images' }
if ($BakeRightGrab) { $taskArgs += '--bake-right-grab' }
if ($BakeCardSnatch) { $taskArgs += '--bake-card-snatch' }
if ($CardSnatch) { $taskArgs += '--card-snatch' }
if ($SmoothPreview) { $taskArgs += '--smooth-preview' }
if ($ContactReview) { $taskArgs += '--contact-review' }
if ($RecoveryReview) { $taskArgs += '--recovery-review' }
if ($RecoveryClip) { $taskArgs += @('--recovery-clip', $RecoveryClip) }
if ($RecoveryNoAim) { $taskArgs += '--recovery-no-aim' }
$taskProcess = Start-Process -FilePath $GodotExe -ArgumentList $taskArgs -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskOutput 'probe.stdout.log') -RedirectStandardError (Join-Path $taskOutput 'probe.stderr.log')
try {
    $taskTimeout = if ($ContactReview -or ($CardSnatch -and -not $NoImages)) { 240000 } else { 45000 }
    if (-not $taskProcess.WaitForExit($taskTimeout)) { throw 'CaveGod action probe timed out.' }
    Get-Content -LiteralPath (Join-Path $taskOutput 'probe.stdout.log') -Tail 20
    if ($taskProcess.ExitCode -ne 0) {
        Get-Content -LiteralPath (Join-Path $taskOutput 'probe.stderr.log') -TotalCount 12
        throw "CaveGod action probe failed: $($taskProcess.ExitCode)"
    }
    $taskErrors = Select-String -LiteralPath (Join-Path $taskOutput 'probe.stderr.log') -Pattern '^ERROR:|SCRIPT ERROR'
    if ($taskErrors) { throw ($taskErrors.Line -join [Environment]::NewLine) }
    if (-not (Select-String -LiteralPath (Join-Path $taskOutput 'probe.stdout.log') -Pattern 'CaveGod action regression: PASS' -Quiet)) { throw 'Action probe did not report PASS.' }
}
finally {
    if (-not $taskProcess.HasExited) { Stop-Process -InputObject $taskProcess }
    $taskProcess.Dispose()
}
