const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTypeScriptModule } = require('./loadTsModule')

const ROOT = path.join(__dirname, '..')
const PHASE1_PAGE_IMAGE_MOCKS = {
  '@/constants/phase1PageImageAssets': {
    PHASE1_PAGE_IMAGE_ASSETS: { im10_page_33: 1 },
    PHASE1_ASTHMA_PAGE_LABELS: ['33'],
  },
}

const { PHASE1_ASTHMA_SECTION_ID } = loadTypeScriptModule(
  path.join(ROOT, 'services', 'phase1VisualEvidenceService.ts'),
  PHASE1_PAGE_IMAGE_MOCKS,
)

const {
  bodyMatchesStudyEvidence,
  formatPageViewerActionLabel,
  resolveCompactEvidenceSourceEntry,
  resolveStudyEvidencePageReference,
} = loadTypeScriptModule(
  path.join(ROOT, 'utils', 'studyEvidencePageReference.ts'),
  PHASE1_PAGE_IMAGE_MOCKS,
)

const TB_SECTION_ID = '第二篇_呼吸系统疾病__第八章_肺结核'

test('formatPageViewerActionLabel matches Phase 1 Step 5 copy', () => {
  assert.equal(formatPageViewerActionLabel('33'), '教材原文 P33')
  assert.equal(formatPageViewerActionLabel('p.33'), '教材原文 P33')
  assert.equal(formatPageViewerActionLabel('?'), null)
  assert.equal(formatPageViewerActionLabel(''), null)
})

test('resolveStudyEvidencePageReference exposes viewerActionLabel for PageViewer sections', () => {
  const resolved = resolveStudyEvidencePageReference(PHASE1_ASTHMA_SECTION_ID, {
    id: 'ev1-test',
    pageLabel: 'p.33',
    sourceLocatorIds: ['loc_ev1_57068078e29b9153d70d'],
    pageReferenceKind: 'pdf',
  })
  assert.equal(resolved.showPageViewer, true)
  assert.equal(resolved.viewerActionLabel, '教材原文 P33')
  assert.equal(resolved.pageReference, '教材页 33')
})

test('resolveStudyEvidencePageReference uses locator printed page for PageViewer CTA', () => {
  const resolved = resolveStudyEvidencePageReference(PHASE1_ASTHMA_SECTION_ID, {
    id: 'ev1-test',
    pageLabel: 'p.99',
    sourceLocatorIds: ['loc_ev1_57068078e29b9153d70d'],
    pageReferenceKind: 'pdf',
  })
  assert.equal(resolved.showPageViewer, true)
  assert.equal(resolved.viewerActionLabel, '教材原文 P33')
  assert.equal(resolved.viewerPageLabel, '33')
  assert.equal(resolved.pageReference, '教材页 33')
  assert.equal(resolved.pageReferenceKind, 'printed')
})

test('resolveStudyEvidencePageReference hides PageViewer when locator page is unresolved', () => {
  const resolved = resolveStudyEvidencePageReference(PHASE1_ASTHMA_SECTION_ID, {
    id: 'ev1-missing-page',
    pageLabel: 'p.33',
    sourceLocatorIds: ['loc_ev1_nonexistent'],
    pageReferenceKind: 'pdf',
  })
  assert.equal(resolved.showPageViewer, false)
  assert.equal(resolved.viewerActionLabel, null)
})

test('resolveCompactEvidenceSourceEntry keeps tuberculosis on PDF page fallback without PageViewer', () => {
  const entry = resolveCompactEvidenceSourceEntry(TB_SECTION_ID, {
    id: 'ev1-88756c5327b1427c',
    text: '示例原文',
    pageLabel: 'p.102',
    sourceLocatorIds: [],
    pageReferenceKind: 'pdf',
  })
  assert.equal(entry.kind, 'page_reference')
  assert.equal(entry.showPageViewer, false)
  assert.equal(entry.viewerActionLabel, null)
  assert.equal(entry.pageReference, 'PDF 页 102')
})

test('bodyMatchesStudyEvidence detects identical body and evidence text', () => {
  const evidence = [{
    id: 'ev1-a',
    text: '肺结核分类包括活动性与非活动性。',
    pageLabel: 'p.102',
    pageReferenceKind: 'pdf',
  }]
  assert.equal(
    bodyMatchesStudyEvidence('肺结核分类包括活动性与非活动性。', evidence),
    true,
  )
  assert.equal(
    bodyMatchesStudyEvidence('不同正文', evidence),
    false,
  )
})

test('resolveStudyEvidencePageReference keeps tuberculosis on page-reference fallback without viewerActionLabel', () => {
  const resolved = resolveStudyEvidencePageReference(TB_SECTION_ID, {
    id: 'ev1-88756c5327b1427c',
    pageLabel: 'p.102',
    sourceLocatorIds: [],
    pageReferenceKind: 'pdf',
  })
  assert.equal(resolved.showPageViewer, false)
  assert.equal(resolved.viewerActionLabel, null)
  assert.equal(resolved.pageReference, 'PDF 页 102')
})