import { supabase } from '@/lib/supabase'
import type { EvaluationResult } from './ai'

export interface SaveFeynmanRecordInput {
  userId: string
  nodeId: string
  transcript: string
  result: EvaluationResult
  attempt?: number
}

export async function saveFeynmanRecord({
  userId,
  nodeId,
  transcript,
  result,
  attempt = 1,
}: SaveFeynmanRecordInput): Promise<void> {
  const { error } = await supabase.from('feynman_records').insert({
    user_id: userId,
    node_id: nodeId,
    transcript,
    ai_score: {
      score: result.score,
      totalScore: result.score,
      missingPoints: result.missingPoints,
      strengths: result.strengths ?? [],
      nextSentence: result.nextSentence ?? '',
      attempt,
    },
    feedback: result.feedback,
  })

  if (error) {
    throw error
  }
}