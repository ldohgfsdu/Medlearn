import test from 'node:test'
import assert from 'node:assert/strict'
import {
  scoreCaseSubmission,
  type GroundTruth,
  type ScoringRubric,
} from '../shared/case-scoring.ts'

const groundTruth: GroundTruth = {
  diagnosis: {
    primary: '急性前壁ST段抬高型心肌梗死',
    primaryAliases: ['STEMI', '急性前壁心梗'],
    icd10: 'I21.0',
  },
  differentials: [
    {
      diagnosis: '主动脉夹层',
      aliases: ['夹层'],
      keyDiscriminator: '关注撕裂样疼痛和双侧血压差',
      mustExclude: true,
      supportAgainst: 'against',
    },
    {
      diagnosis: '肺栓塞',
      aliases: ['PE'],
      keyDiscriminator: '关注呼吸困难和静脉血栓风险',
      mustExclude: true,
      supportAgainst: 'against',
    },
  ],
  criticalEvidence: {
    forDiagnosis: {
      fromHistory: ['胸骨后压榨样胸痛'],
      fromExam: ['心率快'],
      fromTests: ['V1-V4 ST段抬高', '肌钙蛋白升高'],
    },
  },
  treatment: {
    immediate: [
      { action: '阿司匹林', isCritical: true, aliases: ['ASA'] },
      { action: '急诊PCI', isCritical: true, aliases: ['PCI'] },
    ],
    definitive: [
      { action: '他汀类药物', isCritical: true, aliases: ['阿托伐他汀'] },
    ],
    dangerous: [
      { action: '溶栓', penalty: 10, aliases: [] },
    ],
  },
}

const rubric: ScoringRubric = {
  diagnosis: {
    weight: 40,
    exactMatch: 40,
    partialMatch: 30,
    categoryMatch: 15,
    hitDifferential: 8,
    wrong: 0,
  },
  differential: {
    weight: 20,
    threeOrMoreWithReasoning: 20,
    threeOrMore: 16,
    two: 12,
    one: 8,
    none: 0,
    missingCritical: -3,
  },
  evidence: {
    weight: 20,
    coverageWeight: 0.5,
    associationWeight: 0.3,
    interpretationWeight: 0.2,
  },
  treatment: {
    weight: 20,
    criticalCoverageWeight: 0.4,
    safetyWeight: 0.3,
    reasonablenessWeight: 0.3,
  },
}

test('case scoring accepts diagnosis aliases and bounds the report to 100', () => {
  const report = scoreCaseSubmission(
    {
      primaryDiagnosis: 'STEMI',
      differentials: [
        { diagnosis: '主动脉夹层', reasoning: '需要通过症状和检查排除危险诊断' },
        { diagnosis: 'PE', reasoning: '需要结合呼吸症状和检查排除' },
      ],
      evidence: ['胸骨后压榨样胸痛', '心率快', 'V1-V4 ST段抬高', '肌钙蛋白升高'],
      treatments: ['阿司匹林', '急诊PCI', '阿托伐他汀'],
    },
    groundTruth,
    rubric,
  )

  assert.equal(report.diagnosis.score, 40)
  assert.equal(report.evidence.score, 20)
  assert.ok(report.totalScore <= 100)
  assert.equal(report.grade, 'excellent')
})

test('case scoring does not penalize an explicitly negated dangerous treatment', () => {
  const report = scoreCaseSubmission(
    {
      primaryDiagnosis: 'STEMI',
      differentials: [],
      evidence: [],
      treatments: ['不使用溶栓', '急诊PCI'],
    },
    groundTruth,
    rubric,
  )

  assert.equal(
    report.treatment.details.some((detail) => detail.score < 0),
    false,
  )
})

test('case scoring penalizes an unnegated dangerous treatment', () => {
  const report = scoreCaseSubmission(
    {
      primaryDiagnosis: 'STEMI',
      differentials: [],
      evidence: [],
      treatments: ['溶栓'],
    },
    groundTruth,
    rubric,
  )

  assert.equal(
    report.treatment.details.some((detail) => detail.score === -10),
    true,
  )
})
