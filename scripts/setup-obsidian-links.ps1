# Obsidian on Windows garbles Chinese *junction* folder names.
# Use ASCII junctions (.site / .docs) + Chinese regular folders for navigation.

$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$vaultRoot = 'F:\MedLearn Vault'
$medlearnRoot = Join-Path $vaultRoot 'Medlearn'

$junctions = @(
    @{ Name = '.site'; Target = Join-Path $repoRoot 'site' },
    @{ Name = '.docs'; Target = Join-Path $repoRoot 'docs' }
)

$chineseFolders = @('10 发布文档', '11 工程文档')

$legacyPaths = @(
    (Join-Path $vaultRoot '发布文档'),
    (Join-Path $vaultRoot '工程文档'),
    (Join-Path $medlearnRoot '10-site'),
    (Join-Path $medlearnRoot '11-docs'),
    (Join-Path $medlearnRoot '10 发布文档'),
    (Join-Path $medlearnRoot '11 工程文档')
)

if (-not (Test-Path $vaultRoot)) {
    Write-Error "MedLearn Vault not found at $vaultRoot"
}

if (-not (Test-Path $medlearnRoot)) {
    New-Item -ItemType Directory -Path $medlearnRoot | Out-Null
}

function Remove-JunctionIfPresent([string]$Path) {
    if (-not (Test-Path $Path)) { return }
    $item = Get-Item $Path -Force
    if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) {
        cmd /c rmdir "$Path" | Out-Null
        Write-Host "REMOVE junction $Path"
    }
}

foreach ($legacyPath in $legacyPaths) {
    Remove-JunctionIfPresent $legacyPath
}

# Mojibake duplicates from earlier Chinese junction attempts (Obsidian/Windows).
$garbledFolders = @('10 鍙戝竷鏂囨。', '11 宸ョ▼鏂囨。')
foreach ($name in $garbledFolders) {
    $path = Join-Path $medlearnRoot $name
    if (Test-Path $path) {
        cmd /c rmdir "$path" 2>$null
        if (Test-Path $path) { Remove-Item -LiteralPath $path -Recurse -Force }
        Write-Host "REMOVE garbled folder $name"
    }
}

foreach ($folder in $chineseFolders) {
    $path = Join-Path $medlearnRoot $folder
    if (-not (Test-Path $path)) {
        New-Item -ItemType Directory -Path $path | Out-Null
        Write-Host "MKDIR $path"
    }
}

foreach ($junction in $junctions) {
    $junctionPath = Join-Path $medlearnRoot $junction.Name
    $targetPath = $junction.Target

    if (-not (Test-Path $targetPath)) {
        Write-Error "Target path missing: $targetPath"
    }

    Remove-JunctionIfPresent $junctionPath

    cmd /c mklink /J "$junctionPath" "$targetPath" | Out-Null
    Write-Host "LINK $junctionPath -> $targetPath"
}

Write-Host 'Done. Chinese folders = navigation; .site/.docs = real repo files.'