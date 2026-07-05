[CmdletBinding()]
param(
    [ValidateSet("qa", "release")]
    [string]$Mode = "qa",
    [switch]$Clean,
    [switch]$RegenerateNative,
    [switch]$ShowGradleOutput
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$androidRoot = Join-Path $repoRoot "android"
$gradleWrapper = Join-Path $androidRoot "gradlew.bat"
$sourceApk = Join-Path $androidRoot "app\build\outputs\apk\release\app-release.apk"
$artifactRoot = Join-Path $repoRoot "artifacts"
New-Item -ItemType Directory -Force -Path $artifactRoot | Out-Null
$logPath = Join-Path $artifactRoot "android-$Mode-build.log"
$prebuildLogPath = Join-Path $artifactRoot "android-prebuild.log"

if ($RegenerateNative -or -not (Test-Path -LiteralPath $gradleWrapper)) {
    $prebuildArgs = @("expo", "prebuild", "--platform", "android", "--no-install")
    if ($RegenerateNative) {
        $prebuildArgs += "--clean"
        Write-Host "Regenerating ignored Android native project from Expo config..."
    }
    else {
        Write-Host "Android native project is absent; generating it from Expo config..."
    }
    & npx.cmd @prebuildArgs 2>&1 | Tee-Object -FilePath $prebuildLogPath
    if ($LASTEXITCODE -ne 0) {
        throw "Expo Android prebuild failed with exit code $LASTEXITCODE. Log: $prebuildLogPath"
    }
}

if (-not (Test-Path -LiteralPath $gradleWrapper)) {
    throw "Expo prebuild completed but Android Gradle wrapper was not found: $gradleWrapper"
}

if (-not $env:NODE_ENV) {
    $env:NODE_ENV = "production"
}
if (-not $env:CI) {
    # Expo export:embed otherwise honors React Native's --reset-cache flag and
    # rebuilds the Metro file map on every local Gradle invocation.
    $env:CI = "1"
}

$tasks = @()
if ($Clean) {
    $tasks += "app:clean"
}
$tasks += "app:assembleRelease"

$gradleArgs = @(
    "--no-daemon",
    "--build-cache",
    "--console=plain",
    "-Pkotlin.compiler.execution.strategy=in-process"
)

if ($Mode -eq "qa") {
    # Device QA is standalone release JS with one physical-device ABI.
    # Minification and resource shrinking are release-distribution concerns,
    # not visual acceptance concerns.
    $gradleArgs += @(
        "-PreactNativeArchitectures=arm64-v8a",
        "-Pandroid.enableMinifyInReleaseBuilds=false",
        "-Pandroid.enableShrinkResourcesInReleaseBuilds=false",
        "-Pandroid.enableBundleCompression=true"
    )
}

$startedAt = Get-Date
$script:currentProgress = 0
$script:currentPhase = ""

function Show-BuildPhase {
    param(
        [int]$Percent,
        [string]$Phase
    )
    if ($Percent -le $script:currentProgress) {
        return
    }
    $script:currentProgress = $Percent
    $script:currentPhase = $Phase
    $elapsedSeconds = [math]::Round(((Get-Date) - $startedAt).TotalSeconds, 1)
    Write-Progress `
        -Id 1 `
        -Activity "MedLearn Android $Mode build" `
        -Status "$Phase (${elapsedSeconds}s)" `
        -PercentComplete $Percent
    Write-Host ("[{0,3}%] {1} ({2}s)" -f $Percent, $Phase, $elapsedSeconds)
}

function Update-BuildPhaseFromGradleLine {
    param([string]$Line)
    switch -Regex ($Line) {
        "Configure project" {
            Show-BuildPhase 12 "Configure Gradle and Expo modules"
            break
        }
        "Task :app:(generateCodegen|generateAutolinking|preBuild)" {
            Show-BuildPhase 24 "Generate native bindings"
            break
        }
        "Task :app:createBundleReleaseJsAndAssets|Starting Metro Bundler" {
            Show-BuildPhase 40 "Bundle JavaScript and assets"
            break
        }
        "Task :app:(configureCMake|buildCMake|externalNativeBuild)" {
            Show-BuildPhase 60 "Compile arm64 native modules"
            break
        }
        "Task :app:(compileReleaseKotlin|compileReleaseJava)" {
            Show-BuildPhase 72 "Compile Kotlin and Java"
            break
        }
        "Task :app:(mergeReleaseResources|processReleaseResources|mergeReleaseAssets)" {
            Show-BuildPhase 84 "Merge Android resources"
            break
        }
        "Task :app:packageRelease" {
            Show-BuildPhase 94 "Package and sign APK"
            break
        }
        "Task :app:assembleRelease" {
            Show-BuildPhase 98 "Finalize APK"
            break
        }
    }
}

Write-Host "Android local build"
Write-Host "  mode: $Mode"
Write-Host "  clean: $($Clean.IsPresent)"
Write-Host "  regenerate native: $($RegenerateNative.IsPresent)"
Write-Host "  NODE_ENV: $env:NODE_ENV"
Write-Host "  CI: $env:CI (preserve Metro cache)"
Write-Host "  Gradle daemon: single-use (released after build)"
if ($Mode -eq "qa") {
    Write-Host "  ABI: arm64-v8a"
} else {
    Write-Host "  ABI: project release defaults"
}
Write-Host "  full log: $logPath"
Write-Host ""
Show-BuildPhase 5 "Validate environment"

$gradleExitCode = $null
$buildException = $null
$logWriter = New-Object System.IO.StreamWriter($logPath, $false)
$logWriter.AutoFlush = $true
Push-Location $androidRoot
try {
    try {
        & $gradleWrapper @tasks @gradleArgs 2>&1 | ForEach-Object {
            $line = $_.ToString()
            $logWriter.WriteLine($line)
            Update-BuildPhaseFromGradleLine $line
            if (
                $ShowGradleOutput -or
                $line -match "^(FAILURE:|BUILD (SUCCESSFUL|FAILED))" -or
                $line -match "(^|: )(error|warning):"
            ) {
                Write-Host $line
            }
        }
        $gradleExitCode = $LASTEXITCODE
    }
    catch {
        $buildException = $_
    }
}
finally {
    $logWriter.Dispose()
    Write-Progress -Id 1 -Activity "MedLearn Android $Mode build" -Completed
    Pop-Location
}

if ($buildException -or $gradleExitCode -ne 0) {
    Write-Host ""
    Write-Host "Gradle failed. Last 80 log lines:"
    Get-Content -LiteralPath $logPath -Tail 80 | ForEach-Object {
        Write-Host $_
    }
    if ($buildException) {
        throw $buildException
    }
    throw "Gradle build failed with exit code $gradleExitCode"
}

if (-not (Test-Path -LiteralPath $sourceApk)) {
    throw "Gradle reported success but APK was not found: $sourceApk"
}

$artifactName = if ($Mode -eq "qa") {
    "medlearn-qa-arm64.apk"
} else {
    "medlearn-release-all-abi.apk"
}
$artifactPath = Join-Path $artifactRoot $artifactName
Copy-Item -LiteralPath $sourceApk -Destination $artifactPath -Force

$artifact = Get-Item -LiteralPath $artifactPath
$sha256 = (Get-FileHash -LiteralPath $artifactPath -Algorithm SHA256).Hash
$elapsed = (Get-Date) - $startedAt
$gitCommit = "unknown"
$dirtyFileCount = $null
try {
    $gitCommit = (& git -C $repoRoot rev-parse HEAD).Trim()
    $dirtyLines = @(& git -C $repoRoot status --porcelain 2>$null)
    $dirtyFileCount = $dirtyLines.Count
}
catch {
    # Build metadata remains useful when Git metadata is unavailable.
}
$metadataPath = Join-Path $artifactRoot "android-$Mode-build.json"
$metadata = [ordered]@{
    schemaVersion = 1
    platform = "android"
    mode = $Mode
    artifact = "artifacts/$artifactName"
    abi = if ($Mode -eq "qa") { "arm64-v8a" } else { "project-defaults" }
    byteSize = $artifact.Length
    sha256 = $sha256
    builtAtUtc = (Get-Date).ToUniversalTime().ToString("o")
    elapsedSeconds = [math]::Round($elapsed.TotalSeconds, 1)
    gitCommit = $gitCommit
    workingTreeDirty = if ($null -eq $dirtyFileCount) {
        $null
    } else {
        $dirtyFileCount -gt 0
    }
    dirtyFileCount = $dirtyFileCount
    logPath = "artifacts/android-$Mode-build.log"
}
$metadata | ConvertTo-Json | Set-Content -LiteralPath $metadataPath -Encoding UTF8

Show-BuildPhase 100 "Complete"
Write-Progress -Id 1 -Activity "MedLearn Android $Mode build" -Completed
Write-Host ""
Write-Host "Android build complete"
Write-Host "  APK: $artifactPath"
Write-Host "  size: $($artifact.Length) bytes"
Write-Host "  SHA-256: $sha256"
Write-Host "  metadata: $metadataPath"
Write-Host "  log: $logPath"
Write-Host "  elapsed: $([math]::Round($elapsed.TotalSeconds, 1)) seconds"
