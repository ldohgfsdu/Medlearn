#Requires -Version 5.1
param()

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

Write-Host 'MedLearn deploy preflight' -ForegroundColor Cyan
Write-Host '-------------------------'

$cli = Find-SupabaseCli
if ($cli) {
  Write-Host "PASS supabase cli -> $cli"
  & $cli --version | Write-Host
} else {
  Write-Host 'FAIL supabase cli not found (npm install -g supabase)'
}

python scripts/check-env-configured.py
if ($LASTEXITCODE -ne 0) {
  Write-Host 'WARN some .env values are still placeholders'
}

if ($env:SUPABASE_ACCESS_TOKEN) {
  Write-Host 'PASS SUPABASE_ACCESS_TOKEN present'
} else {
  Write-Host 'BLOCKER SUPABASE_ACCESS_TOKEN missing'
  Write-Host '  Create one at https://supabase.com/dashboard/account/tokens'
  Write-Host '  Then add to .env: SUPABASE_ACCESS_TOKEN=sbp_...'
}

if ($env:DATABASE_URL -or ((Get-Content .env -ErrorAction SilentlyContinue) -match '^DATABASE_URL=')) {
  Write-Host 'PASS DATABASE_URL configured (SQL fallback available)'
} else {
  Write-Host 'INFO DATABASE_URL not configured (CLI path preferred)'
}

npm run audit:remote
if ($LASTEXITCODE -ne 0) {
  Write-Host 'INFO remote project is not fully provisioned yet'
}

Write-Host ''
Write-Host 'If token is configured: npm run deploy:remote'
Write-Host 'If only DB URL is configured: npm run build:remote-bootstrap && npm run apply:remote-sql'
Write-Host 'Manual fallback: paste scripts/remote-bootstrap.sql into Supabase SQL Editor'