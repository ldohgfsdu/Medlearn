const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTypeScriptModule } = require('./loadTsModule')

const ROOT = path.join(__dirname, '..')
const TB_SECTION_ID = '第二篇_呼吸系统疾病__第八章_肺结核'

const PHASE1_PAGE_IMAGE_MOCKS = {
  '@/constants/phase1PageImageAssets': {
    PHASE1_PAGE_IMAGE_ASSETS: { im10_page_31: 1, im10_page_33: 1 },
    PHASE1_ASTHMA_PAGE_LABELS: ['31', '33'],
  },
}

const { PHASE1_ASTHMA_SECTION_ID } = loadTypeScriptModule(
  path.join(ROOT, 'services', 'phase1VisualEvidenceService.ts'),
  PHASE1_PAGE_IMAGE_MOCKS,
)

const { getSectionDetail } = loadTypeScriptModule(
  path.join(ROOT, 'services', 'textbookService.ts'),
  PHASE1_PAGE_IMAGE_MOCKS,
)

const { buildChapterStudyUnits } = loadTypeScriptModule(
  path.join(ROOT, 'utils', 'textbookStudy.ts'),
  PHASE1_PAGE_IMAGE_MOCKS,
)

const {
  bodyMatchesStudyEvidence,
  dedupeCompactEvidenceSourceEntries,
  resolveCompactEvidenceSourceEntries,
  resolveCompactEvidenceSourceEntry,
} = loadTypeScriptModule(
  path.join(ROOT, 'utils', 'studyEvidencePageReference.ts'),
  PHASE1_PAGE_IMAGE_MOCKS,
)

function walkStudyItems(items, visit) {
  for (const item of items) {
    visit(item)
    if (item.children?.length) walkStudyItems(item.children, visit)
  }
}

function collectBodyMatchedItems(unit) {
  const matches = []
  for (const group of unit.groups) {
    walkStudyItems(group.items, (item) => {
      const evidence = item.evidence.filter((entry) => entry.text)
      if (!item.body || evidence.length === 0) return
      if (!bodyMatchesStudyEvidence(item.body, evidence)) return
      matches.push({ item, evidence, groupTitle: group.title, unitTitle: unit.title })
    })
  }
  return matches
}

test('tuberculosis body-matched evidence keeps PDF page fallback without PageViewer', async () => {
  const detail = await getSectionDetail(TB_SECTION_ID)
  const units = buildChapterStudyUnits(detail)
  const bodyMatched = units.flatMap((unit) => collectBodyMatchedItems(unit))

  assert.ok(
    bodyMatched.length > 0,
    'expected at least one tuberculosis study item whose body equals evidence text',
  )

  const withoutViewer = bodyMatched.filter(({ evidence }) => (
    evidence.every((entry) => (
      resolveCompactEvidenceSourceEntry(TB_SECTION_ID, entry).kind === 'page_reference'
    ))
  ))
  assert.ok(
    withoutViewer.length > 0,
    'expected tuberculosis body-matched items to expose page-reference fallback entries',
  )

  for (const { item, evidence } of withoutViewer.slice(0, 5)) {
    const entries = resolveCompactEvidenceSourceEntries(TB_SECTION_ID, evidence, item.pageLabel)
    assert.ok(entries.length > 0, `missing compact fallback for ${item.title}`)
    for (const entry of entries) {
      assert.equal(entry.kind, 'page_reference')
      assert.equal(entry.showPageViewer, false)
      assert.equal(entry.viewerActionLabel, null)
      assert.match(entry.pageReference, /^(教材页|PDF 页) /)
      assert.doesNotMatch(entry.pageReference, /来源页/)
    }
  }
})

test('asthma body-matched evidence with locators keeps PageViewer CTA', async () => {
  const detail = await getSectionDetail(PHASE1_ASTHMA_SECTION_ID)
  const units = buildChapterStudyUnits(detail)
  const bodyMatched = units.flatMap((unit) => collectBodyMatchedItems(unit))

  const withViewer = bodyMatched.filter(({ evidence }) => (
    evidence.some((entry) => (
      resolveCompactEvidenceSourceEntry(PHASE1_ASTHMA_SECTION_ID, entry)?.kind === 'page_viewer'
    ))
  ))
  assert.ok(
    withViewer.length > 0,
    'expected asthma body-matched items with PageViewer compact entries',
  )

  const sample = withViewer[0]
  const entries = resolveCompactEvidenceSourceEntries(
    PHASE1_ASTHMA_SECTION_ID,
    sample.evidence,
    sample.item.pageLabel,
  )
  assert.ok(entries.some((entry) => entry.kind === 'page_viewer'))
  for (const viewerEntry of entries.filter((entry) => entry.kind === 'page_viewer')) {
    assert.match(viewerEntry.viewerActionLabel, /^教材原文 P\d+$/)
    assert.equal(viewerEntry.showPageViewer, true)
  }
})

test('asthma definition and overview body has no abnormal CJK spaces and preserves paragraphs', async () => {
  const detail = await getSectionDetail(PHASE1_ASTHMA_SECTION_ID)
  const units = buildChapterStudyUnits(detail)

  // Find the "定义与概述" group in the asthma unit
  const definitionGroup = units
    .flatMap((unit) => unit.groups)
    .find((group) => group.title === '定义与概述')
  assert.ok(definitionGroup, 'expected a 定义与概述 group in asthma units')

  const definitionItem = definitionGroup.items[0]
  assert.ok(definitionItem, 'expected at least one item in 定义与概述 group')
  assert.ok(definitionItem.body.length > 0, 'definition body must not be empty')

  // No abnormal CJK-CJK spaces (PDF line-wrap artifacts should be merged)
  const cjkSpaceMatches = definitionItem.body.match(/[\u4e00-\u9fff] [\u4e00-\u9fff]/g)
  assert.equal(
    cjkSpaceMatches,
    null,
    `definition body must not contain CJK-CJK spaces, found: ${JSON.stringify(cjkSpaceMatches)}`,
  )

  // No CJK-digit or digit-CJK spaces
  const cjkDigitMatches = definitionItem.body.match(/[\u4e00-\u9fff] \d/g)
  assert.equal(
    cjkDigitMatches,
    null,
    `definition body must not contain CJK-digit spaces, found: ${JSON.stringify(cjkDigitMatches)}`,
  )

  // No spaces before/after Chinese punctuation
  const punctSpaceMatches = definitionItem.body.match(/[ \t][，。；：！？、]|[，。；：！？、][ \t]/g)
  assert.equal(
    punctSpaceMatches,
    null,
    `definition body must not contain punctuation-adjacent spaces, found: ${JSON.stringify(punctSpaceMatches)}`,
  )
})

test('asthma definition compact CTA deduplicates to single P31 with merged locators', async () => {
  const detail = await getSectionDetail(PHASE1_ASTHMA_SECTION_ID)
  const units = buildChapterStudyUnits(detail)

  const definitionGroup = units
    .flatMap((unit) => unit.groups)
    .find((group) => group.title === '定义与概述')
  assert.ok(definitionGroup, 'expected a 定义与概述 group in asthma units')

  const definitionItem = definitionGroup.items[0]
  const evidence = definitionItem.evidence.filter((entry) => entry.text)
  assert.ok(evidence.length > 0, 'definition item must have evidence')

  // Multiple evidence items should resolve to multiple raw entries
  const rawEntries = resolveCompactEvidenceSourceEntries(
    PHASE1_ASTHMA_SECTION_ID,
    evidence,
    definitionItem.pageLabel,
  )
  assert.ok(
    rawEntries.length > 1,
    `expected multiple raw entries before dedup, got ${rawEntries.length}`,
  )

  // After dedup, all P31 entries should merge into one
  const deduped = dedupeCompactEvidenceSourceEntries(rawEntries)

  // Only one entry per page label
  const pageLabels = deduped.map((entry) => entry.viewerPageLabel)
  const uniqueLabels = new Set(pageLabels)
  assert.equal(
    pageLabels.length,
    uniqueLabels.size,
    `deduped entries must have unique page labels, got: ${JSON.stringify(pageLabels)}`,
  )

  // The P31 entry should exist and contain merged locators from all P31 evidence
  const p31Entry = deduped.find((entry) => entry.viewerPageLabel === '31')
  assert.ok(p31Entry, 'expected a P31 entry after dedup')
  assert.equal(p31Entry.kind, 'page_viewer')
  assert.equal(p31Entry.showPageViewer, true)
  assert.match(p31Entry.viewerActionLabel, /^教材原文 P31$/)

  // Merged locator count should be >= 2 (multiple evidence fragments on P31)
  assert.ok(
    p31Entry.locatorIds.length >= 2,
    `P31 entry should merge locators from multiple evidence items, got ${p31Entry.locatorIds.length}`,
  )

  // All locator IDs should be unique
  const locatorSet = new Set(p31Entry.locatorIds)
  assert.equal(
    p31Entry.locatorIds.length,
    locatorSet.size,
    'merged locator IDs must be unique',
  )
})