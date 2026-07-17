[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$DataDir,

    [Parameter(Mandatory)]
    [string]$ModDll,

    [string]$DependencyDataDir = $DataDir
)

$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$Project = Join-Path $Root 'tools\HarmonyTargetProbe\HarmonyTargetProbe.csproj'
$DataDir = [IO.Path]::GetFullPath($DataDir)
$ModDll = [IO.Path]::GetFullPath($ModDll)
$DependencyDataDir = [IO.Path]::GetFullPath($DependencyDataDir)

& dotnet run --project $Project -c Release `
    "-p:Sts2DataDir=$DataDir" -- `
    $DataDir $ModDll $DependencyDataDir
if ($LASTEXITCODE -ne 0) {
    throw "Harmony target probe failed with exit code $LASTEXITCODE"
}
