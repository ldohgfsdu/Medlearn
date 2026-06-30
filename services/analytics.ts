import { supabase } from '@/lib/supabase'
import Constants from 'expo-constants'

// PRD Section 11: 全部 17 个事件
export type CaseEventName =
  | 'case_started'
  | 'feedback_viewed'
  | 'medical_issue_reported'
  | 'patient_message_sent'
  | 'patient_message_received'
  | 'exam_requested'
  | 'test_ordered'
  | 'hint_requested'
  | 'diagnosis_submitted'
  | 'case_completed'
  | 'case_abandoned'
  | 'second_case_started'
  | 'diagnosis_leakage_detected'
  | 'prompt_injection_detected'
  | 'scoring_dispute_submitted'
  | 'llm_error'
  | 'llm_cost_recorded'

interface TrackCaseEventInput {
  eventName: CaseEventName
  userId: string
  sessionId?: string
  caseId?: string | null
  chiefComplaint?: string
  difficulty?: string
  properties?: Record<string, unknown>
}

const APP_VERSION = Constants.expoConfig?.version ?? 'unknown'

export async function trackCaseEvent({
  eventName,
  userId,
  sessionId,
  caseId,
  chiefComplaint,
  difficulty,
  properties = {},
}: TrackCaseEventInput): Promise<void> {
  try {
    const { error } = await supabase.from('case_events').insert({
      event_name: eventName,
      user_id: userId,
      session_id: sessionId,
      case_id: caseId,
      chief_complaint: chiefComplaint ?? null,
      difficulty: difficulty ?? null,
      app_version: APP_VERSION,
      properties,
    })

    if (error) {
      if (eventName === 'case_completed' || eventName === 'llm_cost_recorded') {
        throw error
      }
      console.warn('[analytics] track failed:', eventName, error.message)
    }
  } catch (err) {
    // Never let analytics tracking block or crash the main flow
    if (eventName === 'case_completed' || eventName === 'llm_cost_recorded') {
      throw err
    }
    console.warn('[analytics] track error:', eventName, err instanceof Error ? err.message : err)
  }
}
