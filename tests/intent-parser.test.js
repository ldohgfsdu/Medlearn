const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTypeScriptModule } = require('./loadTsModule')

const root = path.resolve(__dirname, '..')
const CasePhase = {
  INTRO: 'intro',
  HISTORY: 'history',
  EXAM: 'exam',
  TESTS: 'tests',
  DIAGNOSIS: 'diagnosis',
  TREATMENT: 'treatment',
  SCORING: 'scoring',
  FEEDBACK: 'feedback',
}

const { intentParser, isIntentType } = loadTypeScriptModule(
  path.join(root, 'services', 'intent-parser.ts'),
  { '@/constants/vindicate': { CasePhase } },
)

const cases = [
  { input: '什么时候开始疼的？', phase: CasePhase.HISTORY, type: 'ask_history', target: 'hpi_onset' },
  { input: '疼痛是什么性质的？', phase: CasePhase.HISTORY, type: 'ask_history', target: 'hpi_character' },
  { input: '查体：心脏听诊', phase: CasePhase.EXAM, type: 'physical_exam' },
  { input: '开心电图', phase: CasePhase.TESTS, type: 'order_test' },
  { input: '我诊断是心肌梗死', phase: CasePhase.DIAGNOSIS, type: 'mention_diagnosis' },
  { input: '治疗方案是什么', phase: CasePhase.TREATMENT, type: 'mention_treatment' },
  { input: '你好', phase: CasePhase.INTRO, type: 'greeting' },
  { input: '   ', phase: CasePhase.HISTORY, type: 'empty' },
  { input: '患者最近心情怎么样', phase: CasePhase.HISTORY, type: 'unknown' },
]

for (const sample of cases) {
  test(`intent parser maps "${sample.input}" in ${sample.phase}`, () => {
    const intent = intentParser.parse(sample.input, sample.phase)
    assert.equal(intent.type, sample.type)
    if (sample.target) {
      assert.equal(intent.target, sample.target)
    }
  })
}

test('isIntentType accepts known intent labels', () => {
  assert.equal(isIntentType('ask_history'), true)
  assert.equal(isIntentType('not_a_real_intent'), false)
  assert.equal(isIntentType(null), false)
})