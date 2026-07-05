const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTypeScriptModule } = require('./loadTsModule')
const { REAL_WRONG_QUESTION_CASES } = require('./fixtures/wrong-question-real-cases')

const ev1DisplayContracts = loadTypeScriptModule(
  path.join(__dirname, '..', 'constants', 'ev1DisplayContracts.ts'),
)

const textbookService = loadTypeScriptModule(
  path.join(__dirname, '..', 'services', 'textbookService.ts'),
  {
    '@/constants/ev1DisplayContracts': ev1DisplayContracts,
    '@/lib/supabase': {
      supabase: {
        from() {
          throw new Error('wrong-question real-case tests must use local EV1 contracts only')
        },
      },
    },
  },
)

const textbookStudy = loadTypeScriptModule(path.join(__dirname, '..', 'utils', 'textbookStudy.ts'))
const {
  locateWrongQuestionCandidates,
} = loadTypeScriptModule(path.join(__dirname, '..', 'utils', 'wrongQuestionIntake.ts'), {
  '@/utils/textbookStudy': textbookStudy,
})

async function localTextbookDetails() {
  const tree = await textbookService.getTextbookTree()
  const details = await Promise.all(
    tree.sections.map((section) => textbookService.getSectionDetail(section.id)),
  )
  return details.filter(Boolean)
}

function assertCandidateMatchesExpected(candidate, expected) {
  assert.equal(candidate.sectionTitle, expected.sectionTitle)
  assert.equal(candidate.unitTitle, expected.unitTitle)
  if (expected.catalogTitle) assert.equal(candidate.catalogTitle, expected.catalogTitle)
  if (expected.groupTitle) assert.equal(candidate.groupTitle, expected.groupTitle)
  assert.equal(candidate.itemTitle, expected.itemTitle)
  assert.equal(candidate.pageLabel, expected.pageLabel)
  assert.equal(typeof candidate.itemId, 'string')
  assert.ok(candidate.itemId.length > 0)

  for (const evidenceTerm of expected.evidenceIncludes) {
    assert.match(candidate.evidenceExcerpt, new RegExp(evidenceTerm))
  }
}

function stemAndOptionsOnly(input) {
  return input.split(/\n正确答案/)[0].trim()
}

for (const realCase of REAL_WRONG_QUESTION_CASES) {
  test(`${realCase.id} reaches expected local textbook evidence`, async () => {
    const candidates = locateWrongQuestionCandidates(realCase.input, await localTextbookDetails())

    if (realCase.expectedUnavailable) {
      assert.equal(candidates.length, 0)
      return
    }

    assert.ok(candidates.length > 0)
    assertCandidateMatchesExpected(candidates[0], realCase.expected)
  })
}

test('rq-resp-001 resolves from stem and options without reference explanation', async () => {
  const realCase = REAL_WRONG_QUESTION_CASES.find((item) => item.id === 'rq-resp-001')
  const candidates = locateWrongQuestionCandidates(stemAndOptionsOnly(realCase.input), await localTextbookDetails())

  assert.ok(candidates.length > 0)
  assertCandidateMatchesExpected(candidates[0], realCase.expected)
})

test('rq-resp-003 resolves viral pneumonia serology from stem and options', async () => {
  const realCase = REAL_WRONG_QUESTION_CASES.find((item) => item.id === 'rq-resp-003')
  const candidates = locateWrongQuestionCandidates(stemAndOptionsOnly(realCase.input), await localTextbookDetails())

  assert.ok(candidates.length > 0)
  assertCandidateMatchesExpected(candidates[0], realCase.expected)
})
