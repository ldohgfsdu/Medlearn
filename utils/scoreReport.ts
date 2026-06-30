import type { ScoreReport } from '@/shared/case-scoring'

function isScoreDimension(value: unknown): value is ScoreReport['diagnosis'] {
  if (!value || typeof value !== 'object') return false
  const dimension = value as Record<string, unknown>
  return (
    typeof dimension.score === 'number' &&
    typeof dimension.maxScore === 'number' &&
    typeof dimension.analysis === 'string' &&
    Array.isArray(dimension.details)
  )
}

export function parseScoreReport(value: unknown): ScoreReport | null {
  if (!value || typeof value !== 'object') return null

  const report = value as Record<string, unknown>
  if (typeof report.totalScore !== 'number') return null
  if (!isScoreDimension(report.diagnosis)) return null
  if (!isScoreDimension(report.differential)) return null
  if (!isScoreDimension(report.evidence)) return null
  if (!isScoreDimension(report.treatment)) return null
  if (!Array.isArray(report.strengths) || !Array.isArray(report.weaknesses)) return null
  if (!Array.isArray(report.recommendations)) return null
  if (
    report.grade !== 'excellent' &&
    report.grade !== 'good' &&
    report.grade !== 'fair' &&
    report.grade !== 'poor'
  ) {
    return null
  }

  return {
    totalScore: report.totalScore,
    grade: report.grade,
    diagnosis: report.diagnosis,
    differential: report.differential,
    evidence: report.evidence,
    treatment: report.treatment,
    strengths: report.strengths,
    weaknesses: report.weaknesses,
    recommendations: report.recommendations,
  }
}

export function getTotalScore(value: ScoreReport | null | undefined): number | null {
  return typeof value?.totalScore === 'number' ? value.totalScore : null
}