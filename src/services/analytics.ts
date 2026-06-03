/**
 * 数据分析服务
 * 替代 analytics 云函数，使用 Supabase 查询
 */

import { supabase } from '../lib/supabase/client'
import type { StudyActivity, SpacedRepetition, UserLearningStats, NodeMastery } from '../lib/supabase/types'

export interface MasteryDistribution {
  excellent: number  // 90-100
  good: number       // 70-89
  fair: number       // 50-69
  poor: number       // 30-49
  veryPoor: number   // 0-29
}

export interface WeakPoint {
  nodeId: string
  nodeTitle?: string
  subject?: string
  avgScore: number
  wrongCount: number
  totalAttempts: number
  errorRate: number
}

export interface ActivityTimelineItem {
  date: string
  count: number
  duration: number
  types: Record<string, number>
}

export interface LearningStats {
  masteryDistribution: MasteryDistribution
  weakPoints: WeakPoint[]
  activityTimeline: ActivityTimelineItem[]
  streakDays: number
  weeklyFeynmanCount: number
  todayReviewCount: number
  totalFeynmanCount: number
  totalExamCount: number
  totalWrongCount: number
  totalActivityCount: number
  averageExamScore: number
}

/**
 * 数据分析服务类
 */
export class AnalyticsService {
  /**
   * 获取完整学习统计
   */
  static async getLearningStats(userId: string): Promise<LearningStats> {
    try {
      // 并行获取所有数据
      const [
        masteryDistribution,
        weakPoints,
        activityTimeline,
        streakDays,
        weeklyFeynmanCount,
        todayReviewCount,
        feynmanCount,
        examCount,
        wrongCount,
        activityCount,
        averageExamScore,
      ] = await Promise.all([
        this.getMasteryDistribution(userId),
        this.getWeakPoints(userId),
        this.getActivityTimeline(userId),
        this.getStreakDays(userId),
        this.getWeeklyFeynmanCount(userId),
        this.getTodayReviewCount(userId),
        this.getTotalFeynmanCount(userId),
        this.getTotalExamCount(userId),
        this.getTotalWrongCount(userId),
        this.getTotalActivityCount(userId),
        this.getAverageExamScore(userId),
      ])

      return {
        masteryDistribution,
        weakPoints,
        activityTimeline,
        streakDays,
        weeklyFeynmanCount,
        todayReviewCount,
        totalFeynmanCount: feynmanCount,
        totalExamCount: examCount,
        totalWrongCount: wrongCount,
        totalActivityCount: activityCount,
        averageExamScore,
      }
    } catch (err) {
      console.error('获取学习统计失败:', err)
      return this.getEmptyStats()
    }
  }

  /**
   * 获取掌握度分布
   */
  static async getMasteryDistribution(userId: string): Promise<MasteryDistribution> {
    try {
      const { data, error } = await supabase
        .from('feynman_records')
        .select('node_id, ai_score')
        .eq('user_id', userId)

      if (error) {
        throw error
      }

      const distribution: MasteryDistribution = {
        excellent: 0,
        good: 0,
        fair: 0,
        poor: 0,
        veryPoor: 0,
      }

      if (!data || data.length === 0) {
        return distribution
      }

      // 按知识点聚合最新分数
      const nodeScores: Record<string, number> = {}
      for (const record of data) {
        const score = record.ai_score as any
        const avgScore =
          ((score.accuracy || 0) +
            (score.completeness || 0) +
            (score.clarity || 0) +
            (score.depth || 0)) /
          4

        // 保留最新分数
        nodeScores[record.node_id] = avgScore
      }

      // 统计分布
      for (const score of Object.values(nodeScores)) {
        if (score >= 90) distribution.excellent++
        else if (score >= 70) distribution.good++
        else if (score >= 50) distribution.fair++
        else if (score >= 30) distribution.poor++
        else distribution.veryPoor++
      }

      return distribution
    } catch (err) {
      console.error('获取掌握度分布失败:', err)
      return { excellent: 0, good: 0, fair: 0, poor: 0, veryPoor: 0 }
    }
  }

  /**
   * 获取薄弱知识点
   */
  static async getWeakPoints(userId: string, limit: number = 20): Promise<WeakPoint[]> {
    try {
      // 获取费曼复述记录
      const { data: feynmanRecords, error: feynmanError } = await supabase
        .from('feynman_records')
        .select('node_id, ai_score')
        .eq('user_id', userId)

      if (feynmanError) {
        throw feynmanError
      }

      // 获取错题记录
      const { data: wrongQuestions, error: wrongError } = await supabase
        .from('wrong_questions')
        .select('node_id')
        .eq('user_id', userId)

      if (wrongError) {
        throw wrongError
      }

      // 按知识点聚合数据
      const nodeData: Record<string, { scores: number[]; wrongCount: number }> = {}

      // 处理费曼复述记录
      if (feynmanRecords) {
        for (const record of feynmanRecords) {
          const { node_id, ai_score } = record
          if (!node_id || !ai_score) continue

          const score = ai_score as any
          const avgScore =
            ((score.accuracy || 0) +
              (score.completeness || 0) +
              (score.clarity || 0) +
              (score.depth || 0)) /
            4

          if (!nodeData[node_id]) {
            nodeData[node_id] = { scores: [], wrongCount: 0 }
          }
          nodeData[node_id].scores.push(avgScore)
        }
      }

      // 处理错题记录
      if (wrongQuestions) {
        for (const wrong of wrongQuestions) {
          const { node_id } = wrong
          if (!node_id) continue

          if (!nodeData[node_id]) {
            nodeData[node_id] = { scores: [], wrongCount: 0 }
          }
          nodeData[node_id].wrongCount++
        }
      }

      // 计算薄弱知识点
      const weakPoints: WeakPoint[] = []

      for (const [nodeId, data] of Object.entries(nodeData)) {
        const avgScore =
          data.scores.length > 0
            ? data.scores.reduce((a, b) => a + b, 0) / data.scores.length
            : 0

        const totalAttempts = data.scores.length + data.wrongCount
        const errorRate = totalAttempts > 0 ? data.wrongCount / totalAttempts : 0

        // 平均分 < 60 或错误率 > 30% 视为薄弱
        if (avgScore < 60 || errorRate > 0.3) {
          weakPoints.push({
            nodeId,
            avgScore: Math.round(avgScore),
            wrongCount: data.wrongCount,
            totalAttempts,
            errorRate: Math.round(errorRate * 100),
          })
        }
      }

      // 按薄弱程度排序
      weakPoints.sort((a, b) => {
        const scoreA = a.avgScore * (1 - a.errorRate / 100)
        const scoreB = b.avgScore * (1 - b.errorRate / 100)
        return scoreA - scoreB
      })

      return weakPoints.slice(0, limit)
    } catch (err) {
      console.error('获取薄弱知识点失败:', err)
      return []
    }
  }

  /**
   * 获取学习活动时间线（最近7天）
   */
  static async getActivityTimeline(userId: string): Promise<ActivityTimelineItem[]> {
    try {
      const now = new Date()
      const sevenDaysAgo = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000)

      const { data, error } = await supabase
        .from('study_activities')
        .select('type, duration, created_at')
        .eq('user_id', userId)
        .gte('created_at', sevenDaysAgo.toISOString())
        .order('created_at', { ascending: true })

      if (error) {
        throw error
      }

      // 初始化时间线
      const timeline: Record<string, ActivityTimelineItem> = {}
      for (let i = 0; i < 7; i++) {
        const date = new Date(now.getTime() - i * 24 * 60 * 60 * 1000)
        const dateStr = date.toISOString().split('T')[0]
        timeline[dateStr] = {
          date: dateStr,
          count: 0,
          duration: 0,
          types: {},
        }
      }

      // 填充数据
      if (data) {
        for (const activity of data) {
          const dateStr = new Date(activity.created_at).toISOString().split('T')[0]
          if (timeline[dateStr]) {
            timeline[dateStr].count++
            timeline[dateStr].duration += activity.duration || 0
            const type = activity.type || 'unknown'
            timeline[dateStr].types[type] = (timeline[dateStr].types[type] || 0) + 1
          }
        }
      }

      // 转换为数组并排序
      return Object.values(timeline).sort((a, b) => a.date.localeCompare(b.date))
    } catch (err) {
      console.error('获取学习活动时间线失败:', err)
      return []
    }
  }

  /**
   * 获取连续学习天数
   */
  static async getStreakDays(userId: string): Promise<number> {
    try {
      const { data, error } = await supabase
        .from('study_activities')
        .select('created_at')
        .eq('user_id', userId)
        .order('created_at', { ascending: false })

      if (error) {
        throw error
      }

      if (!data || data.length === 0) {
        return 0
      }

      // 获取所有学习日期（去重）
      const studyDates = new Set<string>()
      for (const activity of data) {
        const dateStr = new Date(activity.created_at).toISOString().split('T')[0]
        studyDates.add(dateStr)
      }

      // 从今天开始往前计算连续天数
      const now = new Date()
      let streak = 0

      for (let i = 0; i < 365; i++) {
        const date = new Date(now.getTime() - i * 24 * 60 * 60 * 1000)
        const dateStr = date.toISOString().split('T')[0]

        if (studyDates.has(dateStr)) {
          streak++
        } else {
          // 如果今天还没有学习记录，不算中断
          if (i === 0) continue
          break
        }
      }

      return streak
    } catch (err) {
      console.error('获取连续学习天数失败:', err)
      return 0
    }
  }

  /**
   * 获取本周费曼复述完成数
   */
  static async getWeeklyFeynmanCount(userId: string): Promise<number> {
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

  /**
   * 获取今日待复习知识点数
   */
  static async getTodayReviewCount(userId: string): Promise<number> {
    try {
      const today = new Date()
      today.setHours(23, 59, 59, 999)

      const { count, error } = await supabase
        .from('spaced_repetition')
        .select('*', { count: 'exact', head: true })
        .eq('user_id', userId)
        .lte('next_review', today.toISOString())

      if (error) {
        throw error
      }

      return count || 0
    } catch (err) {
      console.error('获取今日待复习数失败:', err)
      return 0
    }
  }

  /**
   * 获取费曼复述总数
   */
  static async getTotalFeynmanCount(userId: string): Promise<number> {
    try {
      const { count, error } = await supabase
        .from('feynman_records')
        .select('*', { count: 'exact', head: true })
        .eq('user_id', userId)

      if (error) {
        throw error
      }

      return count || 0
    } catch (err) {
      console.error('获取费曼复述总数失败:', err)
      return 0
    }
  }

  /**
   * 获取考试总数
   */
  static async getTotalExamCount(userId: string): Promise<number> {
    try {
      const { count, error } = await supabase
        .from('exam_sessions')
        .select('*', { count: 'exact', head: true })
        .eq('user_id', userId)

      if (error) {
        throw error
      }

      return count || 0
    } catch (err) {
      console.error('获取考试总数失败:', err)
      return 0
    }
  }

  /**
   * 获取错题总数
   */
  static async getTotalWrongCount(userId: string): Promise<number> {
    try {
      const { count, error } = await supabase
        .from('wrong_questions')
        .select('*', { count: 'exact', head: true })
        .eq('user_id', userId)

      if (error) {
        throw error
      }

      return count || 0
    } catch (err) {
      console.error('获取错题总数失败:', err)
      return 0
    }
  }

  /**
   * 获取学习活动总数
   */
  static async getTotalActivityCount(userId: string): Promise<number> {
    try {
      const { count, error } = await supabase
        .from('study_activities')
        .select('*', { count: 'exact', head: true })
        .eq('user_id', userId)

      if (error) {
        throw error
      }

      return count || 0
    } catch (err) {
      console.error('获取学习活动总数失败:', err)
      return 0
    }
  }

  /**
   * 获取考试平均分
   */
  static async getAverageExamScore(userId: string): Promise<number> {
    try {
      const { data, error } = await supabase
        .from('exam_sessions')
        .select('score')
        .eq('user_id', userId)

      if (error) {
        throw error
      }

      if (!data || data.length === 0) {
        return 0
      }

      const totalScore = data.reduce((sum, session) => sum + session.score, 0)
      return Math.round(totalScore / data.length)
    } catch (err) {
      console.error('获取考试平均分失败:', err)
      return 0
    }
  }

  /**
   * 获取知识点掌握度详情（使用视图）
   */
  static async getNodeMasteryDetails(userId: string): Promise<NodeMastery[]> {
    try {
      const { data, error } = await supabase
        .from('node_mastery')
        .select('*')
        .eq('user_id', userId)
        .order('avg_accuracy', { ascending: true })

      if (error) {
        throw error
      }

      return data || []
    } catch (err) {
      console.error('获取知识点掌握度详情失败:', err)
      return []
    }
  }

  /**
   * 获取学习统计概览（使用视图）
   */
  static async getLearningStatsOverview(userId: string): Promise<UserLearningStats | null> {
    try {
      const { data, error } = await supabase
        .from('user_learning_stats')
        .select('*')
        .eq('user_id', userId)
        .single()

      if (error) {
        if (error.code === 'PGRST116') {
          return null
        }
        throw error
      }

      return data
    } catch (err) {
      console.error('获取学习统计概览失败:', err)
      return null
    }
  }

  /**
   * 获取空统计数据
   */
  private static getEmptyStats(): LearningStats {
    return {
      masteryDistribution: { excellent: 0, good: 0, fair: 0, poor: 0, veryPoor: 0 },
      weakPoints: [],
      activityTimeline: [],
      streakDays: 0,
      weeklyFeynmanCount: 0,
      todayReviewCount: 0,
      totalFeynmanCount: 0,
      totalExamCount: 0,
      totalWrongCount: 0,
      totalActivityCount: 0,
      averageExamScore: 0,
    }
  }
}

export default AnalyticsService