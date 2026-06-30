import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { supabase } from '@/lib/supabase'
import { calculateNextReview, scoreToQuality, type RepetitionState } from '@/services/spaced-repetition'

/**
 * 获取今日待复习的知识点
 */
export function useDueReviews(userId: string | undefined) {
  return useQuery({
    queryKey: ['dueReviews', userId],
    queryFn: async () => {
      const today = new Date().toISOString()
      const { data, error } = await supabase
        .from('spaced_repetition')
        .select('*, knowledge_nodes(id, title, type, subject, chapter)')
        .eq('user_id', userId!)
        .lte('next_review', today)
        .order('next_review', { ascending: true })

      if (error) throw error
      return data || []
    },
    enabled: !!userId,
  })
}

/**
 * 获取所有复习计划
 */
export function useAllRepetitions(userId: string | undefined) {
  return useQuery({
    queryKey: ['allRepetitions', userId],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('spaced_repetition')
        .select('*, knowledge_nodes(id, title, type, subject)')
        .eq('user_id', userId!)
        .order('next_review', { ascending: true })

      if (error) throw error
      return data || []
    },
    enabled: !!userId,
  })
}

/**
 * 提交复习结果
 */
export function useSubmitReview() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: async ({ userId, nodeId, score }: { userId: string; nodeId: string; score: number }) => {
      // 获取当前状态
      const { data: existing } = await supabase
        .from('spaced_repetition')
        .select('*')
        .eq('user_id', userId)
        .eq('node_id', nodeId)
        .maybeSingle()

      const quality = scoreToQuality(score)
      const current = existing
        ? {
            nodeId: existing.node_id,
            interval: existing.interval ?? 0,
            easeFactor: existing.ease_factor ?? 2.5,
            repetitions: existing.repetitions ?? 0,
            lastQuality: existing.last_quality ?? 0,
          }
        : {
            nodeId,
            interval: 0,
            easeFactor: 2.5,
            repetitions: 0,
            lastQuality: 0,
          }

      const next = calculateNextReview(current, quality)

      if (existing) {
        const { error } = await supabase
          .from('spaced_repetition')
          .update({
            next_review: next.nextReview,
            interval: next.interval,
            ease_factor: next.easeFactor,
            repetitions: next.repetitions,
            last_quality: next.lastQuality,
          })
          .eq('id', existing.id)
        if (error) throw error
      } else {
        const { error } = await supabase
          .from('spaced_repetition')
          .insert({
            user_id: userId,
            node_id: nodeId,
            next_review: next.nextReview,
            interval: next.interval,
            ease_factor: next.easeFactor,
            repetitions: next.repetitions,
            last_quality: next.lastQuality,
          })
        if (error) throw error
      }

      // 记录学习活动
      const { error: activityError } = await supabase.from('study_activities').insert({
        user_id: userId,
        type: 'review',
        node_id: nodeId,
        score,
      })
      if (activityError) throw activityError

      return next
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dueReviews'] })
      queryClient.invalidateQueries({ queryKey: ['allRepetitions'] })
      queryClient.invalidateQueries({ queryKey: ['homeStats'] })
    },
  })
}
