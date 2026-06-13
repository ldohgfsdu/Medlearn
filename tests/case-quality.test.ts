import test from 'node:test'
import assert from 'node:assert/strict'
import { validateCaseQuality } from '../shared/case-quality.ts'

function validCase() {
  return {
    id: 'CC_TEST_001',
    case_code: 'CC_TEST_001',
    title: '测试病例',
    chief_complaint: 'chest_pain',
    difficulty: 'beginner',
    demographics: {
      age: 60,
      presentationContext: '因胸痛来到急诊',
    },
    patient_world: {
      chiefComplaint: '胸痛',
      history: {
        presentIllness: [
          { id: 'onset', field: '起病', answer: '突然', patientVoice: '突然疼起来' },
          { id: 'site', field: '部位', answer: '胸骨后', patientVoice: '胸口中间' },
          { id: 'duration', field: '时长', answer: '一小时', patientVoice: '一个小时了' },
        ],
      },
      physicalExam: { vital_signs: { findings: [] } },
      investigations: { ecg: { result: '异常' } },
    },
    ground_truth: {
      diagnosis: { primary: '疾病A', primaryAliases: ['A'], icd10: 'X00' },
      differentials: [
        {
          diagnosis: '疾病B',
          aliases: [],
          keyDiscriminator: '特征B',
          mustExclude: true,
          supportAgainst: 'against',
        },
        {
          diagnosis: '疾病C',
          aliases: [],
          keyDiscriminator: '特征C',
          mustExclude: false,
          supportAgainst: 'against',
        },
      ],
      criticalEvidence: {
        forDiagnosis: {
          fromHistory: ['病史证据'],
          fromExam: ['查体证据'],
          fromTests: ['检查证据'],
        },
      },
      treatment: {
        immediate: [{ action: '立即处理', isCritical: true, aliases: [] }],
        definitive: [{ action: '后续处理', isCritical: true, aliases: [] }],
        dangerous: [{ action: '危险处理', penalty: 10, aliases: [] }],
      },
    },
    scoring_rubric: {
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
    },
    is_active: true,
    review_status: 'approved',
    reviewed_by: 'reviewer-id',
    reviewed_at: '2026-06-11T00:00:00.000Z',
  }
}

test('case quality accepts a complete reviewed case', () => {
  assert.deepEqual(validateCaseQuality(validCase()), [])
})

test('case quality blocks approval without reviewer and dangerous treatments', () => {
  const record = validCase()
  record.reviewed_by = ''
  record.ground_truth.treatment.dangerous = []
  const issues = validateCaseQuality(record)

  assert.ok(issues.some((issue) => issue.path === 'reviewed_by'))
  assert.ok(
    issues.some((issue) => issue.path === 'ground_truth.treatment.dangerous'),
  )
})
