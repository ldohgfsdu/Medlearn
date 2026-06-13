import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import { rejectUnapprovedCaseTemplate } from '../_shared/case-template-guard.ts'
import {
  scoreCaseSubmission,
  type CaseSubmission,
  type GroundTruth,
  type ScoringRubric,
} from '../_shared/case-scoring.ts'

const APPROVED_TEMPLATE_FIELDS =
  'chief_complaint,difficulty,ground_truth,scoring_rubric,is_active,review_status'

const SUPABASE_URL = Deno.env.get('SUPABASE_URL')
const SUPABASE_ANON_KEY = Deno.env.get('SUPABASE_ANON_KEY')
const SUPABASE_SERVICE_ROLE_KEY = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')
const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  })
}

function normalizeTreatments(value: unknown): string[] | null {
  if (!Array.isArray(value) || value.length === 0 || value.length > 10) return null
  const treatments = value
    .filter((item): item is string => typeof item === 'string')
    .map((item) => item.trim())
    .filter(Boolean)
  return treatments.length > 0 && treatments.every((item) => item.length <= 500)
    ? treatments
    : null
}

function normalizeSubmission(value: unknown, treatments: string[]): CaseSubmission | null {
  if (!value || typeof value !== 'object') return null
  const submitted = value as Partial<CaseSubmission>
  if (
    typeof submitted.primaryDiagnosis !== 'string' ||
    !submitted.primaryDiagnosis.trim() ||
    submitted.primaryDiagnosis.length > 300
  ) {
    return null
  }

  const differentials = Array.isArray(submitted.differentials)
    ? submitted.differentials
        .filter(
          (item): item is { diagnosis: string; reasoning?: string } =>
            Boolean(item) &&
            typeof item === 'object' &&
            typeof (item as { diagnosis?: unknown }).diagnosis === 'string',
        )
        .slice(0, 5)
        .map((item) => ({
          diagnosis: item.diagnosis.trim().slice(0, 300),
          reasoning:
            typeof item.reasoning === 'string'
              ? item.reasoning.trim().slice(0, 1_000)
              : undefined,
        }))
        .filter((item) => item.diagnosis)
    : []
  const evidence = Array.isArray(submitted.evidence)
    ? submitted.evidence
        .filter((item): item is string => typeof item === 'string')
        .slice(0, 8)
        .map((item) => item.trim().slice(0, 500))
        .filter(Boolean)
    : []

  return {
    primaryDiagnosis: submitted.primaryDiagnosis.trim(),
    differentials,
    evidence,
    treatments,
    confidence:
      submitted.confidence === 1 || submitted.confidence === 2 || submitted.confidence === 3
        ? submitted.confidence
        : undefined,
    uncertainty:
      typeof submitted.uncertainty === 'string'
        ? submitted.uncertainty.trim().slice(0, 1_000)
        : undefined,
  }
}

serve(async (request) => {
  if (request.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }
  if (request.method !== 'POST') {
    return jsonResponse({ error: 'Method not allowed' }, 405)
  }

  const authorization = request.headers.get('Authorization')
  if (
    !authorization ||
    !SUPABASE_URL ||
    !SUPABASE_ANON_KEY ||
    !SUPABASE_SERVICE_ROLE_KEY
  ) {
    return jsonResponse({ error: 'Service is not configured' }, 503)
  }

  try {
    const authClient = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      global: { headers: { Authorization: authorization } },
      auth: { persistSession: false },
    })
    const {
      data: { user },
      error: authError,
    } = await authClient.auth.getUser()
    if (authError || !user) return jsonResponse({ error: 'Invalid authorization' }, 401)

    const payload = await request.json()
    const sessionId = typeof payload?.sessionId === 'string' ? payload.sessionId : ''
    const treatments = normalizeTreatments(payload?.treatments)
    if (!sessionId || !treatments) {
      return jsonResponse({ error: 'Invalid submission' }, 400)
    }

    const admin = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
      auth: { persistSession: false },
    })
    const { data: session, error: sessionError } = await admin
      .from('case_sessions')
      .select(
        `id,user_id,case_id,status,current_phase,submitted,score,case_templates(${APPROVED_TEMPLATE_FIELDS})`,
      )
      .eq('id', sessionId)
      .eq('user_id', user.id)
      .single()

    if (sessionError || !session) return jsonResponse({ error: 'Session not found' }, 404)
    if (session.status === 'completed' && session.score) {
      return jsonResponse({ score: session.score })
    }
    if (session.status !== 'in_progress' || session.current_phase !== 'treatment') {
      return jsonResponse({ error: 'Session is not ready for scoring' }, 409)
    }

    const template = Array.isArray(session.case_templates)
      ? session.case_templates[0]
      : session.case_templates
    const approvalError = rejectUnapprovedCaseTemplate(template)
    if (approvalError) {
      return new Response(approvalError.body, {
        status: approvalError.status,
        headers: { ...corsHeaders, 'Content-Type': 'application/json' },
      })
    }
    if (!template?.ground_truth || !template?.scoring_rubric) {
      return jsonResponse({ error: 'Case scoring data is unavailable' }, 500)
    }

    const submission = normalizeSubmission(session.submitted, treatments)
    if (!submission) return jsonResponse({ error: 'Diagnosis submission is incomplete' }, 400)

    const score = scoreCaseSubmission(
      submission,
      template.ground_truth as GroundTruth,
      template.scoring_rubric as ScoringRubric,
    )
    const completedAt = new Date().toISOString()
    const { data: updated, error: updateError } = await admin
      .from('case_sessions')
      .update({
        current_phase: 'feedback',
        status: 'completed',
        completed_at: completedAt,
        score,
        submitted: submission,
      })
      .eq('id', sessionId)
      .eq('user_id', user.id)
      .eq('status', 'in_progress')
      .select('id')
      .maybeSingle()

    if (updateError) throw updateError
    if (!updated) return jsonResponse({ error: 'Session changed while scoring' }, 409)

    const { error: eventError } = await admin.from('case_events').insert({
      event_name: 'case_completed',
      user_id: user.id,
      session_id: sessionId,
      case_id: session.case_id,
      chief_complaint: template.chief_complaint ?? null,
      difficulty: template.difficulty ?? null,
      properties: { totalScore: score.totalScore, grade: score.grade },
    })
    if (eventError) throw eventError

    return jsonResponse({ score })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error'
    return jsonResponse({ error: message }, 500)
  }
})
