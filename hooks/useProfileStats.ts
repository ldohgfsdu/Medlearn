import { useQuery } from '@tanstack/react-query'
import { supabase } from '@/lib/supabase'
import { calculateLearningRecordStats } from '@/utils/learningRecords'
import { getTotalScore, parseScoreReport } from '@/utils/scoreReport'

interface ProfileStats {
  xp: number
  cases: number
  learningDays: number
}

/**
 * 个人页面统计数据（XP、病例数、累计学习日）
 */
export function useProfileStats(userId: string | undefined) {
  return useQuery({
    queryKey: ['profileStats', userId],
    queryFn: async (): Promise<ProfileStats> => {
      const { data: sessions } = await supabase
        .from('case_sessions')
        .select('score, completed_at')
        .eq('user_id', userId!)
        .eq('status', 'completed')

      if (!sessions) return { xp: 0, cases: 0, learningDays: 0 }

      const cases = sessions.length
      const xp = sessions.reduce((acc, s) => acc + (getTotalScore(parseScoreReport(s.score)) ?? 0), 0)
      const { learningDays } = calculateLearningRecordStats(sessions)

      return { xp, cases, learningDays }
    },
    enabled: !!userId,
  })
}
