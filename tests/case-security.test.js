const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const root = path.resolve(__dirname, '..')

function read(relativePath) {
  return fs.readFileSync(path.join(root, relativePath), 'utf8')
}

test('client case queries never request answer keys or scoring rules', () => {
  const clientFiles = [
    'services/case-engine.ts',
    'hooks/useCaseSession.ts',
    'app/case/[sessionId]/diagnose.tsx',
    'app/case/[sessionId]/treat.tsx',
  ]

  for (const file of clientFiles) {
    const source = read(file)
    assert.doesNotMatch(source, /ground_truth|scoring_rubric|case_templates\(\*\)/)
  }
})

test('database migration revokes broad template reads and protects final scores', () => {
  const migration = read('supabase/migrations/016_secure_case_scoring.sql')
  assert.match(migration, /REVOKE SELECT ON TABLE public\.case_templates FROM authenticated/)
  assert.match(migration, /NEW\.score IS DISTINCT FROM OLD\.score/)
  assert.match(migration, /NEW\.case_id IS DISTINCT FROM OLD\.case_id/)
})

test('usage count RPC can mark usage_counted_at once without weakening score guards', () => {
  const migration = read('supabase/migrations/021_fix_increment_usage_count_guard.sql')
  assert.match(migration, /OLD\.usage_counted_at IS NULL/)
  assert.match(migration, /NEW\.completed_at IS DISTINCT FROM OLD\.completed_at/)
  assert.match(read('supabase/migrations/014_harden_case_usage_count.sql'), /usage_counted_at = NOW\(\)/)
})

test('approved cases require a recorded medical reviewer', () => {
  const migration = read('supabase/migrations/017_case_review_workflow.sql')
  assert.match(migration, /reviewed_by IS NOT NULL/)
  assert.match(migration, /reviewed_at IS NOT NULL/)
  assert.match(migration, /review_status <> 'approved'/)
})

test('case patient AI has injection, leakage, usage, and budget guardrails', () => {
  const patientFunction = read('supabase/functions/case-patient/index.ts')
  assert.match(patientFunction, /detectPromptInjection/)
  assert.match(patientFunction, /findDiagnosisLeak/)
  assert.match(patientFunction, /record_case_llm_usage/)
  assert.match(patientFunction, /CASE_MAX_TOKENS/)
  assert.match(patientFunction, /CASE_MAX_COST_USD/)
  assert.doesNotMatch(read('services/case-engine.ts'), /invokeAI|ai-proxy/)
})

test('service-role case functions reject unapproved templates', () => {
  const guard = read('supabase/functions/_shared/case-template-guard.ts')
  assert.match(guard, /Case is not approved for training/)
  for (const file of [
    'supabase/functions/case-patient/index.ts',
    'supabase/functions/case-submit/index.ts',
    'supabase/functions/case-abandon/index.ts',
  ]) {
    const source = read(file)
    assert.match(source, /rejectUnapprovedCaseTemplate/)
    assert.match(source, /is_active,review_status/)
  }
})

test('ai proxy enforces per-user quota and records usage', () => {
  const source = read('supabase/functions/ai-proxy/index.ts')
  assert.match(source, /check_ai_proxy_quota/)
  assert.match(source, /record_ai_proxy_usage/)
  assert.match(source, /AI proxy quota exceeded/)
  assert.match(read('supabase/migrations/019_ai_proxy_cost_controls.sql'), /ai_proxy_usage/)
})

test('knowledge access layer uses knowledge_nodes schema', () => {
  const source = read('app/lib/knowledge.ts')
  assert.match(source, /knowledge_nodes/)
  assert.doesNotMatch(source, /knowledge_points/)
})

test('intro phase allows greeting and open history questions before exam workflow', () => {
  const engine = read('services/case-engine.ts')
  assert.match(engine, /ask_history: \[CasePhase\.INTRO, CasePhase\.HISTORY, CasePhase\.EXAM\]/)
  assert.match(engine, /unknown: \[CasePhase\.INTRO, CasePhase\.HISTORY, CasePhase\.EXAM, CasePhase\.TESTS\]/)
  assert.match(engine, /ensureHistoryPhase/)
  assert.match(engine, /historyResponse === null/)

  const parser = read('services/intent-parser.ts')
  assert.match(parser, /name: 'hpi_open'/)
  assert.match(parser, /有\.\{0,10\}呼吸困难/)
})

test('case lifecycle actions emit their required analytics events', () => {
  assert.match(read('services/case-engine.ts'), /hint_requested/)
  assert.match(read('supabase/functions/case-abandon/index.ts'), /case_abandoned/)
  assert.match(
    read('app/case/[sessionId]/score.tsx'),
    /scoring_dispute_submitted/,
  )
})
