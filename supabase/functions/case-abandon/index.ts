import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'
import { rejectUnapprovedCaseTemplate } from '../_shared/case-template-guard.ts'

const APPROVED_TEMPLATE_FIELDS = 'chief_complaint,difficulty,is_active,review_status'

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
    if (!sessionId) return jsonResponse({ error: 'Invalid request' }, 400)

    const admin = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
      auth: { persistSession: false },
    })
    const { data: session, error: sessionError } = await admin
      .from('case_sessions')
      .select(
        `id,user_id,case_id,status,case_templates(${APPROVED_TEMPLATE_FIELDS})`,
      )
      .eq('id', sessionId)
      .eq('user_id', user.id)
      .single()
    if (sessionError || !session) return jsonResponse({ error: 'Session not found' }, 404)

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

    if (session.status !== 'in_progress') {
      return jsonResponse({ abandoned: session.status === 'abandoned' })
    }

    const { data: updated, error: updateError } = await admin
      .from('case_sessions')
      .update({
        status: 'abandoned',
        completed_at: new Date().toISOString(),
      })
      .eq('id', sessionId)
      .eq('user_id', user.id)
      .eq('status', 'in_progress')
      .select('id')
      .maybeSingle()
    if (updateError) throw updateError
    if (!updated) return jsonResponse({ error: 'Session changed' }, 409)

    const { error: eventError } = await admin.from('case_events').insert({
      event_name: 'case_abandoned',
      user_id: user.id,
      session_id: sessionId,
      case_id: session.case_id,
      chief_complaint: template?.chief_complaint ?? null,
      difficulty: template?.difficulty ?? null,
      properties: {},
    })
    if (eventError) throw eventError

    return jsonResponse({ abandoned: true })
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error'
    return jsonResponse({ error: message }, 500)
  }
})
