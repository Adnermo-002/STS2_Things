[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$DataDirV1071,

    [Parameter(Mandatory)]
    [string]$DataDirV110,

    [Parameter(Mandatory)]
    [string]$BootstrapDll,

    [Parameter(Mandatory)]
    [string]$ImplementationV1071,

    [Parameter(Mandatory)]
    [string]$ImplementationV110
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$Project = Join-Path $Root 'tools\UnifiedPackageProbe\UnifiedPackageProbe.csproj'
$DataDirV1071 = [IO.Path]::GetFullPath($DataDirV1071)
$DataDirV110 = [IO.Path]::GetFullPath($DataDirV110)
$BootstrapDll = [IO.Path]::GetFullPath($BootstrapDll)
$ImplementationV1071 = [IO.Path]::GetFullPath($ImplementationV1071)
$ImplementationV110 = [IO.Path]::GetFullPath($ImplementationV110)

foreach ($probe in @(
    @($DataDirV1071, 'v107.1', $ImplementationV1071),
    @($DataDirV110, 'v110', $ImplementationV110)
)) {
    & dotnet run --project $Project -c Release -- `
        $probe[0] $BootstrapDll $probe[1] $probe[2] $DataDirV110
    if ($LASTEXITCODE -ne 0) {
        throw "Unified $($probe[1]) package probe failed with exit code $LASTEXITCODE"
    }
}
