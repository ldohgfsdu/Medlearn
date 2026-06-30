import { getCasePatientAIOverride } from '@/services/ai-runtime'
import { supabase } from '@/lib/supabase'

interface CasePatientResponse {
  response?: string
}

export async function requestCasePatientResponse(
  sessionId: string,
  question: string,
): Promise<string> {
  const aiOverride = await getCasePatientAIOverride()
  const { data, error } = await supabase.functions.invoke<CasePatientResponse>('case-patient', {
    body: {
      sessionId,
      question,
      ...(aiOverride ? { ai_override: aiOverride } : {}),
    },
  })

  if (error) throw new Error(error.message)
  if (!data?.response) throw new Error('患者服务未返回内容')
  return data.response
}
