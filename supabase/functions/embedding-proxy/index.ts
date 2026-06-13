import { serve } from 'https://deno.land/std@0.168.0/http/server.ts'
import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

const EMBEDDING_PROVIDER = (Deno.env.get('EMBEDDING_PROVIDER') || 'ollama').toLowerCase()
const OLLAMA_URL = (Deno.env.get('OLLAMA_URL') || 'http://127.0.0.1:11434').replace(/\/$/, '')
const OLLAMA_EMBED_MODEL = Deno.env.get('OLLAMA_EMBED_MODEL') || 'bge-m3'
const SILICONFLOW_KEY = Deno.env.get('SILICONFLOW_KEY')
const SUPABASE_URL = Deno.env.get('SUPABASE_URL')
const SUPABASE_ANON_KEY = Deno.env.get('SUPABASE_ANON_KEY')
const EXPECTED_DIMENSION = 1024

const corsHeaders = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, x-client-info, apikey, content-type',
}

const jsonResponse = (body: unknown, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, 'Content-Type': 'application/json' },
  })

async function embedViaOllama(text: string) {
  const response = await fetch(`${OLLAMA_URL}/api/embed`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      model: OLLAMA_EMBED_MODEL,
      input: text,
    }),
  })

  if (!response.ok) {
    throw new Error(`Ollama embedding failed: HTTP ${response.status}`)
  }

  const data = await response.json()
  const embedding = data?.embeddings?.[0] || []
  if (embedding.length !== EXPECTED_DIMENSION) {
    throw new Error(
      `Embedding dimension mismatch: expected ${EXPECTED_DIMENSION}, got ${embedding.length}`,
    )
  }

  return {
    data: [{ embedding, index: 0 }],
    model: OLLAMA_EMBED_MODEL,
    usage: { prompt_tokens: 0, total_tokens: 0 },
  }
}

async function embedViaSiliconFlow(text: string) {
  if (!SILICONFLOW_KEY) {
    throw new Error('SILICONFLOW_KEY is not configured')
  }

  const response = await fetch('https://api.siliconflow.cn/v1/embeddings', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      Authorization: `Bearer ${SILICONFLOW_KEY}`,
    },
    body: JSON.stringify({
      model: 'BAAI/bge-large-zh-v1.5',
      input: text,
    }),
  })

  if (!response.ok) {
    throw new Error(`Embedding API error: HTTP ${response.status}`)
  }

  return await response.json()
}

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
    const {
      data: { user },
      error: authError,
    } = await supabase.auth.getUser()
    if (authError || !user) {
      return jsonResponse({ error: 'Invalid authorization' }, 401)
    }

    const { text } = await req.json()
    if (typeof text !== 'string' || !text.trim()) {
      return jsonResponse({ error: 'Text is required' }, 400)
    }

    const payload =
      EMBEDDING_PROVIDER === 'siliconflow'
        ? await embedViaSiliconFlow(text.substring(0, 8000))
        : await embedViaOllama(text.substring(0, 8000))

    return jsonResponse(payload)
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error'
    return jsonResponse({ error: message }, 500)
  }
})