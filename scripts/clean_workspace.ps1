[CmdletBinding()]
param([switch]$Apply)

$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$rootPrefix = $projectRoot.TrimEnd('\') + '\'
$reportRoot = Join-Path $projectRoot 'build\workspace-cleanup'
$candidates = @{}

function Assert-ProjectPath([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    if (-not $full.StartsWith($rootPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Target is outside the project: $full"
    }
    $item = Get-Item -LiteralPath $full -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw "Refusing a linked target: $full"
    }
    $ancestor = Split-Path -Parent $full
    while ($ancestor -ne $projectRoot) {
        if ((Get-Item -LiteralPath $ancestor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw "Refusing a target below a linked directory: $full"
        }
        $ancestor = Split-Path -Parent $ancestor
    }
    return $full
}

function Add-Candidate([IO.FileInfo]$File, [string]$Reason) {
    $full = Assert-ProjectPath $File.FullName
    $relative = [IO.Path]::GetRelativePath($projectRoot, $full).Replace('\', '/')
    # Historical sources and rollback copies can be the only remaining copy.
    if ($relative -match '(?i)(^|/)([^/]*(backup|before|baseline|original|modified|rollback|installed)[^/]*)(/|$)') { return }
    if ($relative.StartsWith('build/origin-fogmog-repair/') -or
        $relative.StartsWith('build/workspace-cleanup/')) { return }
    $candidates[$full] = [pscustomobject][ordered]@{ path = $relative; bytes = $File.Length; reason = $Reason }
}

# Import descriptors under this .gdignore directory are obsolete editor output.
Get-ChildItem -LiteralPath (Join-Path $projectRoot 'source_assets') -Recurse -File -Filter '*.import' |
    ForEach-Object { Add-Candidate $_ 'editor import metadata for excluded source art' }

Get-ChildItem -LiteralPath $projectRoot -File -Force | ForEach-Object {
    if ($_.Extension -eq '.log' -or $_.Name -in @('diff_background.txt', 'STS2_Things.dll', 'STS2_Things.pck') -or
        ($_.Name.EndsWith('.import') -and -not (Test-Path -LiteralPath $_.FullName.Substring(0, $_.FullName.Length - 7)))) {
        Add-Candidate $_ 'stale root build, diagnostic output, or orphan import'
    }
}

# Remove regenerable frame sequences, not image-generation candidates or artwork.
$buildRoot = Join-Path $projectRoot 'build'
Get-ChildItem -LiteralPath $buildRoot -Recurse -File -Force | ForEach-Object {
    $relative = [IO.Path]::GetRelativePath($buildRoot, $_.FullName).Replace('\', '/')
    if ($relative -match '^(v107\.1|v111|unified|release|deliverables|imagegen)/') { return }
    if ($_.Extension -eq '.log') { Add-Candidate $_ 'old diagnostic log' }
    elseif ($_.Name -match '^(idle(_loop)?|attack|cast|hurt|die|summon|power_up|revive|slam|windup|frame)[_-][0-9]{3,}\.png$') {
        Add-Candidate $_ 'rendered animation frame (rebuildable)'
    }
    elseif (($relative -match '^v(108|109|109-probe|110)/' -or $_.DirectoryName -eq $buildRoot) -and
            $_.Extension -in @('.pck', '.dll', '.pdb')) {
        Add-Candidate $_ 'obsolete diagnostic build; supported builds use v107.1/v111/unified'
    }
}

# Probe/build caches only. Keep the main Godot cache and portable SDKs used by tests.
foreach ($scope in @('tools', 'bootstrap', 'bridges')) {
    $directory = Join-Path $projectRoot $scope
    Get-ChildItem -LiteralPath $directory -Recurse -File -Force | ForEach-Object {
        $relative = [IO.Path]::GetRelativePath($directory, $_.FullName).Replace('\', '/')
        if ($relative -match '(^|/)(\.godot|bin|obj|__pycache__)/') {
            Add-Candidate $_ 'generated probe/compiler cache'
        }
    }
}
foreach ($cache in @('.tmp\dual-obj-v107', '.tmp\gravetide-qa-obj-v107.1', '.tmp\gravetide-qa-obj-v109', 'scripts\__pycache__',
                     'tools\OriginFogmogRig\legacy_v2\out', 'tools\OriginFogmogRig\legacy_v2\pkg',
                     'tools\OriginFogmogRig\legacy_v2\parts', 'tools\OriginFogmogRig\legacy_v2\review_v1')) {
    $directory = Join-Path $projectRoot $cache
    if (Test-Path -LiteralPath $directory) {
        Get-ChildItem -LiteralPath $directory -Recurse -File -Force |
            ForEach-Object { Add-Candidate $_ 'generated compiler/Python cache or retired rig output' }
    }
}

$entries = @($candidates.Values | Sort-Object path)
$total = ($entries | Measure-Object -Property bytes -Sum).Sum
New-Item -ItemType Directory -Path $reportRoot -Force | Out-Null
$manifest = Join-Path $reportRoot $(if ($Apply) { 'deleted-files.json' } else { 'plan.json' })
if ($Apply -and (Test-Path -LiteralPath $manifest)) {
    $manifest = Join-Path $reportRoot ('deleted-files-{0}.json' -f (Get-Date -Format 'yyyyMMdd-HHmmss'))
}
$entries | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $manifest -Encoding utf8
$entries | Group-Object reason | ForEach-Object {
    [pscustomobject]@{ Reason = $_.Name; Files = $_.Count; MiB = [Math]::Round(($_.Group | Measure-Object bytes -Sum).Sum / 1MB, 2) }
} | Format-Table -AutoSize
Write-Host ("{0}: {1} files, {2:N2} MiB. Manifest: {3}" -f $(if ($Apply) {'Removing'} else {'Dry run'}), $entries.Count, ($total / 1MB), $manifest)
if (-not $Apply) { return }

foreach ($entry in $entries) {
    $full = Assert-ProjectPath (Join-Path $projectRoot $entry.path)
    if ((Get-Item -LiteralPath $full).Length -ne $entry.bytes) { throw "File changed since inventory: $full" }
    Remove-Item -LiteralPath $full -Force
}

# Remove only empty scaffolding/cache directories; never remove source trees recursively.
$emptyScopes = @('export_templates', 'feature_profiles', 'script_templates', 'text_editor_themes',
                 'tools', 'bootstrap', 'bridges', '.tmp\dual-obj-v107', '.tmp\gravetide-qa-obj-v107.1', '.tmp\gravetide-qa-obj-v109')
foreach ($scope in $emptyScopes) {
    $directory = Join-Path $projectRoot $scope
    if (-not (Test-Path -LiteralPath $directory)) { continue }
    $dirs = @((Get-Item -LiteralPath $directory)) + @(Get-ChildItem -LiteralPath $directory -Recurse -Directory -Force)
    foreach ($dir in ($dirs | Sort-Object { $_.FullName.Length } -Descending)) {
        if (-not (Get-ChildItem -LiteralPath $dir.FullName -Force | Select-Object -First 1)) {
            $full = Assert-ProjectPath $dir.FullName
            Remove-Item -LiteralPath $full -Force
        }
    }
}
