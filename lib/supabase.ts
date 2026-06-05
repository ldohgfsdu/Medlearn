import 'react-native-url-polyfill/auto'
import { createClient } from '@supabase/supabase-js'

const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL || ''
const supabaseAnonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY || ''

export const supabase = createClient(supabaseUrl, supabaseAnonKey)

/**
 * 混合搜索：同时检索知识点标题和教材原文
 */
export async function hybridSearch(query: string, embedding: number[]) {
  const [nodesResult, chunksResult] = await Promise.all([
    supabase
      .from('knowledge_nodes')
      .select('id, title, type, subject, chapter')
      .or(`title.ilike.%${query}%,content.ilike.%${query}%`)
      .limit(5),

    supabase.rpc('match_documents', {
      query_embedding: embedding,
      match_count: 5,
    })
  ])

  return {
    nodes: nodesResult.data || [],
    chunks: chunksResult.data || []
  }
}

/**
 * 语义搜索文档片段（RAG 核心）
 */
export async function matchDocuments(embedding: number[], limit = 3) {
  const { data, error } = await supabase.rpc('match_documents', {
    query_embedding: embedding,
    match_count: limit,
  })

  if (error) {
    console.error('Match documents error:', error)
    return []
  }
  return data
}
