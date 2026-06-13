import { createClient } from '@supabase/supabase-js'

const url = process.env.SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY
const anonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY

const TABLE_CHECKS = [
  { name: 'knowledge_nodes', columns: 'id' },
  { name: 'case_templates', columns: 'id,review_status,is_active' },
  { name: 'case_sessions', columns: 'id,status' },
  { name: 'case_events', columns: 'id,event_name' },
  { name: 'ai_proxy_usage', columns: 'id,user_id' },
]

const RPC_CHECKS = ['record_case_llm_usage', 'check_ai_proxy_quota', 'record_ai_proxy_usage']

const EDGE_FUNCTIONS = [
  'ai-proxy',
  'embedding-proxy',
  'case-submit',
  'case-patient',
  'case-abandon',
]

function projectRefFromUrl(value) {
  try {
    return new URL(value).hostname.split('.')[0]
  } catch {
    return 'unknown'
  }
}

async function probeTable(supabase, table, columns) {
  const { data, error } = await supabase.from(table).select(columns).limit(1)
  if (error) return { ok: false, detail: error.message }
  return { ok: true, detail: `sample_rows=${data?.length ?? 0}` }
}

async function main() {
  console.log('MedLearn remote schema audit')
  console.log('----------------------------')

  if (!url || !serviceRoleKey) {
    console.error('BLOCKER missing SUPABASE_URL or SUPABASE_SERVICE_ROLE_KEY')
    process.exitCode = 2
    return
  }

  console.log(`project_ref=${projectRefFromUrl(url)}`)
  console.log(`cli_linked=${process.env.SUPABASE_ACCESS_TOKEN ? 'token_present' : 'token_missing'}`)
  console.log(`database_url=${process.env.DATABASE_URL ? 'present' : 'missing'}`)
  console.log('')

  const supabase = createClient(url, serviceRoleKey, { auth: { persistSession: false } })
  let blockers = 0

  console.log('Tables')
  for (const table of TABLE_CHECKS) {
    const result = await probeTable(supabase, table.name, table.columns)
    const status = result.ok ? 'OK' : 'MISSING'
    console.log(`  ${status} ${table.name} ${result.ok ? result.detail : `- ${result.detail}`}`)
    if (!result.ok) blockers += 1
  }

  console.log('')
  console.log('RPC')
  const rpcPayloads = {
    record_case_llm_usage: {
      p_session_id: '00000000-0000-0000-0000-000000000000',
      p_prompt_tokens: 0,
      p_completion_tokens: 0,
      p_total_tokens: 0,
      p_estimated_cost: 0,
    },
    check_ai_proxy_quota: {
      p_user_id: '00000000-0000-0000-0000-000000000000',
      p_window_minutes: 60,
      p_max_requests: 60,
      p_max_tokens: 100000,
    },
    record_ai_proxy_usage: {
      p_user_id: '00000000-0000-0000-0000-000000000000',
      p_prompt_tokens: 0,
      p_completion_tokens: 0,
      p_total_tokens: 0,
      p_estimated_cost: 0,
    },
  }

  for (const rpc of RPC_CHECKS) {
    const { error } = await supabase.rpc(rpc, rpcPayloads[rpc])
    const missing = Boolean(error?.message?.includes('Could not find the function'))
    if (missing) {
      console.log(`  MISSING ${rpc} - ${error.message}`)
      blockers += 1
      continue
    }
    if (error && /service role required|case session not found/i.test(error.message)) {
      console.log(`  OK ${rpc} - ${error.message}`)
      continue
    }
    if (error) {
      console.log(`  WARN ${rpc} - ${error.message}`)
      continue
    }
    console.log(`  OK ${rpc}`)
  }

  if (anonKey) {
    console.log('')
    console.log('Edge Functions')
    const base = url.replace(/\/$/, '')
    for (const name of EDGE_FUNCTIONS) {
      try {
        const response = await fetch(`${base}/functions/v1/${name}`, {
          method: 'POST',
          headers: { apikey: anonKey, 'Content-Type': 'application/json' },
          body: '{}',
        })
        const status = response.status === 404 ? 'MISSING' : 'OK'
        console.log(`  ${status} ${name} http=${response.status}`)
        if (response.status === 404) blockers += 1
      } catch (error) {
        console.log(`  FAIL ${name} - ${error instanceof Error ? error.message : String(error)}`)
        blockers += 1
      }
    }
  }

  console.log('')
  console.log('Recommended next step')
  if (!process.env.SUPABASE_ACCESS_TOKEN && !process.env.DATABASE_URL) {
    console.log('  1. Add SUPABASE_ACCESS_TOKEN to .env (Dashboard -> Account -> Access Tokens)')
    console.log('  2. Run: npm run deploy:remote')
    console.log('  OR paste scripts/remote-bootstrap.sql in Supabase SQL Editor')
  } else if (process.env.DATABASE_URL) {
    console.log('  Run: npm run apply:remote-sql')
  } else {
    console.log('  Run: npm run deploy:remote')
  }

  console.log('')
  console.log(`blockers=${blockers}`)
  if (blockers > 0) process.exitCode = 1
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})