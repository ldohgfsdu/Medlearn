/**
 * 知识点服务
 * 替代 initSeedData 云函数，使用 Supabase
 */

import { supabase } from '../lib/supabase/client'
import type { KnowledgeNode, ExamQuestion, CausalChain, MedicalCase } from '../lib/supabase/types'

export interface KnowledgeQuery {
  subject?: string
  chapter?: string
  type?: string
  difficulty?: number
  keyword?: string
  page?: number
  pageSize?: number
}

export interface PaginatedResult<T> {
  data: T[]
  total: number
  page: number
  pageSize: number
  totalPages: number
}

/**
 * 知识点服务类
 */
export class KnowledgeService {
  /**
   * 获取知识点列表
   */
  static async getNodes(query: KnowledgeQuery = {}): Promise<PaginatedResult<KnowledgeNode>> {
    const {
      subject,
      chapter,
      type,
      difficulty,
      keyword,
      page = 1,
      pageSize = 20,
    } = query

    try {
      let queryBuilder = supabase
        .from('knowledge_nodes')
        .select('*', { count: 'exact' })

      // 应用过滤条件
      if (subject) {
        queryBuilder = queryBuilder.eq('subject', subject)
      }
      if (chapter) {
        queryBuilder = queryBuilder.eq('chapter', chapter)
      }
      if (type) {
        queryBuilder = queryBuilder.eq('type', type)
      }
      if (difficulty) {
        queryBuilder = queryBuilder.eq('difficulty', difficulty)
      }
      if (keyword) {
        queryBuilder = queryBuilder.or(
          `title.ilike.%${keyword}%,content.ilike.%${keyword}%`
        )
      }

      // 分页
      const from = (page - 1) * pageSize
      const to = from + pageSize - 1

      const { data, error, count } = await queryBuilder
        .order('order_num', { ascending: true })
        .range(from, to)

      if (error) {
        throw error
      }

      return {
        data: data || [],
        total: count || 0,
        page,
        pageSize,
        totalPages: Math.ceil((count || 0) / pageSize),
      }
    } catch (err) {
      console.error('获取知识点失败:', err)
      return {
        data: [],
        total: 0,
        page,
        pageSize,
        totalPages: 0,
      }
    }
  }

  /**
   * 根据 ID 获取知识点
   */
  static async getNodeById(id: string): Promise<KnowledgeNode | null> {
    try {
      const { data, error } = await supabase
        .from('knowledge_nodes')
        .select('*')
        .eq('id', id)
        .single()

      if (error) {
        throw error
      }

      return data
    } catch (err) {
      console.error('获取知识点详情失败:', err)
      return null
    }
  }

  /**
   * 获取多个知识点
   */
  static async getNodesByIds(ids: string[]): Promise<KnowledgeNode[]> {
    try {
      const { data, error } = await supabase
        .from('knowledge_nodes')
        .select('*')
        .in('id', ids)

      if (error) {
        throw error
      }

      return data || []
    } catch (err) {
      console.error('获取知识点列表失败:', err)
      return []
    }
  }

  /**
   * 搜索知识点
   */
  static async searchNodes(keyword: string, limit: number = 10): Promise<KnowledgeNode[]> {
    try {
      const { data, error } = await supabase
        .from('knowledge_nodes')
        .select('*')
        .or(`title.ilike.%${keyword}%,content.ilike.%${keyword}%`)
        .limit(limit)

      if (error) {
        throw error
      }

      return data || []
    } catch (err) {
      console.error('搜索知识点失败:', err)
      return []
    }
  }

  /**
   * 获取考试题目
   */
  static async getExamQuestions(options?: {
    nodeId?: string
    difficulty?: number
    limit?: number
  }): Promise<ExamQuestion[]> {
    const { nodeId, difficulty, limit = 10 } = options || {}

    try {
      let queryBuilder = supabase
        .from('exam_questions')
        .select('*')

      if (nodeId) {
        queryBuilder = queryBuilder.contains('related_nodes', [nodeId])
      }
      if (difficulty) {
        queryBuilder = queryBuilder.eq('difficulty', difficulty)
      }

      const { data, error } = await queryBuilder.limit(limit)

      if (error) {
        throw error
      }

      return data || []
    } catch (err) {
      console.error('获取考试题目失败:', err)
      return []
    }
  }

  /**
   * 根据 ID 获取考试题目
   */
  static async getExamQuestionById(id: string): Promise<ExamQuestion | null> {
    try {
      const { data, error } = await supabase
        .from('exam_questions')
        .select('*')
        .eq('id', id)
        .single()

      if (error) {
        throw error
      }

      return data
    } catch (err) {
      console.error('获取考试题目详情失败:', err)
      return null
    }
  }

  /**
   * 获取推导链
   */
  static async getCausalChains(options?: {
    nodeId?: string
    difficulty?: number
    limit?: number
  }): Promise<CausalChain[]> {
    const { nodeId, difficulty, limit = 10 } = options || {}

    try {
      let queryBuilder = supabase
        .from('causal_chains')
        .select('*')

      if (nodeId) {
        queryBuilder = queryBuilder.contains('related_nodes', [nodeId])
      }
      if (difficulty) {
        queryBuilder = queryBuilder.eq('difficulty', difficulty)
      }

      const { data, error } = await queryBuilder.limit(limit)

      if (error) {
        throw error
      }

      return data || []
    } catch (err) {
      console.error('获取推导链失败:', err)
      return []
    }
  }

  /**
   * 根据 ID 获取推导链
   */
  static async getCausalChainById(id: string): Promise<CausalChain | null> {
    try {
      const { data, error } = await supabase
        .from('causal_chains')
        .select('*')
        .eq('id', id)
        .single()

      if (error) {
        throw error
      }

      return data
    } catch (err) {
      console.error('获取推导链详情失败:', err)
      return null
    }
  }

  /**
   * 获取病例
   */
  static async getCases(options?: {
    nodeId?: string
    difficulty?: number
    limit?: number
  }): Promise<MedicalCase[]> {
    const { nodeId, difficulty, limit = 10 } = options || {}

    try {
      let queryBuilder = supabase
        .from('cases')
        .select('*')

      if (nodeId) {
        queryBuilder = queryBuilder.contains('related_nodes', [nodeId])
      }
      if (difficulty) {
        queryBuilder = queryBuilder.eq('difficulty', difficulty)
      }

      const { data, error } = await queryBuilder.limit(limit)

      if (error) {
        throw error
      }

      return data || []
    } catch (err) {
      console.error('获取病例失败:', err)
      return []
    }
  }

  /**
   * 根据 ID 获取病例
   */
  static async getCaseById(id: string): Promise<MedicalCase | null> {
    try {
      const { data, error } = await supabase
        .from('cases')
        .select('*')
        .eq('id', id)
        .single()

      if (error) {
        throw error
      }

      return data
    } catch (err) {
      console.error('获取病例详情失败:', err)
      return null
    }
  }

  /**
   * 获取学科列表
   */
  static async getSubjects(): Promise<string[]> {
    try {
      const { data, error } = await supabase
        .from('knowledge_nodes')
        .select('subject')
        .not('subject', 'is', null)

      if (error) {
        throw error
      }

      // 去重
      const subjects = [...new Set(data?.map(item => item.subject).filter(Boolean))]
      return subjects as string[]
    } catch (err) {
      console.error('获取学科列表失败:', err)
      return []
    }
  }

  /**
   * 获取章节列表
   */
  static async getChapters(subject?: string): Promise<string[]> {
    try {
      let queryBuilder = supabase
        .from('knowledge_nodes')
        .select('chapter')
        .not('chapter', 'is', null)

      if (subject) {
        queryBuilder = queryBuilder.eq('subject', subject)
      }

      const { data, error } = await queryBuilder

      if (error) {
        throw error
      }

      // 去重
      const chapters = [...new Set(data?.map(item => item.chapter).filter(Boolean))]
      return chapters as string[]
    } catch (err) {
      console.error('获取章节列表失败:', err)
      return []
    }
  }

  /**
   * 获取知识点数量
   */
  static async getNodeCount(): Promise<number> {
    try {
      const { count, error } = await supabase
        .from('knowledge_nodes')
        .select('*', { count: 'exact', head: true })

      if (error) {
        throw error
      }

      return count || 0
    } catch (err) {
      console.error('获取知识点数量失败:', err)
      return 0
    }
  }

  /**
   * 保存 AI 生成的病例
   */
  static async saveGeneratedCase(
    userId: string,
    caseData: Omit<MedicalCase, 'id' | 'created_at' | 'updated_at'>
  ): Promise<{ success: boolean; id?: string; error?: string }> {
    try {
      const { data, error } = await supabase
        .from('cases')
        .insert({
          ...caseData,
          source: 'ai-generated',
          creator_user_id: userId,
        })
        .select('id')
        .single()

      if (error) {
        throw error
      }

      return { success: true, id: data.id }
    } catch (err: any) {
      return {
        success: false,
        error: err.message || '保存失败',
      }
    }
  }

  /**
   * 保存 AI 生成的推导链
   */
  static async saveGeneratedChain(
    userId: string,
    chainData: Omit<CausalChain, 'id' | 'created_at' | 'updated_at'>
  ): Promise<{ success: boolean; id?: string; error?: string }> {
    try {
      const { data, error } = await supabase
        .from('causal_chains')
        .insert({
          ...chainData,
          source: 'ai-generated',
          creator_user_id: userId,
        })
        .select('id')
        .single()

      if (error) {
        throw error
      }

      return { success: true, id: data.id }
    } catch (err: any) {
      return {
        success: false,
        error: err.message || '保存失败',
      }
    }
  }
}

export default KnowledgeService