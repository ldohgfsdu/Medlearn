[CmdletBinding()]
param(
    [switch]$Apply
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$artifactRoot = Join-Path $repoRoot "artifacts"

if (-not (Test-Path -LiteralPath $artifactRoot)) {
    Write-Host "No artifacts directory exists."
    exit 0
}

$resolvedRoot = [System.IO.Path]::GetFullPath($artifactRoot).TrimEnd(
    [System.IO.Path]::DirectorySeparatorChar
)
$allowedNames = @(
    "medlearn-qa-arm64.apk",
    "medlearn-release-all-abi.apk"
)

# Only root-level APKs are governed here. QA screenshots, reports, and nested
# audit evidence are deliberately outside this cleanup contract.
$apkFiles = Get-ChildItem -LiteralPath $resolvedRoot -File -Filter "*.apk"
$candidates = @(
    $apkFiles | Where-Object { $allowedNames -notcontains $_.Name }
)
$kept = @(
    $apkFiles | Where-Object { $allowedNames -contains $_.Name }
)

foreach ($file in $candidates) {
    $resolvedFile = [System.IO.Path]::GetFullPath($file.FullName)
    $expectedPrefix = $resolvedRoot + [System.IO.Path]::DirectorySeparatorChar
    if (-not $resolvedFile.StartsWith(
        $expectedPrefix,
        [System.StringComparison]::OrdinalIgnoreCase
    )) {
        throw "Refusing to operate outside artifacts root: $resolvedFile"
    }
    if ($file.Extension -ne ".apk") {
        throw "Refusing to remove a non-APK artifact: $resolvedFile"
    }
}

$candidateBytes = (
    $candidates | Measure-Object -Property Length -Sum
).Sum
if ($null -eq $candidateBytes) {
    $candidateBytes = 0
}

Write-Host "Android artifact retention"
Write-Host "  root: $resolvedRoot"
Write-Host "  mode: $(if ($Apply) { 'apply' } else { 'preview' })"
Write-Host "  keep: $($kept.Count) stable APK(s)"
Write-Host "  remove: $($candidates.Count) historical APK(s)"
Write-Host "  reclaim: $([math]::Round($candidateBytes / 1MB, 1)) MB"

foreach ($file in $kept | Sort-Object Name) {
    Write-Host "  KEEP   $($file.Name)"
}
foreach ($file in $candidates | Sort-Object LastWriteTime) {
    Write-Host "  REMOVE $($file.Name)"
}

if (-not $Apply) {
    Write-Host ""
    Write-Host "Preview only. Run with -Apply to remove listed APKs."
    exit 0
}

foreach ($file in $candidates) {
    Remove-Item -LiteralPath $file.FullName -Force
}

Write-Host ""
Write-Host "Cleanup complete. Removed $($candidates.Count) APK(s)."
