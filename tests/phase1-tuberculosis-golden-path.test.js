const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const { loadTypeScriptModule } = require('./loadTsModule')

const ROOT = path.join(__dirname, '..')
const TB_SECTION_ID = '第二篇_呼吸系统疾病__第八章_肺结核'
const DISPLAY_CONTRACT_PATH = path.join(
  ROOT,
  'generated',
  'display_contracts',
  'internal-medicine-10',
  '第二篇_呼吸系统疾病__第八章_肺结核.display_contract.json',
)

const PHASE1_PAGE_IMAGE_MOCKS = {
  '@/constants/phase1PageImageAssets': {
    PHASE1_PAGE_IMAGE_ASSETS: { im10_page_33: 1 },
    PHASE1_ASTHMA_PAGE_LABELS: ['33'],
  },
}

const {
  buildChapterCatalogStudyUnits,
  buildChapterStudyGroups,
  buildChapterStudyUnits,
} = loadTypeScriptModule(path.join(ROOT, 'utils', 'textbookStudy.ts'), PHASE1_PAGE_IMAGE_MOCKS)

const { evidencePageLabel, getSectionDetail } = loadTypeScriptModule(
  path.join(ROOT, 'services', 'textbookService.ts'),
  PHASE1_PAGE_IMAGE_MOCKS,
)

const { isPhase1VisualEvidenceSection } = loadTypeScriptModule(
  path.join(ROOT, 'services', 'phase1VisualEvidenceService.ts'),
  PHASE1_PAGE_IMAGE_MOCKS,
)

const { resolveStudyEvidencePageReference } = loadTypeScriptModule(
  path.join(ROOT, 'utils', 'studyEvidencePageReference.ts'),
  PHASE1_PAGE_IMAGE_MOCKS,
)

const { EV1_DISPLAY_CONTRACT_SECTIONS } = loadTypeScriptModule(
  path.join(ROOT, 'constants', 'ev1DisplayContracts.ts'),
  PHASE1_PAGE_IMAGE_MOCKS,
)

/** Mirrors scripts/export_ev1_display_contracts_ts.py compact node + section shape. */
function compactDisplayNode(node) {
  return {
    id: node.id,
    render_type: node.render_type,
    publication_state: node.publication_state,
    quality_badges: node.quality_badges || [],
    display: node.display || {},
    source_node_ids: node.source_node_ids || [],
    evidence_items: node.evidence_items || [],
    ...(node.merge ? { merge: node.merge } : {}),
    ...(node.group ? { group: node.group } : {}),
  }
}

function pageBoundsFromNodes(nodes) {
  const pages = []
  for (const node of nodes) {
    for (const item of node.evidence_items || []) {
      if (typeof item.page_start === 'number') pages.push(item.page_start)
      if (typeof item.page_end === 'number') pages.push(item.page_end)
    }
  }
  if (pages.length === 0) return [0, 0]
  return [Math.min(...pages), Math.max(...pages)]
}

function systemTitleFromPart(partTitle) {
  return (partTitle || '').replace(/^第[一二三四五六七八九十百零\d]+篇\s*/, '').trim() || partTitle
}

function buildEv1SectionFromDisplayContractPayload(payload, sectionId) {
  const nodes = payload.nodes || []
  const [pageStart, pageEnd] = pageBoundsFromNodes(nodes)
  const partTitle = payload.part_title || ''
  return {
    id: sectionId,
    textbookId: payload.textbook_id,
    textbookTitle: '内科学（第10版）',
    systemTitle: systemTitleFromPart(partTitle),
    partTitle,
    sectionTitle: payload.section_title,
    nodeCount: payload.node_count,
    pageStart,
    pageEnd,
    summary: payload.summary || {},
    nodes: nodes.filter((node) => node && typeof node === 'object').map(compactDisplayNode),
  }
}

function contractNodeIngestionFingerprint(node) {
  return {
    render_type: node.render_type,
    publication_state: node.publication_state,
    display: node.display,
    evidence_artifact_ids: (node.evidence_items || []).map((item) => item.artifact_id),
  }
}

function assertSameStringList(actual, expected, label) {
  assert.equal(actual.length, expected.length, `${label}: length mismatch`)
  for (let index = 0; index < actual.length; index += 1) {
    assert.equal(actual[index], expected[index], `${label}: mismatch at index ${index}`)
  }
}

function assertJsonEqual(actual, expected, label) {
  assert.equal(
    JSON.stringify(actual),
    JSON.stringify(expected),
    `${label}: JSON mismatch`,
  )
}

function findStudyItemsWithTitle(groups, title) {
  const matches = []
  for (const group of groups) {
    for (const item of group.items) {
      if (item.title === title) matches.push(item)
      if (item.children?.length) {
        const nested = findStudyItemsWithTitle([{ items: item.children }], title)
        matches.push(...nested)
      }
    }
  }
  return matches
}

test('tuberculosis golden path: real display contract file matches bundled ingestion fixture', () => {
  assert.ok(fs.existsSync(DISPLAY_CONTRACT_PATH), 'missing tuberculosis display contract artifact')
  const payload = JSON.parse(fs.readFileSync(DISPLAY_CONTRACT_PATH, 'utf8'))
  const fromFile = buildEv1SectionFromDisplayContractPayload(payload, TB_SECTION_ID)
  const embedded = EV1_DISPLAY_CONTRACT_SECTIONS.find((section) => section.id === TB_SECTION_ID)
  assert.ok(embedded, 'embedded EV1 section missing for tuberculosis')

  assert.equal(fromFile.sectionTitle, embedded.sectionTitle)
  assert.equal(fromFile.nodeCount, embedded.nodeCount)
  assert.equal(fromFile.nodes.length, embedded.nodes.length)
  assertSameStringList(
    fromFile.nodes.map((node) => node.id),
    embedded.nodes.map((node) => node.id),
    'display contract node ids',
  )

  for (let index = 0; index < fromFile.nodes.length; index += 1) {
    const fileNode = fromFile.nodes[index]
    const embeddedNode = embedded.nodes[index]
    assert.equal(fileNode.id, embeddedNode.id, `node id mismatch at index ${index}`)
    assertJsonEqual(
      contractNodeIngestionFingerprint(fileNode),
      contractNodeIngestionFingerprint(embeddedNode),
      `node ingestion fingerprint at index ${index} (${fileNode.id})`,
    )
  }
})

test('tuberculosis golden path: app conversion yields hierarchical study structure from real contract', async () => {
  const detail = await getSectionDetail(TB_SECTION_ID)
  assert.ok(detail, 'getSectionDetail returned null')
  assert.ok(detail.nodes.length > 0, 'expected non-empty knowledge nodes')

  const units = buildChapterStudyUnits(detail)
  const catalogUnits = buildChapterCatalogStudyUnits(detail)
  const groups = buildChapterStudyGroups(detail)

  assert.ok(units.length > 0)
  assert.ok(units.length < detail.nodes.length, 'expected catalog/chapter units, not one card per raw node')
  assert.ok(catalogUnits.length > 0, 'expected catalog-addressable units for tuberculosis chapter')

  const flatItemCount = units.reduce((sum, unit) => (
    sum + unit.groups.reduce((inner, group) => inner + group.items.length, 0)
  ), 0)
  assert.ok(flatItemCount > 0)
  assert.ok(
    units.some((unit) => unit.groups.some((group) => group.items.some((item) => item.children?.length))),
    'expected nested children under at least one study group item',
  )

  const classificationMatches = findStudyItemsWithTitle(groups, '结核病的分类标准')
  assert.equal(classificationMatches.length, 1, 'classification axis should appear once in study groups')
  const classification = classificationMatches[0]
  assert.ok(classification.children.length >= 2, 'classification should retain subtype children')

  const axisTitles = (classification.children.find((item) => item.title === '活动性结核病')?.children || [])
    .map((item) => item.title)
  const expectedAxisTitles = [
    '按病变部位分类',
    '按病原学检查结果分类',
    '按耐药状况分类',
    '按既往治疗史分类',
  ]
  assertSameStringList(axisTitles.slice(0, expectedAxisTitles.length), expectedAxisTitles, 'classification axes')

  const siteTitles = (classification.children
    .find((item) => item.title === '活动性结核病')
    ?.children?.find((item) => item.title === '按病变部位分类')
    ?.children || [])
    .map((item) => item.title)
  assertSameStringList(
    siteTitles.slice(0, 2),
    ['原发性肺结核', '血行播散性肺结核'],
    'site classification subtypes',
  )

  const topLevelUnitTitles = units.map((unit) => unit.title)
  const evidenceOnlyFragmentTitles = detail.nodes
    .filter((node) => node.publicationState === 'evidence_only' && node.renderType === 'evidence_only')
    .map((node) => node.title)
    .filter((title) => title && title !== '原文证据')
  for (const fragmentTitle of evidenceOnlyFragmentTitles) {
    assert.equal(
      topLevelUnitTitles.includes(fragmentTitle),
      false,
      `OCR/evidence-only fragment promoted to top-level unit: ${fragmentTitle}`,
    )
  }
})

test('tuberculosis golden path: evidence keeps artifact id and page reference without forged PageViewer locators', async () => {
  const detail = await getSectionDetail(TB_SECTION_ID)
  const classificationNode = detail.nodes.find((node) => node.groupTopic === 'classification')
  assert.ok(classificationNode, 'expected classification grouped node in real contract')

  const sampleArtifactId = classificationNode.evidenceItems[0]?.artifactId
  assert.ok(sampleArtifactId?.startsWith('ev1-'), 'expected ev1 artifact id from contract')

  const groups = buildChapterStudyGroups(detail)
  const classificationItem = findStudyItemsWithTitle(groups, '结核病的分类标准')[0]
  const evidence = classificationItem.evidence.find((item) => item.id === sampleArtifactId)
    || classificationItem.evidence[0]
  assert.ok(evidence?.id?.startsWith('ev1-'))
  assert.ok(evidence?.text?.length > 0)
  assert.ok(evidence?.pageLabel?.length > 0)

  assert.equal(isPhase1VisualEvidenceSection(TB_SECTION_ID), false)

  const resolved = resolveStudyEvidencePageReference(TB_SECTION_ID, evidence)
  assert.equal(resolved.showPageViewer, false)
  assert.equal(resolved.viewerActionLabel, null)
  assert.equal(resolved.locatorIds.length, 0)
  assert.ok(
    resolved.pageReference.includes('教材页') || resolved.pageReference.includes('PDF 页'),
    `expected explicit textbook or PDF page label, got: ${resolved.pageReference}`,
  )
  assert.equal(
    resolved.pageReferenceKind === 'printed' || resolved.pageReferenceKind === 'pdf',
    true,
  )

  const payload = JSON.parse(fs.readFileSync(DISPLAY_CONTRACT_PATH, 'utf8'))
  const rawEvidence = (payload.nodes || [])
    .flatMap((node) => node.evidence_items || [])
    .find((item) => item.artifact_id === evidence.id)
  assert.ok(rawEvidence, 'study evidence artifact must exist in real display contract')
  assert.equal(evidencePageLabel(rawEvidence), evidence.pageLabel.replace(/^p\.?/i, 'p.'))
})