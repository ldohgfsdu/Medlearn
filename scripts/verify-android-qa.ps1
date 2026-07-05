[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$artifactRoot = Join-Path $repoRoot "artifacts"
New-Item -ItemType Directory -Force -Path $artifactRoot | Out-Null
$logPath = Join-Path $artifactRoot "android-qa-gate.log"
$metadataPath = Join-Path $artifactRoot "android-qa-gate.json"
$startedAt = Get-Date

$steps = @(
    @{ Name = "Route contracts"; Args = @("run", "check:routes") },
    @{ Name = "TypeScript"; Args = @("run", "typecheck") },
    @{ Name = "Lint"; Args = @("run", "lint") }
)

$writer = New-Object System.IO.StreamWriter($logPath, $false)
$writer.AutoFlush = $true
$status = "passed"
$failedStep = $null

try {
    for ($index = 0; $index -lt $steps.Count; $index++) {
        $step = $steps[$index]
        $percent = [int](($index / $steps.Count) * 90) + 5
        Write-Progress `
            -Id 1 `
            -Activity "MedLearn Android QA gate" `
            -Status $step.Name `
            -PercentComplete $percent
        Write-Host "[$($index + 1)/$($steps.Count)] $($step.Name)"
        $stepStartedAt = Get-Date
        & npm.cmd @($step.Args) 2>&1 | ForEach-Object {
            $writer.WriteLine($_.ToString())
        }
        $exitCode = $LASTEXITCODE
        $stepSeconds = [math]::Round(
            ((Get-Date) - $stepStartedAt).TotalSeconds,
            1
        )
        if ($exitCode -ne 0) {
            $status = "failed"
            $failedStep = $step.Name
            Write-Host "  FAILED ($($stepSeconds)s)"
            break
        }
        Write-Host "  PASS ($($stepSeconds)s)"
    }
}
finally {
    $writer.Dispose()
    Write-Progress -Id 1 -Activity "MedLearn Android QA gate" -Completed
}

$gitCommit = "unknown"
$dirtyFileCount = $null
try {
    $gitCommit = (& git -C $repoRoot rev-parse HEAD).Trim()
    $dirtyLines = @(& git -C $repoRoot status --porcelain 2>$null)
    $dirtyFileCount = $dirtyLines.Count
}
catch {
    # Gate result remains useful when Git metadata is unavailable.
}

$metadata = [ordered]@{
    schemaVersion = 1
    gate = "android-qa"
    status = $status
    failedStep = $failedStep
    verifiedAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    elapsedSeconds = [math]::Round(
        ((Get-Date) - $startedAt).TotalSeconds,
        1
    )
    gitCommit = $gitCommit
    workingTreeDirty = if ($null -eq $dirtyFileCount) {
        $null
    } else {
        $dirtyFileCount -gt 0
    }
    dirtyFileCount = $dirtyFileCount
    logPath = "artifacts/android-qa-gate.log"
}
$metadata | ConvertTo-Json | Set-Content -LiteralPath $metadataPath -Encoding UTF8

if ($status -ne "passed") {
    Write-Host ""
    Write-Host "QA gate failed at: $failedStep"
    Write-Host "Last 80 log lines:"
    Get-Content -LiteralPath $logPath -Tail 80 | ForEach-Object {
        Write-Host $_
    }
    throw "Android QA gate failed"
}

Write-Host ""
Write-Host "Android QA gate passed"
Write-Host "  metadata: $metadataPath"
Write-Host "  log: $logPath"
