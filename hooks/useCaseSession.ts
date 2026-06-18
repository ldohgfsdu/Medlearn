import { useQuery } from '@tanstack/react-query'
import { supabase } from '@/lib/supabase'
import type { ScoreReport } from '@/shared/case-scoring'
import { parseScoreReport } from '@/utils/scoreReport'

export type CaseTemplateSummary = {
  id: string
  case_code: string
  title: string
  chief_complaint: string
  specialty: string
  difficulty: string
  estimated_minutes: number
  demographics: Record<string, unknown> | null
  patient_world: Record<string, unknown> | null
  is_active: boolean
  review_status: string
}

export type CaseSessionRecord = {
  id: string
  user_id: string
  case_id: string
  status: string
  current_phase: string
  revealed: Record<string, unknown> | null
  submitted: Record<string, unknown> | null
  hints_used: number
  max_hints: number
  started_at: string
  completed_at: string | null
  duration_seconds: number | null
  turn_count: number
  score: ScoreReport | null
  total_tokens: number | null
  total_cost: number | null
  created_at: string
  updated_at: string
  case_templates: CaseTemplateSummary | CaseTemplateSummary[] | null
}

export function resolveCaseTemplate(
  joined: CaseTemplateSummary | CaseTemplateSummary[] | null | undefined,
): CaseTemplateSummary | null {
  if (!joined) return null
  return Array.isArray(joined) ? (joined[0] ?? null) : joined
}

/**
 * 统一获取病例会话（含病例模板）
 * chat / diagnose / treat / score 页面共用
 */
export function useCaseSession(sessionId: string | undefined) {
  return useQuery({
    queryKey: ['caseSession', sessionId],
    queryFn: async () => {
      const { data, error } = await supabase
        .from('case_sessions')
        .select(
          'id,user_id,case_id,status,current_phase,revealed,submitted,hints_used,max_hints,started_at,completed_at,duration_seconds,turn_count,score,total_tokens,total_cost,created_at,updated_at,case_templates(id,case_code,title,chief_complaint,specialty,difficulty,estimated_minutes,demographics,patient_world,is_active,review_status)',
        )
        .eq('id', sessionId!)
        .single()

      if (error) throw error
      return {
        ...data,
        score: parseScoreReport(data.score),
      } as CaseSessionRecord
    },
    enabled: !!sessionId,
  })
}
