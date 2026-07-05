const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTypeScriptModule } = require('./loadTsModule')

const {
  PHASE1_ASTHMA_SECTION_ID,
  buildPageViewerPayload,
  locatorIdsForEvidenceArtifact,
  isPhase1VisualEvidenceSection,
} = loadTypeScriptModule(
  path.join(__dirname, '..', 'services', 'phase1VisualEvidenceService.ts'),
  {
    '@/constants/phase1PageImageAssets': {
      PHASE1_PAGE_IMAGE_ASSETS: { im10_page_33: 1 },
      PHASE1_ASTHMA_PAGE_LABELS: ['33'],
    },
  },
)

test('phase1 visual evidence section is asthma only', () => {
  assert.equal(isPhase1VisualEvidenceSection(PHASE1_ASTHMA_SECTION_ID), true)
  assert.equal(
    isPhase1VisualEvidenceSection('第二篇_呼吸系统疾病__第八章_肺结核'),
    false,
  )
})

test('BDT locator keeps PDF page 64 separate from printed textbook page 33', () => {
  const locatorId = 'loc_ev1_57068078e29b9153d70d'
  const payload = buildPageViewerPayload([locatorId], '33')
  assert.ok(payload, 'expected non-null payload for known BDT locator')
  assert.equal(payload.pageLabel, '33')
  assert.equal(payload.locators[0].pdfPageIndex, 63)
  assert.equal(typeof payload.imageSource, 'number')
  assert.ok(payload.locators.length >= 1)
  const b = payload.locators[0].bboxNorm
  assert.equal(b?.length, 4)
  for (const v of b) {
    assert.ok(v >= 0 && v <= 1, `bboxNorm out of range: ${v}`)
  }
})

test('locatorIdsForEvidenceArtifact uses explicit ids when provided', () => {
  const explicit = ['loc_ev1_57068078e29b9153d70d']
  const ids = locatorIdsForEvidenceArtifact(PHASE1_ASTHMA_SECTION_ID, 'ev1-any', explicit)
  assert.deepEqual(ids, explicit)
})
