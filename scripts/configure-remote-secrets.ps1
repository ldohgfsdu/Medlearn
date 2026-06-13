#Requires -Version 5.1
param(
  [switch]$DryRun,
  [switch]$AllowPartial
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Find-SupabaseCli {
  if (Get-Command supabase -ErrorAction SilentlyContinue) { return 'supabase' }
  $npmGlobal = & npm prefix -g 2>$null
  $candidate = Join-Path $npmGlobal 'supabase.cmd'
  if (Test-Path $candidate) { return $candidate }
  return $null
}

function Read-DotEnvValue([string]$Key) {
  $envFile = Join-Path $Root '.env'
  if (-not (Test-Path $envFile)) { return $null }
  $line = Get-Content $envFile -Encoding utf8 | Where-Object { $_ -match "^\s*$([regex]::Escape($Key))\s*=" } | Select-Object -First 1
  if (-not $line) { return $null }
  return ($line -split '=', 2)[1].Trim().Trim('"').Trim("'")
}

function Is-Placeholder([string]$Value) {
  if ([string]::IsNullOrWhiteSpace($Value)) { return $true }
  return $Value.StartsWith('your_') -or $Value.EndsWith('_here')
}

$SupabaseCli = Find-SupabaseCli
if (-not $SupabaseCli) {
  throw 'Supabase CLI not found. Install with: npm install -g supabase'
}

if (-not $env:SUPABASE_ACCESS_TOKEN) {
  $tokenFromEnv = Read-DotEnvValue 'SUPABASE_ACCESS_TOKEN'
  if ($tokenFromEnv) { $env:SUPABASE_ACCESS_TOKEN = $tokenFromEnv }
}
if (-not $env:SUPABASE_ACCESS_TOKEN) {
  throw 'SUPABASE_ACCESS_TOKEN is required in .env'
}

$projectUrl = Read-DotEnvValue 'EXPO_PUBLIC_SUPABASE_URL'
if (-not $projectUrl) { $projectUrl = Read-DotEnvValue 'SUPABASE_URL' }
$projectRef = $null
if ($projectUrl -match '^https?://([^.]+)\.supabase\.co') {
  $projectRef = $Matches[1]
}
if (-not $projectRef) {
  throw 'Could not derive project ref from SUPABASE_URL'
}

$secretKeys = @(
  'AI_API_KEY',
  'AI_BASE_URL',
  'AI_MODEL',
  'SILICONFLOW_KEY',
  'AI_INPUT_COST_PER_MILLION',
  'AI_OUTPUT_COST_PER_MILLION',
  'CASE_MAX_TOKENS',
  'CASE_MAX_COST_USD',
  'AI_PROXY_WINDOW_MINUTES',
  'AI_PROXY_MAX_REQUESTS',
  'AI_PROXY_MAX_TOKENS'
)

$functionsEnv = Join-Path $Root '.env.functions'
$lines = @('# Generated for supabase secrets set; do not commit real API keys.')
$missingRequired = @()

foreach ($key in $secretKeys) {
  $value = Read-DotEnvValue $key
  if ($key -eq 'AI_API_KEY' -and (Is-Placeholder $value)) {
    $missingRequired += $key
    continue
  }
  if ([string]::IsNullOrWhiteSpace($value) -or (Is-Placeholder $value)) { continue }
  $lines += "$key=$value"
}

Set-Content -Path $functionsEnv -Value $lines -Encoding utf8

Write-Host 'MedLearn remote secrets configuration' -ForegroundColor Cyan
Write-Host "Project ref: $projectRef"
Write-Host "Secrets file: $functionsEnv"

if ($missingRequired.Count -gt 0) {
  Write-Host ''
  Write-Host 'WARN missing required secrets in .env:' -ForegroundColor Yellow
  foreach ($key in $missingRequired) {
    Write-Host "  - $key"
  }
  if (-not $AllowPartial) {
    Write-Host ''
    Write-Host 'Add AI_API_KEY to .env, then rerun: npm run configure:remote-secrets'
    exit 2
  }
  Write-Host 'Continuing with available defaults (-AllowPartial).'
}

if ($lines.Count -le 1) {
  Write-Host 'No secrets to upload.'
  exit 0
}

Write-Host ''
Write-Host 'Uploading secrets:' -ForegroundColor Cyan
$lines | Where-Object { $_ -notmatch '^#' } | ForEach-Object {
  $name = ($_ -split '=', 2)[0]
  Write-Host "  - $name"
}

if ($DryRun) {
  Write-Host 'Dry run only; no secrets uploaded.'
  exit 0
}

& $SupabaseCli secrets set --env-file $functionsEnv --project-ref $projectRef
if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
  throw "supabase secrets set failed ($LASTEXITCODE)"
}

Write-Host ''
Write-Host 'Remote secrets configured.' -ForegroundColor Green
& $SupabaseCli secrets list --project-ref $projectRef