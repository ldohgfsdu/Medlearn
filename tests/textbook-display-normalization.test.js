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

const { normalizeTextbookDisplayText, isTruncatedText } = loadTypeScriptModule(
  path.join(ROOT, 'utils', 'textbookStudy.ts'),
  PHASE1_PAGE_IMAGE_MOCKS,
)

const { dedupeCompactEvidenceSourceEntries } = loadTypeScriptModule(
  path.join(ROOT, 'utils', 'studyEvidencePageReference.ts'),
  PHASE1_PAGE_IMAGE_MOCKS,
)

// ---------------------------------------------------------------------------
// normalizeTextbookDisplayText — mirrors Python normalize_display_text
// ---------------------------------------------------------------------------

test('normalizeTextbookDisplayText merges CJK-CJK line-wrap space', () => {
  const raw = '气道 炎症是支气管哮喘 的核心机制'
  assert.equal(
    normalizeTextbookDisplayText(raw),
    '气道炎症是支气管哮喘的核心机制',
  )
})

test('normalizeTextbookDisplayText merges CJK-CJK line-wrap newline', () => {
  const raw = '气道\n炎症\n是慢性疾病'
  assert.equal(normalizeTextbookDisplayText(raw), '气道炎症是慢性疾病')
})

test('normalizeTextbookDisplayText preserves paragraph boundary', () => {
  const raw = '哮喘是一种慢性气道炎症性疾病\n\n定义是指可逆性气流受限'
  assert.equal(
    normalizeTextbookDisplayText(raw),
    '哮喘是一种慢性气道炎症性疾病\n\n定义是指可逆性气流受限',
  )
})

test('normalizeTextbookDisplayText preserves English phrase spacing', () => {
  const raw = '支气管哮喘 bronchial asthma 是慢性气道炎症'
  assert.equal(
    normalizeTextbookDisplayText(raw),
    '支气管哮喘 bronchial asthma 是慢性气道炎症',
  )
})

test('normalizeTextbookDisplayText preserves unit spacing but removes digit-CJK space', () => {
  const raw = '口服 10 mg 每次 10 岁以下慎用'
  const result = normalizeTextbookDisplayText(raw)
  assert.ok(result.includes('10 mg'), '10 mg should preserve space')
  assert.ok(result.includes('10岁以下'), '10岁 should not have space')
})

test('normalizeTextbookDisplayText removes spaces before and after Chinese punctuation', () => {
  const raw = '哮喘 ， 是慢性疾病 ； 表现为喘息'
  assert.equal(
    normalizeTextbookDisplayText(raw),
    '哮喘，是慢性疾病；表现为喘息',
  )
})

test('normalizeTextbookDisplayText removes punctuation suffix-only space', () => {
  const raw = '哮喘， 是慢性疾病； 表现为喘息'
  assert.equal(
    normalizeTextbookDisplayText(raw),
    '哮喘，是慢性疾病；表现为喘息',
  )
})

test('normalizeTextbookDisplayText removes bracket spaces', () => {
  const raw = '（ 支气管哮喘 ） 是一种【 慢性疾病 】'
  assert.equal(
    normalizeTextbookDisplayText(raw),
    '（支气管哮喘）是一种【慢性疾病】',
  )
})

test('normalizeTextbookDisplayText removes space after closing bracket', () => {
  const raw = '（支气管哮喘） 是慢性疾病'
  assert.equal(
    normalizeTextbookDisplayText(raw),
    '（支气管哮喘）是慢性疾病',
  )
})

test('normalizeTextbookDisplayText strips zero-width chars', () => {
  const raw = '气道\u200b炎症\u200c\u200d是\u3000疾病\ufeff'
  assert.equal(normalizeTextbookDisplayText(raw), '气道炎症是疾病')
})

test('normalizeTextbookDisplayText preserves double newline across CJK', () => {
  const raw = '第一段结束\n\n第二段开始'
  assert.equal(normalizeTextbookDisplayText(raw), '第一段结束\n\n第二段开始')
})

test('normalizeTextbookDisplayText handles mixed line-wrap and paragraph boundary', () => {
  const raw = '气道 炎症\n是慢性疾病\n\n定义\n是指可逆性气流受限'
  assert.equal(
    normalizeTextbookDisplayText(raw),
    '气道炎症是慢性疾病\n\n定义是指可逆性气流受限',
  )
})

test('normalizeTextbookDisplayText removes CJK-digit space', () => {
  const raw = '剂量 10岁以下禁用'
  assert.equal(normalizeTextbookDisplayText(raw), '剂量10岁以下禁用')
})

test('normalizeTextbookDisplayText removes digit-CJK space', () => {
  const raw = '剂量10 岁以下禁用'
  assert.equal(normalizeTextbookDisplayText(raw), '剂量10岁以下禁用')
})

test('normalizeTextbookDisplayText handles digit newline CJK', () => {
  const raw = '剂量 10\n岁以下禁用'
  assert.equal(normalizeTextbookDisplayText(raw), '剂量10岁以下禁用')
})

test('normalizeTextbookDisplayText preserves English unit spacing', () => {
  const raw = 'FEV1/FVC < 70% 提示气流受限'
  const result = normalizeTextbookDisplayText(raw)
  // English/digit units should keep their internal spacing
  assert.ok(result.includes('FEV1/FVC'))
  assert.ok(result.includes('70%'))
})

test('normalizeTextbookDisplayText handles empty and null', () => {
  assert.equal(normalizeTextbookDisplayText(''), '')
  assert.equal(normalizeTextbookDisplayText(null), '')
  assert.equal(normalizeTextbookDisplayText(undefined), '')
})

test('normalizeTextbookDisplayText is idempotent', () => {
  const raw = '气道 炎症\n是慢性疾病\n\n定义 ， 是指可逆性气流受限'
  const once = normalizeTextbookDisplayText(raw)
  const twice = normalizeTextbookDisplayText(once)
  assert.equal(twice, once)
})

// ---------------------------------------------------------------------------
// isTruncatedText — port of Python is_truncated_sentence
// ---------------------------------------------------------------------------

test('isTruncatedText detects truncation tail markers', () => {
  assert.equal(isTruncatedText('反复发作喘息、气急，伴或不伴胸闷或咳嗽，夜间及凌晨多发'), true)
  assert.equal(isTruncatedText('临床表现为反复发作的喘息、气急、胸闷或咳嗽等症状，常在夜间及凌晨发作或加重，同时伴'), true)
  assert.equal(isTruncatedText('大多数哮喘病人诱导痰中嗜酸性粒细胞计数增高（＞2.5%），且与'), true)
})

test('isTruncatedText returns false for complete sentences', () => {
  assert.equal(isTruncatedText('哮喘是一种以慢性气道炎症为特征的异质性疾病。'), false)
  assert.equal(isTruncatedText('反复发作喘息、气急、胸闷或咳嗽。'), false)
  assert.equal(isTruncatedText('FEV1/FVC < 70%提示气流受限。'), false)
})

test('isTruncatedText returns false for mid-clause punctuation endings', () => {
  assert.equal(isTruncatedText('哮喘的典型症状包括喘息、气急、胸闷或咳嗽，'), false)
  assert.equal(isTruncatedText('分为急性发作期、慢性持续期和临床缓解期：'), false)
})

test('isTruncatedText handles empty and null', () => {
  assert.equal(isTruncatedText(''), false)
  assert.equal(isTruncatedText(null), false)
  assert.equal(isTruncatedText(undefined), false)
  assert.equal(isTruncatedText('   '), false)
})

test('isTruncatedText returns false for sentence-ending brackets', () => {
  assert.equal(isTruncatedText('（见第三章）'), false)
  assert.equal(isTruncatedText('哮喘的核心机制」'), false)
})

// ---------------------------------------------------------------------------
// dedupeCompactEvidenceSourceEntries
// ---------------------------------------------------------------------------

function makeEntry(overrides) {
  return {
    kind: 'page_viewer',
    locatorIds: overrides.locatorIds ?? ['loc-1'],
    pageReference: overrides.pageReference ?? '教材页 31',
    showPageViewer: overrides.showPageViewer ?? true,
    viewerActionLabel: overrides.viewerActionLabel ?? '教材原文 P31',
    viewerPageLabel: overrides.viewerPageLabel ?? '31',
    ...overrides,
  }
}

test('dedupeCompactEvidenceSourceEntries merges entries with same viewerPageLabel', () => {
  const entries = [
    makeEntry({ locatorIds: ['loc-1'] }),
    makeEntry({ locatorIds: ['loc-2'] }),
    makeEntry({ locatorIds: ['loc-3'] }),
  ]
  const result = dedupeCompactEvidenceSourceEntries(entries)
  assert.equal(result.length, 1)
  assert.equal(result[0].locatorIds.length, 3)
  assert.equal(result[0].locatorIds[0], 'loc-1')
  assert.equal(result[0].locatorIds[1], 'loc-2')
  assert.equal(result[0].locatorIds[2], 'loc-3')
})

test('dedupeCompactEvidenceSourceEntries keeps separate entries for different pages', () => {
  const entries = [
    makeEntry({ viewerPageLabel: '31', locatorIds: ['loc-1'] }),
    makeEntry({ viewerPageLabel: '33', locatorIds: ['loc-2'] }),
  ]
  const result = dedupeCompactEvidenceSourceEntries(entries)
  assert.equal(result.length, 2)
})

test('dedupeCompactEvidenceSourceEntries deduplicates locatorIds', () => {
  const entries = [
    makeEntry({ locatorIds: ['loc-1', 'loc-2'] }),
    makeEntry({ locatorIds: ['loc-2', 'loc-3'] }),
  ]
  const result = dedupeCompactEvidenceSourceEntries(entries)
  assert.equal(result.length, 1)
  assert.equal(result[0].locatorIds.length, 3)
  assert.equal(result[0].locatorIds[0], 'loc-1')
  assert.equal(result[0].locatorIds[1], 'loc-2')
  assert.equal(result[0].locatorIds[2], 'loc-3')
})

test('dedupeCompactEvidenceSourceEntries gives page_viewer precedence over page_reference', () => {
  const entries = [
    makeEntry({ kind: 'page_reference', showPageViewer: false, viewerActionLabel: null }),
    makeEntry({ kind: 'page_viewer', showPageViewer: true, viewerActionLabel: '教材原文 P31' }),
  ]
  const result = dedupeCompactEvidenceSourceEntries(entries)
  assert.equal(result.length, 1)
  assert.equal(result[0].kind, 'page_viewer')
  assert.equal(result[0].showPageViewer, true)
  assert.equal(result[0].viewerActionLabel, '教材原文 P31')
})

test('dedupeCompactEvidenceSourceEntries handles empty array', () => {
  const result = dedupeCompactEvidenceSourceEntries([])
  assert.equal(result.length, 0)
})
