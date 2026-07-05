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

const vindicate = { CasePhase, PHASE_ORDER: Object.values(CasePhase) }
const { intentParser } = loadTypeScriptModule(
  path.join(root, 'services', 'intent-parser.ts'),
  { '@/constants/vindicate': vindicate },
)
const { canPerformAction, canTransition, isValidPhase } = loadTypeScriptModule(
  path.join(root, 'services', 'case-engine.ts'),
  {
    '@/lib/supabase': { supabase: {} },
    '@/constants/vindicate': vindicate,
    './intent-parser': { intentParser },
    './analytics': { trackCaseEvent: async () => {} },
    './case-patient': {
      requestCasePatientResponse: async () => '',
      requestCasePatientTurn: async () => ({ response: '', source: 'preset' }),
    },
  },
)

function makeState(phase) {
  return {
    caseId: 'case-1',
    sessionId: 'session-1',
    currentPhase: phase,
    revealed: {
      historyFields: [],
      examPerformed: [],
      testsOrdered: [],
      testsResultsReleased: [],
    },
    turnCount: 0,
    hintsUsed: 0,
    maxHints: 3,
    startedAt: '2026-06-14T00:00:00.000Z',
  }
}

test('canTransition allows intro to history only', () => {
  const state = makeState(CasePhase.INTRO)
  assert.equal(canTransition(state, CasePhase.HISTORY), true)
  assert.equal(canTransition(state, CasePhase.EXAM), false)
})

test('canTransition allows history to exam and tests', () => {
  const state = makeState(CasePhase.HISTORY)
  assert.equal(canTransition(state, CasePhase.EXAM), true)
  assert.equal(canTransition(state, CasePhase.TESTS), true)
  assert.equal(canTransition(state, CasePhase.DIAGNOSIS), false)
})

test('canPerformAction gates physical exam to exam phase', () => {
  assert.equal(canPerformAction(makeState(CasePhase.EXAM), 'physical_exam'), true)
  assert.equal(canPerformAction(makeState(CasePhase.INTRO), 'physical_exam'), false)
})

test('canPerformAction allows ask_history during intro', () => {
  assert.equal(canPerformAction(makeState(CasePhase.INTRO), 'ask_history'), true)
  assert.equal(canPerformAction(makeState(CasePhase.DIAGNOSIS), 'ask_history'), false)
})

test('isValidPhase recognizes configured phases', () => {
  assert.equal(isValidPhase(CasePhase.HISTORY), true)
  assert.equal(isValidPhase('not-a-phase'), false)
})
