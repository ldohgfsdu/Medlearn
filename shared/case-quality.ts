import type { GroundTruth, ScoringRubric } from './case-scoring'

export interface CaseQualityRecord {
  id?: unknown
  case_code?: unknown
  title?: unknown
  chief_complaint?: unknown
  difficulty?: unknown
  demographics?: unknown
  patient_world?: unknown
  ground_truth?: unknown
  scoring_rubric?: unknown
  is_active?: unknown
  review_status?: unknown
  reviewed_by?: unknown
  reviewed_at?: unknown
}

export interface CaseQualityIssue {
  path: string
  message: string
  severity: 'error' | 'warning'
}

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value)
}

function nonEmptyString(value: unknown): value is string {
  return typeof value === 'string' && value.trim().length > 0
}

function requireString(
  issues: CaseQualityIssue[],
  path: string,
  value: unknown,
): void {
  if (!nonEmptyString(value)) {
    issues.push({ path, message: '必须是非空字符串', severity: 'error' })
  }
}

function requireArray(
  issues: CaseQualityIssue[],
  path: string,
  value: unknown,
  minimum = 1,
): unknown[] {
  if (!Array.isArray(value) || value.length < minimum) {
    issues.push({
      path,
      message: `必须至少包含 ${minimum} 项`,
      severity: 'error',
    })
    return []
  }
  return value
}

function validatePatientWorld(
  issues: CaseQualityIssue[],
  value: unknown,
): void {
  if (!isObject(value)) {
    issues.push({ path: 'patient_world', message: '必须是对象', severity: 'error' })
    return
  }

  requireString(issues, 'patient_world.chiefComplaint', value.chiefComplaint)
  if (!isObject(value.history)) {
    issues.push({
      path: 'patient_world.history',
      message: '必须是对象',
      severity: 'error',
    })
  } else {
    const historyFields = Object.values(value.history).flatMap((section) =>
      Array.isArray(section) ? section : [],
    )
    requireArray(issues, 'patient_world.history.*', historyFields, 3)
    const ids = historyFields
      .filter(isObject)
      .map((field) => field.id)
      .filter(nonEmptyString)
    if (new Set(ids).size !== ids.length) {
      issues.push({
        path: 'patient_world.history.*.id',
        message: '病史字段 ID 不能重复',
        severity: 'error',
      })
    }
    for (const [index, field] of historyFields.entries()) {
      if (!isObject(field)) continue
      requireString(issues, `patient_world.history.*[${index}].id`, field.id)
      requireString(issues, `patient_world.history.*[${index}].field`, field.field)
      requireString(issues, `patient_world.history.*[${index}].answer`, field.answer)
      requireString(
        issues,
        `patient_world.history.*[${index}].patientVoice`,
        field.patientVoice,
      )
    }
  }

  if (!isObject(value.physicalExam) || Object.keys(value.physicalExam).length === 0) {
    issues.push({
      path: 'patient_world.physicalExam',
      message: '必须至少包含一个查体区域',
      severity: 'error',
    })
  }
  if (!isObject(value.investigations) || Object.keys(value.investigations).length === 0) {
    issues.push({
      path: 'patient_world.investigations',
      message: '必须至少包含一个检查项目',
      severity: 'error',
    })
  }
}

function validateGroundTruth(
  issues: CaseQualityIssue[],
  value: unknown,
): void {
  if (!isObject(value)) {
    issues.push({ path: 'ground_truth', message: '必须是对象', severity: 'error' })
    return
  }
  const groundTruth = value as unknown as GroundTruth
  if (!isObject(groundTruth.diagnosis)) {
    issues.push({
      path: 'ground_truth.diagnosis',
      message: '必须是对象',
      severity: 'error',
    })
  } else {
    requireString(issues, 'ground_truth.diagnosis.primary', groundTruth.diagnosis.primary)
    requireArray(
      issues,
      'ground_truth.diagnosis.primaryAliases',
      groundTruth.diagnosis.primaryAliases,
    )
  }

  const differentials = requireArray(
    issues,
    'ground_truth.differentials',
    groundTruth.differentials,
    2,
  )
  if (
    !differentials.some(
      (item) => isObject(item) && item.mustExclude === true,
    )
  ) {
    issues.push({
      path: 'ground_truth.differentials',
      message: '至少需要一个 mustExclude 高风险鉴别诊断',
      severity: 'error',
    })
  }

  const evidence = groundTruth.criticalEvidence?.forDiagnosis
  requireArray(issues, 'ground_truth.criticalEvidence.forDiagnosis.fromHistory', evidence?.fromHistory)
  requireArray(issues, 'ground_truth.criticalEvidence.forDiagnosis.fromExam', evidence?.fromExam)
  requireArray(issues, 'ground_truth.criticalEvidence.forDiagnosis.fromTests', evidence?.fromTests)

  requireArray(
    issues,
    'ground_truth.treatment.immediate',
    groundTruth.treatment?.immediate,
  )
  requireArray(
    issues,
    'ground_truth.treatment.definitive',
    groundTruth.treatment?.definitive,
  )
  requireArray(
    issues,
    'ground_truth.treatment.dangerous',
    groundTruth.treatment?.dangerous,
  )
}

function validateRubric(
  issues: CaseQualityIssue[],
  value: unknown,
): void {
  if (!isObject(value)) {
    issues.push({ path: 'scoring_rubric', message: '必须是对象', severity: 'error' })
    return
  }
  const rubric = value as unknown as ScoringRubric
  const expectedWeights = {
    diagnosis: 40,
    differential: 20,
    evidence: 20,
    treatment: 20,
  }
  const weights = Object.entries(expectedWeights).map(([dimension, expected]) => {
    const actual = rubric[dimension as keyof typeof expectedWeights]?.weight
    if (actual !== expected) {
      issues.push({
        path: `scoring_rubric.${dimension}.weight`,
        message: `MVP 权重必须为 ${expected}`,
        severity: 'error',
      })
    }
    return typeof actual === 'number' ? actual : 0
  })
  if (weights.reduce((total, weight) => total + weight, 0) !== 100) {
    issues.push({
      path: 'scoring_rubric',
      message: '评分权重总和必须为 100',
      severity: 'error',
    })
  }
}

export function validateCaseQuality(record: CaseQualityRecord): CaseQualityIssue[] {
  const issues: CaseQualityIssue[] = []
  requireString(issues, 'id', record.id)
  requireString(issues, 'case_code', record.case_code)
  requireString(issues, 'title', record.title)
  requireString(issues, 'chief_complaint', record.chief_complaint)
  if (!['beginner', 'intermediate', 'advanced'].includes(String(record.difficulty))) {
    issues.push({
      path: 'difficulty',
      message: '难度必须是 beginner、intermediate 或 advanced',
      severity: 'error',
    })
  }

  if (!isObject(record.demographics)) {
    issues.push({ path: 'demographics', message: '必须是对象', severity: 'error' })
  } else {
    if (typeof record.demographics.age !== 'number') {
      issues.push({
        path: 'demographics.age',
        message: '必须是数字',
        severity: 'error',
      })
    }
    requireString(
      issues,
      'demographics.presentationContext',
      record.demographics.presentationContext,
    )
  }

  validatePatientWorld(issues, record.patient_world)
  validateGroundTruth(issues, record.ground_truth)
  validateRubric(issues, record.scoring_rubric)

  if (record.review_status === 'approved') {
    requireString(issues, 'reviewed_by', record.reviewed_by)
    requireString(issues, 'reviewed_at', record.reviewed_at)
  } else if (record.is_active === true) {
    issues.push({
      path: 'is_active',
      message: '未批准病例不应启用',
      severity: 'warning',
    })
  }

  return issues
}
