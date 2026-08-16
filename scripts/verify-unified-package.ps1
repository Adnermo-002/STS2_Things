[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string]$DataDirV1071,

    [Parameter(Mandatory)]
    [string]$DataDirV111,

    [Parameter(Mandatory)]
    [string]$BootstrapDll,

    [Parameter(Mandatory)]
    [string]$ImplementationV1071,

    [Parameter(Mandatory)]
    [string]$ImplementationV111
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..')).Path
$Project = Join-Path $Root 'tools\UnifiedPackageProbe\UnifiedPackageProbe.csproj'
$DataDirV1071 = [IO.Path]::GetFullPath($DataDirV1071)
$DataDirV111 = [IO.Path]::GetFullPath($DataDirV111)
$BootstrapDll = [IO.Path]::GetFullPath($BootstrapDll)
$ImplementationV1071 = [IO.Path]::GetFullPath($ImplementationV1071)
$ImplementationV111 = [IO.Path]::GetFullPath($ImplementationV111)

foreach ($probe in @(
    @($DataDirV1071, 'v107.1', $ImplementationV1071),
    @($DataDirV111, 'v111', $ImplementationV111)
)) {
    & dotnet run --project $Project -c Release -- `
        $probe[0] $BootstrapDll $probe[1] $probe[2] $DataDirV111
    if ($LASTEXITCODE -ne 0) {
        throw "Unified $($probe[1]) package probe failed with exit code $LASTEXITCODE"
    }
}
