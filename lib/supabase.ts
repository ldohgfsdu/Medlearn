import 'react-native-url-polyfill/auto'
import { createClient } from '@supabase/supabase-js'
import AsyncStorage from '@react-native-async-storage/async-storage'
import { AppState, Platform } from 'react-native'

const supabaseUrl = process.env.EXPO_PUBLIC_SUPABASE_URL || ''
const supabaseAnonKey = process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY || ''

if (!supabaseUrl || !supabaseAnonKey) {
  throw new Error('Supabase environment variables are not configured')
}

export const supabase = createClient(supabaseUrl, supabaseAnonKey, {
  auth: {
    storage: Platform.OS === 'web' ? (typeof window !== 'undefined' ? window.localStorage : undefined) : AsyncStorage,
    autoRefreshToken: true,
    persistSession: true,
    detectSessionInUrl: Platform.OS === 'web',
  },
})

if (Platform.OS !== 'web') {
  AppState.addEventListener('change', (state) => {
    if (state === 'active') {
      supabase.auth.startAutoRefresh()
    } else {
      supabase.auth.stopAutoRefresh()
    }
  })
}

/**
 * 混合搜索：同时检索知识点标题和教材原文
 */
export async function hybridSearch(query: string, embedding: number[]) {
  // 转义 PostgREST 过滤器中的特殊字符
  const escaped = query.replace(/[,().]/g, '')
  const [nodesResult, chunksResult] = await Promise.all([
    supabase
      .from('knowledge_nodes')
      .select('id, title, type, subject, chapter')
      .or(`title.ilike.%${escaped}%,content.ilike.%${escaped}%`)
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
