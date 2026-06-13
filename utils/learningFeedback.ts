import type { ScoreDimension, ScoreReport } from '@/services/scoring-engine'

export type CaseFocusKey = 'diagnosis' | 'differential' | 'evidence' | 'treatment'

export interface CaseFeedbackFocus {
  key: CaseFocusKey
  title: string
  summary: string
  action: string
  percent: number
}

const FOCUS_COPY: Record<CaseFocusKey, { title: string; action: string }> = {
  diagnosis: {
    title: '把诊断说得更精确',
    action: '重做时先写出疾病全称，再用两条关键证据验证它。',
  },
  differential: {
    title: '补上最危险的鉴别诊断',
    action: '重做时至少列出一个不能漏掉的诊断，并写清排除依据。',
  },
  evidence: {
    title: '让判断落到证据上',
    action: '重做时分别引用一条病史、查体或检查证据支撑结论。',
  },
  treatment: {
    title: '先处理关键治疗步骤',
    action: '重做时先写危及生命问题的立即处理，再补充后续方案。',
  },
}

function dimensionPercent(dimension: ScoreDimension): number {
  if (dimension.maxScore <= 0) return 100
  return Math.round((dimension.score / dimension.maxScore) * 100)
}

export function getCaseFeedbackFocus(report: ScoreReport): CaseFeedbackFocus {
  const dimensions: { key: CaseFocusKey; value: ScoreDimension }[] = [
    { key: 'diagnosis', value: report.diagnosis },
    { key: 'differential', value: report.differential },
    { key: 'evidence', value: report.evidence },
    { key: 'treatment', value: report.treatment },
  ]

  const dangerousTreatment = report.treatment.details.find((detail) => detail.score < 0)
  const selected = dangerousTreatment
    ? dimensions.find((dimension) => dimension.key === 'treatment')!
    : dimensions.reduce((lowest, current) => (
        dimensionPercent(current.value) < dimensionPercent(lowest.value) ? current : lowest
      ))

  const copy = FOCUS_COPY[selected.key]
  const detailFeedback = selected.value.details.find((detail) => detail.feedback)?.feedback
  const summary = dangerousTreatment?.feedback
    || selected.value.analysis
    || detailFeedback
    || report.weaknesses[0]
    || '这部分还有提升空间。'

  return {
    key: selected.key,
    title: copy.title,
    summary,
    action: copy.action,
    percent: dimensionPercent(selected.value),
  }
}

export function uniqueWeakNodeIds(
  wrongQuestionIndexes: number[],
  questions: { related_nodes?: string[] }[]
): string[] {
  return Array.from(new Set(
    wrongQuestionIndexes.flatMap((index) => questions[index]?.related_nodes || [])
  ))
}
