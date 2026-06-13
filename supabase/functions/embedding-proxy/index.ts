import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { createClient } from "https://esm.sh/@supabase/supabase-js@2"

const SILICONFLOW_KEY = Deno.env.get('SILICONFLOW_KEY')
const SUPABASE_URL = Deno.env.get('SUPABASE_URL')
const SUPABASE_ANON_KEY = Deno.env.get('SUPABASE_ANON_KEY')
const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}
const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  })

serve(async (req) => {
  if (req.method === 'OPTIONS') {
    return new Response('ok', { headers: corsHeaders })
  }

  const authHeader = req.headers.get('Authorization')
  if (!authHeader || !SUPABASE_URL || !SUPABASE_ANON_KEY) {
    return jsonResponse({ error: 'Missing authorization' }, 401)
  }

  try {
    const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY, {
      global: { headers: { Authorization: authHeader } },
      auth: { persistSession: false },
    })
    const { data: { user }, error: authError } = await supabase.auth.getUser()
    if (authError || !user) {
      return jsonResponse({ error: 'Invalid authorization' }, 401)
    }
    if (!SILICONFLOW_KEY) {
      return jsonResponse({ error: 'Embedding service is not configured' }, 503)
    }

    const { text } = await req.json()
    
    if (typeof text !== 'string' || !text.trim()) {
      return jsonResponse({ error: 'Text is required' }, 400)
    }

    const response = await fetch('https://api.siliconflow.cn/v1/embeddings', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${SILICONFLOW_KEY}`,
      },
      body: JSON.stringify({
        model: 'BAAI/bge-large-zh-v1.5',
        input: text.substring(0, 8000),
      }),
    })

    if (!response.ok) {
      return jsonResponse({ error: `Embedding API error: ${response.status}` }, response.status)
    }

    const data = await response.json()
    return jsonResponse(data)
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error'
    return jsonResponse({ error: message }, 500)
  }
})
