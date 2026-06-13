/**
 * 向量生成服务
 * 将用户的复述文字转化为数字向量，用于 Supabase RAG 检索
 */

import { supabase } from '@/lib/supabase'

const MAX_TEXT_LENGTH = 8000
const embeddingCache = new Map<string, number[]>()
const EMBEDDING_PROVIDER = process.env.EXPO_PUBLIC_EMBEDDING_PROVIDER || 'ollama'
const OLLAMA_URL = (process.env.EXPO_PUBLIC_OLLAMA_URL || 'http://127.0.0.1:11434').replace(/\/$/, '')
const OLLAMA_EMBED_MODEL = process.env.EXPO_PUBLIC_OLLAMA_EMBED_MODEL || 'bge-m3'
const EXPECTED_DIMENSION = 1024

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

async function getEmbeddingViaOllama(text: string): Promise<number[]> {
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
  return data?.embeddings?.[0] || []
}

export async function getEmbedding(text: string): Promise<number[]> {
  const trimmed = text.trim()
  if (!trimmed) {
    throw new Error('文本不能为空')
  }

  const truncated = trimmed.length > MAX_TEXT_LENGTH ? trimmed.slice(0, MAX_TEXT_LENGTH) : trimmed
  const cacheKey = simpleHash(truncated)
  const cached = embeddingCache.get(cacheKey)
  if (cached) return cached

  const embedding =
    EMBEDDING_PROVIDER === 'ollama'
      ? await getEmbeddingViaOllama(truncated)
      : await getEmbeddingViaProxy(truncated)

  if (embedding.length !== EXPECTED_DIMENSION) {
    throw new Error(
      `Embedding dimension mismatch: expected ${EXPECTED_DIMENSION}, got ${embedding.length}`,
    )
  }

  embeddingCache.set(cacheKey, embedding)
  return embedding
}
