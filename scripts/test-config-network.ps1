[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$DataDir,
    [Parameter(Mandatory)][string]$ImplementationDll,
    [Parameter(Mandatory)][string]$Pck,
    [string]$RuntimeDependencyDir = $DataDir,
    [string]$GodotExe = 'D:\Download\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64\Godot_v4.5.1-stable_mono_win64_console.exe',
    [string]$OutputDirectory = 'build\multiplayer-config-20261002\enet',
    [ushort]$Port = 29342
)
$ErrorActionPreference = 'Stop'
$taskRoot = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$taskProbe = Join-Path $taskRoot 'tools\ThingsConfigProbe'
$taskOutput = [IO.Path]::GetFullPath((Join-Path $taskRoot $OutputDirectory))
if (-not $taskOutput.StartsWith($taskRoot + '\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Output must stay inside the project.' }
New-Item -ItemType Directory -Path $taskOutput -Force | Out-Null
$taskDll = [IO.Path]::GetFullPath($ImplementationDll)
$taskPack = [IO.Path]::GetFullPath($Pck)
$taskData = [IO.Path]::GetFullPath($DataDir)
$taskRuntime = [IO.Path]::GetFullPath($RuntimeDependencyDir)
& 'C:\Program Files\dotnet\dotnet.exe' build (Join-Path $taskProbe 'ThingsConfigProbe.csproj') -t:Rebuild -c Debug --nologo "/p:Sts2DataDir=$taskData" "/p:RuntimeDependencyDir=$taskRuntime" "/p:ImplementationDll=$taskDll"
if ($LASTEXITCODE -ne 0) { throw 'Network probe build failed.' }
$env:DOTNET_ROOT = Join-Path $taskRoot '.tmp\dotnet9'
$env:DOTNET_MULTILEVEL_LOOKUP = '0'
$taskProcesses = @()
$taskRunners = @()
try {
    foreach ($taskRole in @('host','client1','client2')) {
        $taskRunner = Join-Path $taskOutput $taskRole
        if (Test-Path -LiteralPath $taskRunner) { throw "Runner already exists: $taskRunner" }
        New-Item -ItemType Directory -Path $taskRunner | Out-Null
        $taskRunners += $taskRunner
        Get-ChildItem -LiteralPath $taskProbe -File | Where-Object { $_.Extension -in '.cs','.tscn' } | Copy-Item -Destination $taskRunner
        $taskSettings = (Get-Content -LiteralPath (Join-Path $taskProbe 'project.godot') -Raw).Replace('Things Config Probe','Things Config Probe ENet ' + $taskRole)
        $taskSettings | Set-Content -LiteralPath (Join-Path $taskRunner 'project.godot') -Encoding utf8
        $taskBin = Join-Path $taskRunner '.godot\mono\temp\bin'
        New-Item -ItemType Directory -Path $taskBin -Force | Out-Null
        Copy-Item -LiteralPath (Join-Path $taskProbe '.godot\mono\temp\bin\Debug') -Destination $taskBin -Recurse
        foreach ($taskName in @($taskRole + '.result', 'host-ready')) {
            $taskOld = Join-Path $taskOutput $taskName
            if (Test-Path -LiteralPath $taskOld) { Remove-Item -LiteralPath $taskOld }
        }
        $taskArguments = @('--headless','--path',('"{0}"' -f $taskRunner),'--','"' + $taskPack + '"',$taskRole,$Port,('"{0}"' -f $taskOutput))
        $taskProcess = Start-Process -FilePath $GodotExe -ArgumentList $taskArguments -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $taskOutput ($taskRole + '.stdout.log')) -RedirectStandardError (Join-Path $taskOutput ($taskRole + '.stderr.log'))
        $taskProcesses += $taskProcess
        if ($taskRole -eq 'host') {
            $taskDeadline = [DateTime]::UtcNow.AddSeconds(15)
            while (-not (Test-Path -LiteralPath (Join-Path $taskOutput 'host-ready'))) {
                if ($taskProcess.HasExited -or [DateTime]::UtcNow -gt $taskDeadline) { throw 'Host did not become ready. Inspect host logs.' }
                Start-Sleep -Milliseconds 200
            }
        }
    }
    $taskDeadline = [DateTime]::UtcNow.AddSeconds(40)
    while (@($taskProcesses | Where-Object { -not $_.HasExited }).Count -gt 0) {
        if ([DateTime]::UtcNow -gt $taskDeadline) { throw 'Network probe timed out.' }
        Start-Sleep -Milliseconds 300
    }
    foreach ($taskRole in @('host','client1','client2')) {
        $taskResult = Join-Path $taskOutput ($taskRole + '.result')
        if (-not (Test-Path -LiteralPath $taskResult)) { throw "Missing success report: $taskRole" }
        Get-Content -LiteralPath $taskResult
    }
    $taskReports = @('host','client1','client2') | ForEach-Object { Get-Content -LiteralPath (Join-Path $taskOutput ($_ + '.result')) }
    if (@($taskReports | Select-Object -Unique).Count -ne 1) { throw 'Room digests differed between processes.' }
    Write-Host 'Three-process ENet config probe: PASS'
}
finally {
    foreach ($taskProcess in $taskProcesses) {
        if (-not $taskProcess.HasExited) { Stop-Process -InputObject $taskProcess }
        $taskProcess.Dispose()
    }
    foreach ($taskRunner in $taskRunners) {
        $taskResolved = [IO.Path]::GetFullPath($taskRunner)
        if ((Split-Path -Parent $taskResolved) -ne $taskOutput -or (Split-Path -Leaf $taskResolved) -notin @('host','client1','client2')) { throw 'Unsafe runner cleanup target.' }
        Remove-Item -LiteralPath $taskResolved -Recurse -Force
    }
}
