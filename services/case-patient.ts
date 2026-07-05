import { getCasePatientAIOverride } from '@/services/ai-runtime'
import { supabase } from '@/lib/supabase'

interface CasePatientResponse {
  response?: string
  source?: 'preset' | 'ai' | 'safety_fallback'
  revealed?: {
    historyFieldId?: string
    examId?: string
    testId?: string
    hintFieldId?: string
  }
}

export type CasePatientIntentType = 'ask_history' | 'physical_exam' | 'order_test' | 'hint'

export interface CasePatientIntent {
  intentType: CasePatientIntentType
  target?: string
}

export async function requestCasePatientTurn(
  sessionId: string,
  question: string,
  intent?: CasePatientIntent,
): Promise<Required<Pick<CasePatientResponse, 'response'>> & Omit<CasePatientResponse, 'response'>> {
  const aiOverride = await getCasePatientAIOverride()
  const { data, error } = await supabase.functions.invoke<CasePatientResponse>('case-patient', {
    body: {
      sessionId,
      question,
      ...(intent ? { intent } : {}),
      ...(aiOverride ? { ai_override: aiOverride } : {}),
    },
  })

  if (error) throw new Error(error.message)
  if (!data?.response) throw new Error('Case patient service returned no response')
  return {
    response: data.response,
    source: data.source,
    revealed: data.revealed,
  }
}

export async function requestCasePatientResponse(
  sessionId: string,
  question: string,
): Promise<string> {
  return (await requestCasePatientTurn(sessionId, question)).response
}
