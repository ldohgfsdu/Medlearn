import { useState, useCallback } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { supabase } from '@/lib/supabase'
import { generateExamQuestions, calculateScore, type ExamQuestion } from '@/services/exam'

/**
 * 获取知识点的历史考试记录
 */
export function useExamHistory(userId: string | undefined, nodeId?: string) {
  return useQuery({
    queryKey: ['examHistory', userId, nodeId],
    queryFn: async () => {
      let query = supabase
        .from('exam_sessions')
        .select('*')
        .eq('user_id', userId!)
        .order('created_at', { ascending: false })
        .limit(20)

      if (nodeId) {
        query = query.contains('weak_nodes', [nodeId])
      }

      const { data, error } = await query
      if (error) throw error
      return data || []
    },
    enabled: !!userId,
  })
}

/**
 * 考试会话 Hook（管理答题流程）
 */
export function useExamSession(userId: string | undefined) {
  const [questions, setQuestions] = useState<ExamQuestion[]>([])
  const [currentIndex, setCurrentIndex] = useState(0)
  const [answers, setAnswers] = useState<Record<number, number>>({})
  const [loading, setLoading] = useState(false)
  const [completed, setCompleted] = useState(false)
  const queryClient = useQueryClient()

  const startExam = useCallback(async (nodeIds: string[], count = 10, difficulty = 2) => {
    setLoading(true)
    try {
      const qs = await generateExamQuestions(nodeIds, count, difficulty)
      setQuestions(qs)
      setCurrentIndex(0)
      setAnswers({})
      setCompleted(false)
    } finally {
      setLoading(false)
    }
  }, [])

  const answerQuestion = useCallback((questionIndex: number, answer: number) => {
    setAnswers(prev => ({ ...prev, [questionIndex]: answer }))
  }, [])

  const nextQuestion = useCallback(() => {
    if (currentIndex < questions.length - 1) {
      setCurrentIndex(prev => prev + 1)
    }
  }, [currentIndex, questions.length])

  const prevQuestion = useCallback(() => {
    if (currentIndex > 0) {
      setCurrentIndex(prev => prev - 1)
    }
  }, [currentIndex])

  const goToQuestion = useCallback((questionIndex: number) => {
    if (questionIndex >= 0 && questionIndex < questions.length) {
      setCurrentIndex(questionIndex)
    }
  }, [questions.length])

  const finishExam = useCallback(async () => {
    if (!userId) return null
    const { totalScore, wrongQuestions: wrongIdxs } = calculateScore(questions, answers)

    // 保存考试会话
    const { data: session, error } = await supabase
      .from('exam_sessions')
      .insert({
        user_id: userId,
        question_ids: questions.map(q => q.id),
        score: totalScore,
        weak_nodes: wrongIdxs
          .map(i => questions[i]?.related_nodes || [])
          .flat()
          .filter((v: string, i: number, a: string[]) => a.indexOf(v) === i),
        duration: 0,
      })
      .select()
      .single()

    if (error) throw error

    // 记录学习活动
    const { error: activityError } = await supabase.from('study_activities').insert({
      user_id: userId,
      type: 'exam',
      score: totalScore,
      session_id: session.id,
    })
    if (activityError) throw activityError

    setCompleted(true)
    queryClient.invalidateQueries({ queryKey: ['examHistory'] })
    queryClient.invalidateQueries({ queryKey: ['homeStats'] })

    return { totalScore, wrongQuestions: wrongIdxs, sessionId: session.id }
  }, [userId, questions, answers, queryClient])

  return {
    questions,
    currentIndex,
    answers,
    loading,
    completed,
    currentQuestion: questions[currentIndex] || null,
    totalQuestions: questions.length,
    answeredCount: Object.keys(answers).length,
    startExam,
    answerQuestion,
    nextQuestion,
    prevQuestion,
    goToQuestion,
    finishExam,
  }
}
