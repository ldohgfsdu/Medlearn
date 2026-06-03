/**
 * 费曼复述服务
 * 处理费曼复述记录和评分
 */

import { supabase } from '../lib/supabase/client'
import type { FeynmanRecord, AIScore } from '../lib/supabase/types'

export interface FeynmanSubmitData {
  nodeId: string
  transcript: string
  aiScore: AIScore
  feedback?: string
}

/**
 * 费曼复述服务类
 */
export class FeynmanService {
  /**
   * 提交费曼复述记录
   */
  static async submitRecord(
    userId: string,
    data: FeynmanSubmitData
  ): Promise<{ success: boolean; id?: string; error?: string }> {
    try {
      const { data: record, error } = await supabase
        .from('feynman_records')
        .insert({
          user_id: userId,
          node_id: data.nodeId,
          transcript: data.transcript,
          ai_score: data.aiScore,
          feedback: data.feedback,
        })
        .select('id')
        .single()

      if (error) {
        throw error
      }

      // 记录学习活动
      await supabase.from('study_activities').insert({
        user_id: userId,
        type: 'feynman',
        node_id: data.nodeId,
        record_id: record.id,
        score: Math.round(
          (data.aiScore.accuracy +
            data.aiScore.completeness +
            data.aiScore.clarity +
            data.aiScore.depth) /
            4
        ),
      })

      return { success: true, id: record.id }
    } catch (err: any) {
      console.error('提交费曼复述记录失败:', err)
      return {
        success: false,
        error: err.message || '提交失败',
      }
    }
  }

  /**
   * 获取用户的费曼复述记录
   */
  static async getUserRecords(
    userId: string,
    options?: {
      nodeId?: string
      page?: number
      pageSize?: number
    }
  ): Promise<{ data: FeynmanRecord[]; total: number }> {
    const { nodeId, page = 1, pageSize = 20 } = options || {}

    try {
      let queryBuilder = supabase
        .from('feynman_records')
        .select('*', { count: 'exact' })
        .eq('user_id', userId)

      if (nodeId) {
        queryBuilder = queryBuilder.eq('node_id', nodeId)
      }

      const from = (page - 1) * pageSize
      const to = from + pageSize - 1

      const { data, error, count } = await queryBuilder
        .order('created_at', { ascending: false })
        .range(from, to)

      if (error) {
        throw error
      }

      return {
        data: data || [],
        total: count || 0,
      }
    } catch (err) {
      console.error('获取费曼复述记录失败:', err)
      return {
        data: [],
        total: 0,
      }
    }
  }

  /**
   * 获取知识点的最新费曼复述记录
   */
  static async getLatestRecord(
    userId: string,
    nodeId: string
  ): Promise<FeynmanRecord | null> {
    try {
      const { data, error } = await supabase
        .from('feynman_records')
        .select('*')
        .eq('user_id', userId)
        .eq('node_id', nodeId)
        .order('created_at', { ascending: false })
        .limit(1)
        .single()

      if (error) {
        if (error.code === 'PGRST116') {
          // 没有找到记录
          return null
        }
        throw error
      }

      return data
    } catch (err) {
      console.error('获取最新费曼复述记录失败:', err)
      return null
    }
  }

  /**
   * 获取知识点的费曼复述次数
   */
  static async getRecordCount(
    userId: string,
    nodeId?: string
  ): Promise<number> {
    try {
      let queryBuilder = supabase
        .from('feynman_records')
        .select('*', { count: 'exact', head: true })
        .eq('user_id', userId)

      if (nodeId) {
        queryBuilder = queryBuilder.eq('node_id', nodeId)
      }

      const { count, error } = await queryBuilder

      if (error) {
        throw error
      }

      return count || 0
    } catch (err) {
      console.error('获取费曼复述次数失败:', err)
      return 0
    }
  }

  /**
   * 获取知识点的平均分数
   */
  static async getAverageScore(
    userId: string,
    nodeId: string
  ): Promise<AIScore | null> {
    try {
      const { data, error } = await supabase
        .from('feynman_records')
        .select('ai_score')
        .eq('user_id', userId)
        .eq('node_id', nodeId)

      if (error) {
        throw error
      }

      if (!data || data.length === 0) {
        return null
      }

      // 计算平均分
      const scores = data.map(record => record.ai_score as AIScore)
      const avgScore: AIScore = {
        accuracy: Math.round(
          scores.reduce((sum, s) => sum + s.accuracy, 0) / scores.length
        ),
        completeness: Math.round(
          scores.reduce((sum, s) => sum + s.completeness, 0) / scores.length
        ),
        clarity: Math.round(
          scores.reduce((sum, s) => sum + s.clarity, 0) / scores.length
        ),
        depth: Math.round(
          scores.reduce((sum, s) => sum + s.depth, 0) / scores.length
        ),
      }

      return avgScore
    } catch (err) {
      console.error('获取平均分数失败:', err)
      return null
    }
  }

  /**
   * 删除费曼复述记录
   */
  static async deleteRecord(
    userId: string,
    recordId: string
  ): Promise<{ success: boolean; error?: string }> {
    try {
      const { error } = await supabase
        .from('feynman_records')
        .delete()
        .eq('id', recordId)
        .eq('user_id', userId)

      if (error) {
        throw error
      }

      return { success: true }
    } catch (err: any) {
      return {
        success: false,
        error: err.message || '删除失败',
      }
    }
  }

  /**
   * 获取今日费曼复述完成数
   */
  static async getTodayCount(userId: string): Promise<number> {
    try {
      const today = new Date()
      today.setHours(0, 0, 0, 0)

      const { count, error } = await supabase
        .from('feynman_records')
        .select('*', { count: 'exact', head: true })
        .eq('user_id', userId)
        .gte('created_at', today.toISOString())

      if (error) {
        throw error
      }

      return count || 0
    } catch (err) {
      console.error('获取今日费曼复述数失败:', err)
      return 0
    }
  }

  /**
   * 获取本周费曼复述完成数
   */
  static async getWeeklyCount(userId: string): Promise<number> {
    try {
      const now = new Date()
      const weekStart = new Date(now)
      weekStart.setDate(now.getDate() - now.getDay())
      weekStart.setHours(0, 0, 0, 0)

      const { count, error } = await supabase
        .from('feynman_records')
        .select('*', { count: 'exact', head: true })
        .eq('user_id', userId)
        .gte('created_at', weekStart.toISOString())

      if (error) {
        throw error
      }

      return count || 0
    } catch (err) {
      console.error('获取本周费曼复述数失败:', err)
      return 0
    }
  }
}

export default FeynmanService