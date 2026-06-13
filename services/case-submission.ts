import { supabase } from '@/lib/supabase'
import type { ScoreReport } from '@/shared/case-scoring'

interface CaseSubmitResponse {
  score: ScoreReport
}

export async function submitCaseForScoring(
  sessionId: string,
  treatments: string[],
): Promise<ScoreReport> {
  const { data, error } = await supabase.functions.invoke<CaseSubmitResponse>('case-submit', {
    body: { sessionId, treatments },
  })

  if (error) throw new Error(error.message)
  if (!data?.score) throw new Error('评分服务未返回结果')
  return data.score
}
