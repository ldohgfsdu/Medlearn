/**
 * 考试服务
 * 替代 submitExam 云函数，使用 Supabase 事务
 */

import { supabase } from '../lib/supabase/client'
import type { ExamSession, ExamRecord, WrongQuestion } from '../lib/supabase/types'

export interface ExamAnswer {
  questionId: string
  nodeId?: string
  userAnswer: number
  isCorrect: boolean
}

export interface ExamSubmitData {
  questionIds: string[]
  answers: ExamAnswer[]
  score: number
  weakNodes?: string[]
  duration?: number
}

export interface ExamResult {
  sessionId: string
  score: number
  totalQuestions: number
  correctCount: number
  wrongCount: number
  weakNodes: string[]
}

/**
 * 考试服务类
 */
export class ExamService {
  /**
   * 提交考试结果（使用事务保证数据一致性）
   */
  static async submitExam(
    userId: string,
    examData: ExamSubmitData
  ): Promise<{ success: boolean; result?: ExamResult; error?: string }> {
    try {
      const { questionIds, answers, score, weakNodes = [], duration = 0 } = examData
      const timestamp = new Date().toISOString()

      // 1. 创建考试会话
      const { data: session, error: sessionError } = await supabase
        .from('exam_sessions')
        .insert({
          user_id: userId,
          question_ids: questionIds,
          score,
          weak_nodes: weakNodes,
          duration,
        })
        .select('id')
        .single()

      if (sessionError) {
        throw sessionError
      }

      // 2. 批量创建答题记录
      const examRecords = answers.map(answer => ({
        user_id: userId,
        session_id: session.id,
        question_id: answer.questionId,
        user_answer: answer.userAnswer,
        is_correct: answer.isCorrect,
      }))

      const { error: recordsError } = await supabase
        .from('exam_records')
        .insert(examRecords)

      if (recordsError) {
        throw recordsError
      }

      // 3. 批量创建错题记录
      const wrongAnswers = answers.filter(a => !a.isCorrect)
      if (wrongAnswers.length > 0) {
        const wrongQuestions = wrongAnswers.map(answer => ({
          user_id: userId,
          question_id: answer.questionId,
          node_id: answer.nodeId || null,
          session_id: session.id,
          retry_correct: false,
        }))

        const { error: wrongError } = await supabase
          .from('wrong_questions')
          .insert(wrongQuestions)

        if (wrongError) {
          throw wrongError
        }
      }

      // 4. 创建学习活动记录
      const correctCount = answers.filter(a => a.isCorrect).length
      await supabase.from('study_activities').insert({
        user_id: userId,
        type: 'exam',
        session_id: session.id,
        score,
        duration,
        metadata: {
          question_count: questionIds.length,
          correct_count: correctCount,
          wrong_count: wrongAnswers.length,
        },
      })

      // 5. 返回结果
      const result: ExamResult = {
        sessionId: session.id,
        score,
        totalQuestions: questionIds.length,
        correctCount,
        wrongCount: wrongAnswers.length,
        weakNodes,
      }

      return { success: true, result }
    } catch (err: any) {
      console.error('提交考试失败:', err)
      return {
        success: false,
        error: err.message || '提交失败',
      }
    }
  }

  /**
   * 获取用户考试会话列表
   */
  static async getUserSessions(
    userId: string,
    options?: {
      page?: number
      pageSize?: number
    }
  ): Promise<{ data: ExamSession[]; total: number }> {
    const { page = 1, pageSize = 20 } = options || {}

    try {
      const from = (page - 1) * pageSize
      const to = from + pageSize - 1

      const { data, error, count } = await supabase
        .from('exam_sessions')
        .select('*', { count: 'exact' })
        .eq('user_id', userId)
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
      console.error('获取考试会话失败:', err)
      return {
        data: [],
        total: 0,
      }
    }
  }

  /**
   * 获取考试会话详情
   */
  static async getSessionById(
    userId: string,
    sessionId: string
  ): Promise<ExamSession | null> {
    try {
      const { data, error } = await supabase
        .from('exam_sessions')
        .select('*')
        .eq('id', sessionId)
        .eq('user_id', userId)
        .single()

      if (error) {
        throw error
      }

      return data
    } catch (err) {
      console.error('获取考试会话详情失败:', err)
      return null
    }
  }

  /**
   * 获取考试答题记录
   */
  static async getSessionRecords(
    userId: string,
    sessionId: string
  ): Promise<ExamRecord[]> {
    try {
      const { data, error } = await supabase
        .from('exam_records')
        .select('*')
        .eq('user_id', userId)
        .eq('session_id', sessionId)
        .order('created_at', { ascending: true })

      if (error) {
        throw error
      }

      return data || []
    } catch (err) {
      console.error('获取答题记录失败:', err)
      return []
    }
  }

  /**
   * 获取用户错题列表
   */
  static async getWrongQuestions(
    userId: string,
    options?: {
      retryCorrect?: boolean
      nodeId?: string
      page?: number
      pageSize?: number
    }
  ): Promise<{ data: WrongQuestion[]; total: number }> {
    const { retryCorrect, nodeId, page = 1, pageSize = 20 } = options || {}

    try {
      let queryBuilder = supabase
        .from('wrong_questions')
        .select('*', { count: 'exact' })
        .eq('user_id', userId)

      if (retryCorrect !== undefined) {
        queryBuilder = queryBuilder.eq('retry_correct', retryCorrect)
      }
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
      console.error('获取错题失败:', err)
      return {
        data: [],
        total: 0,
      }
    }
  }

  /**
   * 标记错题已纠正
   */
  static async markWrongQuestionCorrect(
    userId: string,
    wrongQuestionId: string
  ): Promise<{ success: boolean; error?: string }> {
    try {
      const { error } = await supabase
        .from('wrong_questions')
        .update({ retry_correct: true })
        .eq('id', wrongQuestionId)
        .eq('user_id', userId)

      if (error) {
        throw error
      }

      return { success: true }
    } catch (err: any) {
      return {
        success: false,
        error: err.message || '更新失败',
      }
    }
  }

  /**
   * 获取错题数量
   */
  static async getWrongQuestionCount(
    userId: string,
    retryCorrect: boolean = false
  ): Promise<number> {
    try {
      const { count, error } = await supabase
        .from('wrong_questions')
        .select('*', { count: 'exact', head: true })
        .eq('user_id', userId)
        .eq('retry_correct', retryCorrect)

      if (error) {
        throw error
      }

      return count || 0
    } catch (err) {
      console.error('获取错题数量失败:', err)
      return 0
    }
  }

  /**
   * 获取考试平均分
   */
  static async getAverageScore(userId: string): Promise<number> {
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
      console.error('获取平均分失败:', err)
      return 0
    }
  }

  /**
   * 获取考试次数
   */
  static async getExamCount(userId: string): Promise<number> {
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
      console.error('获取考试次数失败:', err)
      return 0
    }
  }
}

export default ExamService