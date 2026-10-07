[CmdletBinding()]
param(
    [string]$PythonExe = 'python',
    [string]$NodeExe = 'node',
    [switch]$Deploy
)
$ErrorActionPreference = 'Stop'
$rigRoot = Join-Path $PSScriptRoot 'v3'
Push-Location $rigRoot
try {
    if (-not (Test-Path -LiteralPath 'node_modules\@esotericsoftware\spine-core')) {
        & npm ci --ignore-scripts --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw 'npm ci failed' }
    }
    & $NodeExe snapshot.mjs source/origin_fogmog.spjson source/origin_fogmog.atlas out/bind.json idle_loop
    if ($LASTEXITCODE -ne 0) { throw 'Spine bind snapshot failed' }
    & $PythonExe build.py
    if ($LASTEXITCODE -ne 0) { throw 'Skin rebuild failed' }
    & $NodeExe verify.mjs
    if ($LASTEXITCODE -ne 0) { throw 'Joint regression failed' }
    & $NodeExe motion.mjs
    if ($LASTEXITCODE -ne 0) { throw 'Boss motion build failed' }
    & $NodeExe verify.mjs out/origin_fogmog_boss.spjson source/origin_fogmog.atlas --authored-motion
    if ($LASTEXITCODE -ne 0) { throw 'Authored motion seam regression failed' }
    & $NodeExe verify_motion.mjs
    if ($LASTEXITCODE -ne 0) { throw 'Boss motion regression failed' }
    if ($Deploy) {
        $destination = Join-Path $PSScriptRoot '..\..\STS2_Things\animations\monsters\origin_fogmog'
        foreach ($suffix in @('spjson', 'png', 'atlas', 'spatlas')) {
            $source = if ($suffix -eq 'spjson') { 'out\origin_fogmog_boss.spjson' } else { "out\origin_fogmog.$suffix" }
            Copy-Item -LiteralPath $source -Destination (Join-Path $destination "origin_fogmog.$suffix") -Force
        }
        Write-Host 'Updated project assets. Run scripts/build.ps1 to import, validate and package.'
    }
}
finally { Pop-Location }
