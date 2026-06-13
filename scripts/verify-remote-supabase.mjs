import { createClient } from '@supabase/supabase-js'

const url = process.env.SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY
const anonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY

const REQUIRED_TABLES = [
  'knowledge_nodes',
  'case_templates',
  'case_sessions',
  'case_events',
  'ai_proxy_usage',
]

const REQUIRED_FUNCTIONS = [
  'ai-proxy',
  'embedding-proxy',
  'case-submit',
  'case-patient',
  'case-abandon',
]

const REQUIRED_RPC = [
  'record_case_llm_usage',
  'check_ai_proxy_quota',
  'record_ai_proxy_usage',
]

function fail(message) {
  console.error(`FAIL ${message}`)
  process.exitCode = 1
}

function pass(message) {
  console.log(`PASS ${message}`)
}

function warn(message) {
  console.warn(`WARN ${message}`)
}

async function checkTables(supabase) {
  let ok = true
  for (const table of REQUIRED_TABLES) {
    const { error } = await supabase.from(table).select('id').limit(1)
    if (error) {
      fail(`${table}: ${error.message}`)
      ok = false
      continue
    }
    pass(`table ${table} is reachable`)
  }
  return ok
}

async function checkApprovedCases(supabase) {
  const { data, error } = await supabase
    .from('case_templates')
    .select('id,case_code,review_status,is_active', { count: 'exact' })
    .eq('review_status', 'approved')
    .eq('is_active', true)

  if (error) {
    fail(`case_templates query failed: ${error.message}`)
    return false
  }

  const count = data?.length ?? 0
  if (count < 15) {
    fail(`approved active cases: ${count} (need >= 15)`)
    return false
  }

  pass(`approved active cases: ${count}`)
  return true
}

async function checkRpcFunctions(supabase) {
  const { error: quotaError } = await supabase.rpc('check_ai_proxy_quota', {
    p_user_id: '00000000-0000-0000-0000-000000000000',
    p_window_minutes: 60,
    p_max_requests: 60,
    p_max_tokens: 100000,
  })
  if (quotaError) {
    fail(`check_ai_proxy_quota: ${quotaError.message}`)
    return false
  }
  pass('rpc check_ai_proxy_quota is callable')

  for (const rpc of REQUIRED_RPC.filter((name) => name !== 'check_ai_proxy_quota')) {
    const { error } = await supabase.rpc(rpc, {
      p_user_id: '00000000-0000-0000-0000-000000000000',
      p_session_id: '00000000-0000-0000-0000-000000000000',
      p_prompt_tokens: 0,
      p_completion_tokens: 0,
      p_total_tokens: 0,
      p_estimated_cost: 0,
    })
    if (!error) {
      pass(`rpc ${rpc} is callable`)
      continue
    }
    if (error.message.includes('service role required') || error.message.includes('not found')) {
      pass(`rpc ${rpc} exists (${error.message})`)
      continue
    }
    fail(`rpc ${rpc}: ${error.message}`)
    return false
  }

  return true
}

async function checkEdgeFunctions(baseUrl, anon) {
  if (!anon) {
    warn('EXPO_PUBLIC_SUPABASE_ANON_KEY missing; skipping edge function probe')
    return true
  }

  let ok = true
  for (const name of REQUIRED_FUNCTIONS) {
    const endpoint = `${baseUrl.replace(/\/$/, '')}/functions/v1/${name}`
    try {
      const response = await fetch(endpoint, {
        method: 'POST',
        headers: {
          apikey: anon,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({}),
      })
      if (response.status === 404) {
        fail(`edge function ${name} returned 404 (not deployed?)`)
        ok = false
        continue
      }
      pass(`edge function ${name} responded with HTTP ${response.status}`)
    } catch (error) {
      fail(`edge function ${name}: ${error instanceof Error ? error.message : String(error)}`)
      ok = false
    }
  }
  return ok
}

async function main() {
  console.log('MedLearn remote Supabase verification')
  console.log('-------------------------------------')

  if (!url || !serviceRoleKey) {
    fail('SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required in .env')
    return
  }

  const supabase = createClient(url, serviceRoleKey, {
    auth: { persistSession: false },
  })

  let healthy = true
  healthy = (await checkTables(supabase)) && healthy
  healthy = (await checkApprovedCases(supabase)) && healthy
  healthy = (await checkRpcFunctions(supabase)) && healthy
  healthy = (await checkEdgeFunctions(url, anonKey)) && healthy

  console.log('-------------------------------------')
  if (healthy && process.exitCode !== 1) {
    console.log('Remote verification passed.')
  } else {
    console.log('Remote verification failed.')
    process.exitCode = 1
  }
}

main().catch((error) => {
  fail(error instanceof Error ? error.message : String(error))
})