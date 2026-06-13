import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const AI_API_KEY = Deno.env.get('AI_API_KEY')
const AI_BASE_URL = Deno.env.get('AI_BASE_URL') || 'https://api.deepseek.com/v1'
const AI_MODEL = Deno.env.get('AI_MODEL') || 'deepseek-v4-pro'
const AI_INPUT_COST_PER_MILLION = Number(Deno.env.get('AI_INPUT_COST_PER_MILLION') || 0)
const AI_OUTPUT_COST_PER_MILLION = Number(Deno.env.get('AI_OUTPUT_COST_PER_MILLION') || 0)
const AI_PROXY_WINDOW_MINUTES = Number(Deno.env.get('AI_PROXY_WINDOW_MINUTES') || 60)
const AI_PROXY_MAX_REQUESTS = Number(Deno.env.get('AI_PROXY_MAX_REQUESTS') || 60)
const AI_PROXY_MAX_TOKENS = Number(Deno.env.get('AI_PROXY_MAX_TOKENS') || 100_000)
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

function estimateCost(usage: {
  prompt_tokens?: number
  completion_tokens?: number
}): number {
  const input = Math.max(0, Number(usage.prompt_tokens) || 0)
  const output = Math.max(0, Number(usage.completion_tokens) || 0)
  return (
    (input * AI_INPUT_COST_PER_MILLION + output * AI_OUTPUT_COST_PER_MILLION) / 1_000_000
  )
}

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  const authHeader = req.headers.get('Authorization')
  if (!authHeader || !SUPABASE_URL || !SUPABASE_ANON_KEY || !SUPABASE_SERVICE_ROLE_KEY) {
    return jsonResponse({ error: 'Missing authorization' }, 401)
  }

  try {
    const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      global: { headers: { Authorization: authHeader } },
      auth: { persistSession: false },
    })
    const {
      data: { user },
      error: authError,
    } = await supabase.auth.getUser()
    if (authError || !user) {
      return jsonResponse({ error: 'Invalid authorization' }, 401)
    }
    if (!AI_API_KEY) {
      return jsonResponse({ error: 'AI service is not configured' }, 503)
    }

    const admin = createClient(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, {
      auth: { persistSession: false },
    })
    const { data: withinQuota, error: quotaError } = await admin.rpc('check_ai_proxy_quota', {
      p_user_id: user.id,
      p_window_minutes: AI_PROXY_WINDOW_MINUTES,
      p_max_requests: AI_PROXY_MAX_REQUESTS,
      p_max_tokens: AI_PROXY_MAX_TOKENS,
    })
    if (quotaError) {
      return jsonResponse({ error: 'Quota check failed' }, 503)
    }
    if (withinQuota !== true) {
      return jsonResponse({ error: 'AI proxy quota exceeded' }, 429)
    }

    const { messages, temperature = 0.7, max_tokens = 2000, response_format } = await req.json()
    if (!Array.isArray(messages) || messages.length === 0 || messages.length > 50) {
      return jsonResponse({ error: 'Invalid messages' }, 400)
    }
    const totalCharacters = messages.reduce(
      (sum: number, message: { content?: unknown }) =>
        sum + (typeof message?.content === 'string' ? message.content.length : 0),
      0,
    )
    if (totalCharacters > 50_000) {
      return jsonResponse({ error: 'Request is too large' }, 413)
    }
    const safeMaxTokens = Math.min(Math.max(Number(max_tokens) || 2000, 1), 4096)
    const safeTemperature = Math.min(Math.max(Number(temperature) || 0.7, 0), 2)

    const response = await fetch(`${AI_BASE_URL}/chat/completions`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${AI_API_KEY}`,
      },
      body: JSON.stringify({
        model: AI_MODEL,
        messages,
        temperature: safeTemperature,
        max_tokens: safeMaxTokens,
        ...(response_format?.type === 'json_object' ? { response_format } : {}),
      }),
    })

    if (!response.ok) {
      return jsonResponse({ error: `AI API error: ${response.status}` }, response.status)
    }

    const data = await response.json()
    const usage = data?.usage ?? {}
    const promptTokens = Math.max(0, Number(usage.prompt_tokens) || 0)
    const completionTokens = Math.max(0, Number(usage.completion_tokens) || 0)
    const totalTokens =
      Math.max(0, Number(usage.total_tokens) || 0) || promptTokens + completionTokens
    const estimatedCost = estimateCost(usage)

    const { error: recordError } = await admin.rpc('record_ai_proxy_usage', {
      p_user_id: user.id,
      p_prompt_tokens: promptTokens,
      p_completion_tokens: completionTokens,
      p_total_tokens: totalTokens,
      p_estimated_cost: estimatedCost,
    })
    if (recordError) {
      return jsonResponse({ error: 'Failed to record AI usage' }, 500)
    }

    return jsonResponse(data)
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error'
    return jsonResponse({ error: message }, 500)
  }
})