export type CaseDifficulty = 'beginner' | 'intermediate' | 'advanced'
export type ConfidenceLevel = 1 | 2 | 3

export interface CalibrationFeedback {
  title: string
  summary: string
  action: string
}

export function recommendStretchDifficulty(latestScore?: number | null): CaseDifficulty {
  if (latestScore == null) return 'beginner'
  if (latestScore >= 85) return 'advanced'
  if (latestScore >= 60) return 'intermediate'
  return 'beginner'
}

export function getDifficultyLabel(difficulty: CaseDifficulty): string {
  return {
    beginner: '基础',
    intermediate: '进阶',
    advanced: '挑战',
  }[difficulty]
}

export function getCalibrationFeedback(
  confidence: ConfidenceLevel | undefined,
  score: number,
  uncertainty?: string
): CalibrationFeedback | null {
  if (!confidence) return null

  if (confidence === 3 && score < 60) {
    return {
      title: '确定感高于实际表现',
      summary: uncertainty
        ? `你当时最不确定的是“${uncertainty}”，但结果还暴露了更多盲点。`
        : '高确定感与当前结果存在偏差，这是一次重要的认知校准。',
      action: '下一轮先写证据，再判断自己有多确定。',
    }
  }

  if (confidence === 1 && score >= 80) {
    return {
      title: '你的掌握比感觉更稳',
      summary: uncertainty
        ? `即使你对“${uncertainty}”没有把握，整体判断仍然可靠。`
        : '低确定感与良好结果并不一致，你可能低估了自己的掌握。',
      action: '复盘正确依据，建立可重复使用的判断标准。',
    }
  }

  return {
    title: '自我判断与结果基本一致',
    summary: uncertainty
      ? `你提前识别了“${uncertainty}”这个疑点，元认知判断有效。`
      : '你对自身掌握程度的判断较准确。',
    action: '继续在提交前标记最大疑点，用结果反复校准判断。',
  }
}
