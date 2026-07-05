import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import { createRequire } from 'node:module'
import test from 'node:test'

const require = createRequire(import.meta.url)
const { loadTypeScriptModule } = require('./loadTsModule')

const root = process.cwd()
const {
  buildKnowledgeMapRoute,
  buildTextbookSectionRoute,
  buildTextbookUnitRoute,
  chapterHasCatalogOutlineUnits,
  isAllowedMapUnitEntry,
  shouldOpenChapterCatalog,
} = loadTypeScriptModule(path.join(root, 'utils', 'routeBuilders.ts'))

test('legacy detail route files are removed', () => {
  for (const relative of [
    'app/topic.tsx',
    'app/node/[id].tsx',
    'app/knowledge/[id].tsx',
    'app/feynman.tsx',
  ]) {
    assert.equal(fs.existsSync(path.join(root, relative)), false, relative)
  }
})

test('route builders are the only business route constructors', () => {
  const source = fs.readFileSync(path.join(root, 'utils/routeBuilders.ts'), 'utf8')
  assert.match(source, /pathname: '\/disease\/\[id\]'/)
  assert.match(source, /pathname: '\/chapter\/\[id\]'/)
  assert.match(source, /pathname: '\/textbook\/\[sectionId\]'/)
  assert.match(source, /pathname: '\/textbook\/\[sectionId\]\/unit\/\[unitId\]'/)
  assert.match(source, /buildKnowledgeMapRoute/)
  assert.match(source, /content_class === 'confirmed_disease'/)
  assert.match(source, /node\.node_type === 'disease'/)
  assert.match(source, /node\.content_status === 'available'/)
  assert.match(source, /content_class === 'non_disease_knowledge'/)
  assert.match(source, /return null/)
})

test('chapter outline detection keeps 绪论 on chapter catalog instead of first unit', () => {
  assert.equal(chapterHasCatalogOutlineUnits({ units: [{ title: '第一节 | 示例' }] }), true)
  assert.equal(chapterHasCatalogOutlineUnits({ title: '绪论' }), false)
  assert.equal(chapterHasCatalogOutlineUnits({}), false)
})

test('single-section chapters skip chapter catalog and open content directly', () => {
  assert.equal(shouldOpenChapterCatalog(1), false)
  assert.equal(shouldOpenChapterCatalog(16), true)
  assert.equal(shouldOpenChapterCatalog(0), false)
})

test('map unit entry requires explicit via when coming from knowledge map', () => {
  assert.equal(isAllowedMapUnitEntry('map', undefined), false)
  assert.equal(isAllowedMapUnitEntry('map', 'catalog'), true)
  assert.equal(isAllowedMapUnitEntry('map', 'map-inline'), true)
  assert.equal(isAllowedMapUnitEntry('wrong-question', undefined), true)
})

test('textbook route builders carry map origin and target item identity', () => {
  assert.equal(buildKnowledgeMapRoute(), '/(tabs)/learn')

  const sectionRoute = buildTextbookSectionRoute('resp-intro', 'map')
  assert.equal(sectionRoute.pathname, '/textbook/[sectionId]')
  assert.equal(sectionRoute.params.sectionId, 'resp-intro')
  assert.equal(sectionRoute.params.from, 'map')

  const unitRoute = buildTextbookUnitRoute('resp-intro', 'unit-1', { from: 'map' })
  assert.equal(unitRoute.pathname, '/textbook/[sectionId]/unit/[unitId]')
  assert.equal(unitRoute.params.sectionId, 'resp-intro')
  assert.equal(unitRoute.params.unitId, 'unit-1')
  assert.equal(unitRoute.params.from, 'map')

  const wrongQuestionRoute = buildTextbookUnitRoute('resp-intro', 'unit-1', {
    from: 'wrong-question',
    targetItemId: 'item-9',
  })
  assert.equal(wrongQuestionRoute.pathname, '/textbook/[sectionId]/unit/[unitId]')
  assert.equal(wrongQuestionRoute.params.sectionId, 'resp-intro')
  assert.equal(wrongQuestionRoute.params.unitId, 'unit-1')
  assert.equal(wrongQuestionRoute.params.from, 'wrong-question')
  assert.equal(wrongQuestionRoute.params.targetItemId, 'item-9')
})

test('textbook map entry preserves origin through section and unit routes', () => {
  const sectionSource = fs.readFileSync(path.join(root, 'app/textbook/[sectionId].tsx'), 'utf8')
  const unitSource = fs.readFileSync(
    path.join(root, 'app/textbook/[sectionId]/unit/[unitId].tsx'),
    'utf8',
  )
  const mapSource = fs.readFileSync(path.join(root, 'app/map.tsx'), 'utf8')

  assert.match(sectionSource, /buildKnowledgeMapRoute/)
  assert.match(sectionSource, /buildTextbookUnitRoute/)
  assert.match(sectionSource, /fromMap/)
  assert.match(unitSource, /buildTextbookSectionRoute/)
  assert.match(unitSource, /isAllowedMapUnitEntry/)
  assert.match(sectionSource, /via: 'catalog'/)
  assert.match(mapSource, /via: 'map-inline'/)
  assert.match(mapSource, /buildTextbookSectionRoute/)
  assert.match(mapSource, /buildTextbookUnitRoute/)
  assert.match(mapSource, /chapterHasCatalogOutlineUnits/)
  assert.match(mapSource, /openChapterFromMap/)
  assert.match(mapSource, /shouldOpenChapterCatalog/)
  assert.match(mapSource, /router\.push\(buildTextbookSectionRoute/)
  assert.match(mapSource, /router\.push\(buildTextbookUnitRoute/)
  assert.doesNotMatch(mapSource, /router\.replace\(buildTextbookSectionRoute/)
  assert.doesNotMatch(mapSource, /router\.replace\(buildTextbookUnitRoute/)
  assert.match(unitSource, /buildKnowledgeMapRoute/)
  assert.match(unitSource, /from === 'map'/)
  assert.doesNotMatch(mapSource, /进入\$\{catalog\.title\}章节目录/)
  assert.doesNotMatch(mapSource, /enterActionText.*查看目录/s)
})

test('MVP status migration separates node type from content status', () => {
  const source = fs.readFileSync(
    path.join(root, 'supabase/migrations/20260614021344_respiratory_knowledge_mvp_status.sql'),
    'utf8',
  )
  assert.match(source, /ADD COLUMN IF NOT EXISTS node_type/)
  assert.match(source, /ADD COLUMN IF NOT EXISTS content_status/)
  assert.match(source, /'overview'/)
  assert.match(source, /'in_progress'/)
  assert.match(source, /'unavailable'/)
})

test('database migration defines identity constraints and reasoning gate', () => {
  const source = fs.readFileSync(
    path.join(root, 'supabase/migrations/022_disease_detail_convergence.sql'),
    'utf8',
  )
  assert.match(source, /chapter_section_id TEXT PRIMARY KEY/)
  assert.match(source, /UNIQUE \(textbook_series_id, catalog_path\)/)
  assert.match(source, /disease_id TEXT PRIMARY KEY/)
  assert.match(source, /UNIQUE \(source_textbook_series_id, canonical_key\)/)
  assert.match(source, /knowledge_nodes_identity_consistency_check/)
  assert.match(source, /idx_knowledge_nodes_disease_aspect/)
  assert.match(source, /invalid_medical_logic/)
  assert.match(source, /resolution_status <> 'rejected'/)
})

test('wrong-question routes preserve target textbook item identity', () => {
  const homeSource = fs.readFileSync(path.join(root, 'app/(tabs)/index.tsx'), 'utf8')
  const queueSource = fs.readFileSync(path.join(root, 'app/wrong-questions.tsx'), 'utf8')
  const unitSource = fs.readFileSync(
    path.join(root, 'app/textbook/[sectionId]/unit/[unitId].tsx'),
    'utf8',
  )

  assert.match(homeSource, /targetItemId: candidate\.itemId/)
  assert.match(queueSource, /targetItemId: record\.candidate\.itemId/)
  assert.match(unitSource, /targetItemId/)
  assert.match(unitSource, /findTargetItem/)
  assert.match(homeSource, /home-wrong-question-input/)
  assert.match(homeSource, /home-wrong-question-locate-button/)
  assert.match(homeSource, /wrong-question-save-candidate-button/)
  assert.match(homeSource, /wrong-question-open-candidate-button/)
  assert.match(queueSource, /wrong-question-record/)
  assert.match(queueSource, /-reason-\$\{reason\.id\}/)
  assert.match(queueSource, /-open-textbook/)
  assert.match(queueSource, /-toggle-reviewed/)
  assert.match(queueSource, /wrong-question-reviewed-segment/)
  assert.match(unitSource, /wrong-question-target-card/)
  assert.match(unitSource, /wrong-question-target-evidence/)
  assert.match(unitSource, /错题定位目标/)
  assert.match(unitSource, /expandedGroups/)
  assert.match(unitSource, /targetGroupIds/)
  assert.match(unitSource, /accessibilityState=\{\{ expanded \}\}/)
  assert.match(unitSource, /<Text style=\{styles\.itemPage\} numberOfLines=\{1\}>/)
  assert.match(unitSource, /minWidth: 54/)
  assert.match(unitSource, /flexShrink: 0/)
})

test('case training UI exposes current mode boundaries and VINDICATE guide', () => {
  const casesSource = fs.readFileSync(path.join(root, 'app/(tabs)/cases.tsx'), 'utf8')
  const diagnoseSource = fs.readFileSync(path.join(root, 'app/case/[sessionId]/diagnose.tsx'), 'utf8')

  assert.match(casesSource, /case-mode-clinical/)
  assert.match(casesSource, /case-mode-exam/)
  assert.match(casesSource, /case-exam-mode-placeholder/)
  assert.match(casesSource, /不生成模拟真题/)
  assert.match(diagnoseSource, /diagnosis-vindicate-guide/)
  assert.match(diagnoseSource, /VINDICATE_CATEGORIES/)
})
