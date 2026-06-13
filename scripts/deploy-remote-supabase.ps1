#Requires -Version 5.1
<#
.SYNOPSIS
  Deploy MedLearn migrations, seeds, Edge Functions, and secrets to a linked Supabase project.

.DESCRIPTION
  Prerequisites:
    1. Supabase CLI installed: https://supabase.com/docs/guides/cli
    2. Logged in: supabase login
    3. Project linked: supabase link --project-ref <ref>
    4. .env populated with SUPABASE_URL, keys, and AI provider secrets

.EXAMPLE
  .\scripts\deploy-remote-supabase.ps1
  .\scripts\deploy-remote-supabase.ps1 -SkipSecrets -SkipSeeds
#>
param(
  [switch]$SkipSecrets,
  [switch]$SkipSeeds,
  [switch]$SkipFunctions,
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot
Set-Location $Root

function Write-Step([string]$Message) {
  Write-Host ""
  Write-Host "==> $Message" -ForegroundColor Cyan
}

function Assert-Command([string]$Name) {
  if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
    throw "Required command not found: $Name"
  }
}

function Read-DotEnvValue([string]$Key) {
  $envFile = Join-Path $Root '.env'
  if (-not (Test-Path $envFile)) { return $null }
  $line = Get-Content $envFile | Where-Object { $_ -match "^\s*$([regex]::Escape($Key))\s*=" } | Select-Object -First 1
  if (-not $line) { return $null }
  return ($line -split '=', 2)[1].Trim().Trim('"').Trim("'")
}

function Invoke-Step([string]$Command, [string[]]$Args = @()) {
  Write-Host "+ $Command $($Args -join ' ')" -ForegroundColor DarkGray
  if ($DryRun) { return }
  if ($Command -eq 'supabase') { $Command = $SupabaseCli }
  & $Command @Args
  if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) {
    throw "Command failed ($LASTEXITCODE): $Command $($Args -join ' ')"
  }
}

function Find-SupabaseCli {
  if (Get-Command supabase -ErrorAction SilentlyContinue) { return 'supabase' }
  $npmGlobal = & npm prefix -g 2>$null
  $candidate = Join-Path $npmGlobal 'supabase.cmd'
  if (Test-Path $candidate) { return $candidate }
  return $null
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
  throw 'SUPABASE_ACCESS_TOKEN is required. Create one at https://supabase.com/dashboard/account/tokens and add it to .env'
}

Assert-Command 'npm'

if (-not (Test-Path (Join-Path $Root 'supabase\config.toml'))) {
  throw 'supabase/config.toml not found. Run this script from the MedLearn repo root.'
}

Write-Step 'Checking Supabase project link'
Invoke-Step 'supabase' @('projects', 'list')

$projectUrl = Read-DotEnvValue 'EXPO_PUBLIC_SUPABASE_URL'
if (-not $projectUrl) { $projectUrl = Read-DotEnvValue 'SUPABASE_URL' }
$projectRef = $null
if ($projectUrl -match '^https?://([^.]+)\.supabase\.co') {
  $projectRef = $Matches[1]
}
if ($projectRef) {
  Write-Step "Linking project ref $projectRef"
  Invoke-Step 'supabase' @('link', '--project-ref', $projectRef, '--yes')
}

Write-Step 'Pushing database migrations (001-019)'
Invoke-Step 'supabase' @('db', 'push')

if (-not $SkipSeeds) {
  Write-Step 'Applying alpha case seed library'
  $seedFile = Join-Path $Root 'supabase\seeds\002_alpha_case_library.sql'
  if (-not (Test-Path $seedFile)) {
    Write-Host 'Seed file missing; generating...' -ForegroundColor Yellow
    Invoke-Step 'npm' @('run', 'generate:case-seeds')
  }
  Invoke-Step 'supabase' @('db', 'execute', '--linked', '-f', $seedFile)
}

if (-not $SkipFunctions) {
  Write-Step 'Deploying Edge Functions'
  foreach ($name in @('ai-proxy', 'embedding-proxy', 'case-submit', 'case-patient', 'case-abandon')) {
    Invoke-Step 'supabase' @('functions', 'deploy', $name)
  }
}

if (-not $SkipSecrets) {
  Write-Step 'Setting Edge Function secrets from .env'
  $secretMap = @{
    'AI_API_KEY' = Read-DotEnvValue 'AI_API_KEY'
    'AI_BASE_URL' = Read-DotEnvValue 'AI_BASE_URL'
    'AI_MODEL' = Read-DotEnvValue 'AI_MODEL'
    'SILICONFLOW_KEY' = Read-DotEnvValue 'SILICONFLOW_KEY'
    'AI_INPUT_COST_PER_MILLION' = Read-DotEnvValue 'AI_INPUT_COST_PER_MILLION'
    'AI_OUTPUT_COST_PER_MILLION' = Read-DotEnvValue 'AI_OUTPUT_COST_PER_MILLION'
    'CASE_MAX_TOKENS' = Read-DotEnvValue 'CASE_MAX_TOKENS'
    'CASE_MAX_COST_USD' = Read-DotEnvValue 'CASE_MAX_COST_USD'
    'AI_PROXY_WINDOW_MINUTES' = Read-DotEnvValue 'AI_PROXY_WINDOW_MINUTES'
    'AI_PROXY_MAX_REQUESTS' = Read-DotEnvValue 'AI_PROXY_MAX_REQUESTS'
    'AI_PROXY_MAX_TOKENS' = Read-DotEnvValue 'AI_PROXY_MAX_TOKENS'
  }

  $pairs = @()
  foreach ($entry in $secretMap.GetEnumerator()) {
    if ([string]::IsNullOrWhiteSpace($entry.Value)) { continue }
    $pairs += "$($entry.Key)=$($entry.Value)"
  }

  if ($pairs.Count -eq 0) {
    Write-Host 'No secrets found in .env; skipping supabase secrets set.' -ForegroundColor Yellow
  } else {
    Invoke-Step 'supabase' @('secrets', 'set', '--env-file', '.env')
  }
}

Write-Step 'Running remote verification'
Invoke-Step 'npm' @('run', 'verify:remote')

Write-Step 'Validating case library release gate'
Invoke-Step 'npm' @('run', 'validate:cases')

Write-Host ""
Write-Host 'Remote deployment workflow completed.' -ForegroundColor Green
Write-Host 'Next: run the device E2E checklist in docs/E2E_ACCEPTANCE_CHECKLIST.md' -ForegroundColor Green