/**
 * 向量生成服务
 * 将用户的复述文字转化为数字向量，用于 Supabase RAG 检索
 */

import { loadAISettings } from '@/lib/ai-settings'
import { supabase } from '@/lib/supabase'

const MAX_TEXT_LENGTH = 8000
const MAX_CACHE_ENTRIES = 200
const EXPECTED_DIMENSION = 1024
const OLLAMA_TIMEOUT_MS = 30_000

/** Simple LRU cache with max entry limit */
const embeddingCache = new Map<string, number[]>()

function cacheGet(key: string): number[] | undefined {
  const val = embeddingCache.get(key)
  if (val !== undefined) {
    // Move to end (most recently used)
    embeddingCache.delete(key)
    embeddingCache.set(key, val)
  }
  return val
}

function cacheSet(key: string, value: number[]): void {
  if (embeddingCache.has(key)) {
    embeddingCache.delete(key)
  }
  embeddingCache.set(key, value)
  // Evict oldest entries when over limit
  while (embeddingCache.size > MAX_CACHE_ENTRIES) {
    const oldest = embeddingCache.keys().next().value
    if (oldest !== undefined) embeddingCache.delete(oldest)
  }
}

function simpleHash(str: string): string {
  let hash = 0
  for (let i = 0; i < str.length; i++) {
    hash = (hash * 31 + str.charCodeAt(i)) | 0
  }
  return String(hash)
}

/**
 * 通过 Edge Function 代理获取 Embedding
 */
async function getEmbeddingViaProxy(text: string): Promise<number[]> {
  const { data, error } = await supabase.functions.invoke('embedding-proxy', {
    body: { text },
  })

  if (error) {
    throw new Error(`Edge Function 调用失败: ${error.message}`)
  }

  return data?.data?.[0]?.embedding || []
}

async function getEmbeddingViaOllama(
  text: string,
  ollamaUrl: string,
  ollamaModel: string,
): Promise<number[]> {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), OLLAMA_TIMEOUT_MS)

  try {
    const response = await fetch(`${ollamaUrl}/api/embed`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        model: ollamaModel,
        input: text,
      }),
      signal: controller.signal,
    })

    if (!response.ok) {
      throw new Error(`Ollama embedding failed: HTTP ${response.status}`)
    }

    const data = await response.json()
    return data?.embeddings?.[0] || []
  } finally {
    clearTimeout(timeout)
  }
}

export async function getEmbedding(text: string): Promise<number[]> {
  const trimmed = text.trim()
  if (!trimmed) {
    throw new Error('文本不能为空')
  }

  const truncated = trimmed.length > MAX_TEXT_LENGTH ? trimmed.slice(0, MAX_TEXT_LENGTH) : trimmed
  const cacheKey = simpleHash(truncated)
  const cached = cacheGet(cacheKey)
  if (cached) return cached

  const settings = await loadAISettings()
  const embedding =
    settings.embeddingProvider === 'ollama'
      ? await getEmbeddingViaOllama(truncated, settings.ollamaUrl, settings.ollamaEmbedModel)
      : await getEmbeddingViaProxy(truncated)

  if (embedding.length !== EXPECTED_DIMENSION) {
    throw new Error(
      `Embedding dimension mismatch: expected ${EXPECTED_DIMENSION}, got ${embedding.length}`,
    )
  }

  cacheSet(cacheKey, embedding)
  return embedding
}
