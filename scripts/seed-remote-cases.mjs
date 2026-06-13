import { createClient } from '@supabase/supabase-js'
import { ALPHA_CASE_LIBRARY } from '../shared/alpha-case-library.ts'

const url = process.env.SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY
const DEMO_REVIEWER_EMAIL = 'alpha-demo-reviewer@medlearn.local'
const DEMO_REVIEWER_ID = 'aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa'

async function ensureDemoReviewer(supabase) {
  const { data: existing, error: getError } = await supabase.auth.admin.getUserById(DEMO_REVIEWER_ID)
  if (!getError && existing?.user) return existing.user.id

  const { data, error } = await supabase.auth.admin.createUser({
    id: DEMO_REVIEWER_ID,
    email: DEMO_REVIEWER_EMAIL,
    password: 'MedlearnDemoReviewer2026!',
    email_confirm: true,
    user_metadata: { role: 'medical_reviewer_demo' },
  })
  if (error) throw error
  return data.user.id
}

function toRow(record, reviewerId) {
  return {
    id: record.id,
    case_code: record.case_code,
    title: record.title,
    chief_complaint: record.chief_complaint,
    specialty: record.specialty ?? 'general',
    difficulty: record.difficulty,
    estimated_minutes: 15,
    demographics: record.demographics,
    patient_world: record.patient_world,
    ground_truth: record.ground_truth,
    scoring_rubric: record.scoring_rubric,
    is_active: true,
    review_status: 'approved',
    reviewed_by: reviewerId,
    reviewed_at: record.reviewed_at,
  }
}

async function main() {
  if (!url || !serviceRoleKey) {
    console.error('SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY are required')
    process.exitCode = 2
    return
  }

  const supabase = createClient(url, serviceRoleKey, { auth: { persistSession: false } })
  const reviewerId = await ensureDemoReviewer(supabase)
  console.log(`demo_reviewer_id=${reviewerId}`)

  const rows = ALPHA_CASE_LIBRARY.map((record) => toRow(record, reviewerId))
  const { error } = await supabase.from('case_templates').upsert(rows, { onConflict: 'id' })
  if (error) throw error

  const { count, error: countError } = await supabase
    .from('case_templates')
    .select('*', { head: true, count: 'exact' })
    .eq('review_status', 'approved')
    .eq('is_active', true)

  if (countError) throw countError
  console.log(`seeded approved cases=${count}`)
}

function formatError(error) {
  if (!error || typeof error !== 'object') return String(error)
  if (error instanceof Error) return error.message
  return JSON.stringify(error, null, 2)
}

main().catch((error) => {
  console.error(formatError(error))
  process.exitCode = 1
})