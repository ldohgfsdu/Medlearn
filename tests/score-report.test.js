const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTypeScriptModule } = require('./loadTsModule')

const root = path.resolve(__dirname, '..')
const caseScoring = loadTypeScriptModule(
  path.join(root, 'supabase', 'functions', '_shared', 'case-scoring.ts'),
)
const { parseScoreReport, getTotalScore } = loadTypeScriptModule(
  path.join(root, 'utils', 'scoreReport.ts'),
  { '@/shared/case-scoring': caseScoring },
)

const validReport = {
  totalScore: 82,
  grade: 'good',
  diagnosis: { score: 20, maxScore: 25, analysis: 'ok', details: [] },
  differential: { score: 18, maxScore: 20, analysis: 'ok', details: [] },
  evidence: { score: 22, maxScore: 25, analysis: 'ok', details: [] },
  treatment: { score: 22, maxScore: 30, analysis: 'ok', details: [] },
  strengths: ['诊断准确'],
  weaknesses: ['治疗不完整'],
  recommendations: ['复习抗血小板方案'],
}

test('parseScoreReport accepts a complete score report', () => {
  const parsed = parseScoreReport(validReport)
  assert.equal(parsed?.totalScore, 82)
  assert.equal(parsed?.grade, 'good')
})

test('parseScoreReport rejects malformed payloads', () => {
  assert.equal(parseScoreReport(null), null)
  assert.equal(parseScoreReport({ totalScore: 50 }), null)
})

test('getTotalScore returns null for invalid values', () => {
  assert.equal(getTotalScore(parseScoreReport(validReport)), 82)
  assert.equal(getTotalScore(null), null)
})