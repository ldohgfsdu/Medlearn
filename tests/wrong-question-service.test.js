const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTypeScriptModule } = require('./loadTsModule')

const storage = new Map()
const AsyncStorage = {
  async getItem(key) {
    return storage.get(key) ?? null
  },
  async setItem(key, value) {
    storage.set(key, value)
  },
}

const service = loadTypeScriptModule(path.join(__dirname, '..', 'services', 'wrongQuestionService.ts'), {
  '@react-native-async-storage/async-storage': AsyncStorage,
  '@/services/textbookService': {
    getTextbookTree: async () => ({ sections: [] }),
    getSectionDetail: async () => null,
  },
  '@/utils/wrongQuestionIntake': {
    locateWrongQuestionCandidates: () => [],
  },
})

function candidate(overrides = {}) {
  return {
    id: 'section-a:unit-a:item-a',
    sectionId: 'section-a',
    sectionTitle: 'Pulmonary Infection',
    partTitle: 'Respiratory',
    unitId: 'unit-a',
    unitTitle: 'Pneumonia',
    groupTitle: 'Treatment',
    itemTitle: 'Treatment',
    pageLabel: 'p.82',
    evidenceExcerpt: 'Grounded textbook evidence.',
    matchedTerms: ['pneumonia', 'treatment'],
    score: 42,
    ...overrides,
  }
}

test('wrong question records save, dedupe by textbook candidate, and stay active', async () => {
  storage.clear()

  const first = await service.saveWrongQuestionRecord('first question', candidate())
  const second = await service.saveWrongQuestionRecord('updated question', candidate())

  assert.equal(first.length, 1)
  assert.equal(second.length, 1)
  assert.equal(second[0].question, 'updated question')
  assert.equal(second[0].reviewedAt, null)
  assert.equal(second[0].candidate.pageLabel, 'p.82')
})

test('wrong question records can move between active and reviewed queues', async () => {
  storage.clear()

  const records = await service.saveWrongQuestionRecord('question', candidate())
  const reviewed = await service.markWrongQuestionReviewed(records[0].id)
  const activeAgain = await service.reactivateWrongQuestionRecord(records[0].id)

  assert.equal(typeof reviewed[0].reviewedAt, 'string')
  assert.equal(activeAgain[0].reviewedAt, null)
  assert.equal(activeAgain[0].candidate.evidenceExcerpt, 'Grounded textbook evidence.')
})

test('wrong question records preserve answer context from learner text', async () => {
  storage.clear()

  const question = [
    '## 题目',
    '患者可能是',
    '',
    '## 正确答案：B',
    '',
    '## 我的答案：A',
  ].join('\n')

  const records = await service.saveWrongQuestionRecord(question, candidate())

  assert.equal(records[0].review.correctAnswer, 'B')
  assert.equal(records[0].review.userAnswer, 'A')
})

test('wrong question mistake reason persists in local storage', async () => {
  storage.clear()

  const records = await service.saveWrongQuestionRecord('question', candidate())
  const tagged = await service.setWrongQuestionMistakeReason(records[0].id, 'missed_clue')
  const loaded = await service.loadWrongQuestionRecords()

  assert.equal(tagged[0].review.mistakeReason, 'missed_clue')
  assert.equal(typeof tagged[0].review.updatedAt, 'string')
  assert.equal(loaded[0].review.mistakeReason, 'missed_clue')
})

test('wrong question record loader filters malformed local records', async () => {
  storage.clear()
  await AsyncStorage.setItem('@medlearn/wrong-question-records', JSON.stringify([
    { id: 'bad', question: 'missing candidate', createdAt: new Date().toISOString() },
    {
      id: 'good',
      question: 'valid',
      candidate: candidate(),
      createdAt: new Date().toISOString(),
      reviewedAt: null,
    },
  ]))

  const records = await service.loadWrongQuestionRecords()

  assert.equal(records.length, 1)
  assert.equal(records[0].id, 'good')
})
