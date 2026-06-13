import { useQuery } from '@tanstack/react-query'
import { supabase } from '@/lib/supabase'

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
      return data
    },
    enabled: !!sessionId,
  })
}
