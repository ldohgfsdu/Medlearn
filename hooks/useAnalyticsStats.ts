import { useQuery } from '@tanstack/react-query'
import { supabase } from '@/lib/supabase'
import { resolveCaseTemplate, type CaseTemplateSummary } from '@/hooks/useCaseSession'
import { getTotalScore, parseScoreReport } from '@/utils/scoreReport'

interface AnalyticsData {
  completedCases: number
  avgScore: number
  totalMinutes: number
  subjectScores: { name: string; score: number }[]
  reasoningMetrics: { name: string; value: string }[]
}

/**
 * 学习分析统计数据
 */
export function useAnalyticsStats(userId: string | undefined) {
  return useQuery({
    queryKey: ['analyticsStats', userId],
    queryFn: async (): Promise<AnalyticsData> => {
      const { data: sessions } = await supabase
        .from('case_sessions')
        .select('score, completed_at, started_at, case_templates(specialty)')
        .eq('user_id', userId!)
        .eq('status', 'completed')

      if (!sessions) {
        return { completedCases: 0, avgScore: 0, totalMinutes: 0, subjectScores: [], reasoningMetrics: [] }
      }

      const completedCases = sessions.length

      // Parse score reports once per session to avoid redundant parsing
      const parsedReports = sessions.map((s) => parseScoreReport(s.score))

      // 计算平均分
      const scores = parsedReports
        .map((report) => getTotalScore(report))
        .filter((s): s is number => typeof s === 'number')
      const avgScore = scores.length > 0
        ? Math.round(scores.reduce((a, b) => a + b, 0) / scores.length)
        : 0

      // 计算总学习分钟数
      const totalMinutes = sessions.reduce((acc, s) => {
        if (s.started_at && s.completed_at) {
          const mins = (new Date(s.completed_at).getTime() - new Date(s.started_at).getTime()) / 60000
          return acc + Math.round(mins)
        }
        return acc
      }, 0)

      // 按学科统计分数
      const subjectMap: Record<string, number[]> = {}
      sessions.forEach((s, i) => {
        const template = resolveCaseTemplate(
          s.case_templates as CaseTemplateSummary | CaseTemplateSummary[] | null,
        )
        const subject = template?.specialty || '其他'
        const score = getTotalScore(parsedReports[i])
        if (typeof score === 'number') {
          if (!subjectMap[subject]) subjectMap[subject] = []
          subjectMap[subject].push(score)
        }
      })
      const subjectScores = Object.entries(subjectMap).map(([name, arr]) => ({
        name,
        score: arr.length > 0 ? Math.round(arr.reduce((a, b) => a + b, 0) / arr.length) : 0,
      })).sort((a, b) => b.score - a.score)

      // 推理维度指标
      const diagnosisCorrect = sessions.filter((_s, i) => {
        const report = parsedReports[i]
        const ds = report?.diagnosis.score
        const dm = report?.diagnosis.maxScore
        return typeof ds === 'number' && typeof dm === 'number' && dm > 0 && ds / dm >= 0.75
      }).length
      const diagnosisRate = completedCases > 0 ? Math.round((diagnosisCorrect / completedCases) * 100) : 0

      const reasoningMetrics = [
        { name: '诊断准确率', value: `${diagnosisRate}%` },
        { name: '平均分', value: `${avgScore}` },
        { name: '完成病例', value: `${completedCases}` },
      ]

      return { completedCases, avgScore, totalMinutes, subjectScores, reasoningMetrics }
    },
    enabled: !!userId,
  })
}
