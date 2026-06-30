const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

const moduleCache = new Map()

function loadTypeScriptModule(filePath) {
  const resolved = path.resolve(filePath)
  if (moduleCache.has(resolved)) return moduleCache.get(resolved)

  const source = fs.readFileSync(resolved, 'utf8')
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      esModuleInterop: true,
    },
  }).outputText

  const module = { exports: {} }
  const wrapper = vm.runInNewContext(`(function (require, module, exports) { ${output} })`)
  const localRequire = (id) => {
    if (id.startsWith('@/')) {
      const base = path.join(__dirname, '..', id.slice(2))
      const withTs = `${base}.ts`
      return loadTypeScriptModule(fs.existsSync(withTs) ? withTs : base)
    }
    return require(id)
  }
  wrapper(localRequire, module, module.exports)
  moduleCache.set(resolved, module.exports)
  return module.exports
}

const {
  parseTopicAspect,
  groupNodesIntoTopics,
  buildSubjectKnowledgeTree,
  getAspectSortWeight,
  filterTopicNodes,
  isCrossDiseaseExpansionNode,
  formatSectionUnitTitle,
  extractSectionUnitEntity,
  splitDiseaseGroup,
  deriveSubsectionEntities,
  nodeMatchesSectionUnit,
  nodeMatchesSubsection,
  isChapterLeaf,
  isSectionLeaf,
  getChapterEntryTarget,
  getSectionEntryTarget,
} = loadTypeScriptModule(path.join(__dirname, '..', 'utils', 'knowledgeTree.ts'))

test('parseTopicAspect splits title into topic and aspect', () => {
  const parsed = parseTopicAspect('支气管哮喘的定义', '第四章 支气管哮喘')
  assert.equal(parsed.topic, '支气管哮喘')
  assert.equal(parsed.aspect, '定义')
})

test('groupNodesIntoTopics keeps one disease subsection per chapter', () => {
  const sections = groupNodesIntoTopics([
    { id: '1', title: '支气管哮喘的定义', sub_chapter: '第四章 支气管哮喘', order_num: 0 },
    { id: '2', title: '支气管哮喘的临床表现', sub_chapter: '第四章 支气管哮喘', order_num: 1 },
    { id: '3', title: '支气管哮喘的病因', sub_chapter: '第四章 支气管哮喘', order_num: 2 },
  ], '第四章 支气管哮喘')

  assert.equal(sections.length, 1)
  assert.equal(sections[0].subsections.length, 1)
  assert.equal(sections[0].subsections[0].name, '支气管哮喘')
  assert.equal(sections[0].subsections[0].nodeCount, 3)
})

test('isCrossDiseaseExpansionNode rejects LLM-expanded rhinitis treatment rows', () => {
  const rejected = isCrossDiseaseExpansionNode({
    id: 'x',
    title: '抗IL-5单克隆抗体治疗变应性鼻炎',
    source_span: { parent_entity: '变应性鼻炎' },
  }, '支气管哮喘')
  assert.equal(rejected, true)
})

test('filterTopicNodes drops cross-disease rows and disambiguates generic treatment labels', () => {
  const nodes = filterTopicNodes([
    {
      id: '1',
      title: '支气管哮喘的定义',
      sub_chapter: '第四章 支气管哮喘',
      order_num: 0,
      structured_sections: [{ title: '定义', content: '支气管哮喘的定义：支气管哮喘是一种慢性病' }],
    },
    {
      id: '2',
      title: '抗IL-5单克隆抗体治疗哮喘',
      sub_chapter: '第四章 支气管哮喘',
      order_num: 1,
      structured_sections: [{ title: '治疗方案', content: '抗IL-5单克隆抗体治疗哮喘：抑制嗜酸性粒细胞增多' }],
      source_span: { parent_entity: '哮喘' },
    },
    {
      id: '3',
      title: '抗IL-5单克隆抗体治疗变应性鼻炎',
      sub_chapter: '第四章 支气管哮喘',
      order_num: 2,
      structured_sections: [{ title: '治疗方案', content: '抗IL-5单克隆抗体治疗变应性鼻炎：减少嗜酸性粒细胞' }],
      source_span: { parent_entity: '变应性鼻炎' },
    },
    {
      id: '4',
      title: '吸入型糖皮质激素治疗哮喘',
      sub_chapter: '第四章 支气管哮喘',
      order_num: 3,
      structured_sections: [{ title: '治疗方案', content: '吸入型糖皮质激素治疗哮喘：基础治疗药物' }],
      source_span: { parent_entity: '哮喘' },
    },
  ], '第四章 支气管哮喘', '支气管哮喘')

  assert.equal(nodes.length, 3)
  assert.equal(nodes.find((node) => node.id === '3'), undefined)
  assert.equal(nodes.find((node) => node.id === '2')?.displayAspect, '抗IL-5单克隆抗体治疗哮喘')
  assert.equal(nodes.find((node) => node.id === '4')?.displayAspect, '吸入型糖皮质激素治疗哮喘')
})

test('buildSubjectKnowledgeTree uses catalog skeleton and groups topics', () => {
  const tree = buildSubjectKnowledgeTree([
    {
      id: '1',
      title: '支气管哮喘的定义',
      chapter: '第二篇 呼吸系统疾病',
      sub_chapter: '第四章 支气管哮喘',
      order_num: 0,
    },
  ], [
    {
      chapterTitle: '第二篇 呼吸系统疾病',
      sections: [
        { title: '第三章 慢性阻塞性肺疾病' },
        { title: '第四章 支气管哮喘' },
      ],
    },
  ])

  assert.equal(tree.length, 1)
  assert.equal(tree[0].chapters.length, 2)
  assert.equal(tree[0].chapters[0].hasData, false)
  assert.equal(tree[0].chapters[1].sections[0].subsections[0].name, '支气管哮喘')
})

test('formatSectionUnitTitle and extractSectionUnitEntity parse textbook 节 titles', () => {
  assert.equal(formatSectionUnitTitle('第二节 | 急性白血病'), '第二节　急性白血病')
  assert.equal(extractSectionUnitEntity('第二节 | 急性白血病'), '急性白血病')
  assert.equal(extractSectionUnitEntity('第一节 | 概述'), '概述')
})

test('splitDiseaseGroup and deriveSubsectionEntities split disease groups inside a 节', () => {
  assert.equal(
    JSON.stringify(splitDiseaseGroup('肺炎支原体肺炎、衣原体肺炎与肺军团病')),
    JSON.stringify(['肺炎支原体肺炎', '衣原体肺炎', '肺军团病']),
  )
  assert.equal(
    JSON.stringify(
      deriveSubsectionEntities('第四节 | 肺炎支原体肺炎、衣原体肺炎与肺军团病', '第六章 肺部感染性疾病'),
    ),
    JSON.stringify(['肺炎支原体肺炎', '衣原体肺炎', '肺军团病']),
  )
})

test('buildSubjectKnowledgeTree maps nodes into 节 and disease 小节 for leukemia chapter', () => {
  const tree = buildSubjectKnowledgeTree([
    {
      id: '1',
      title: '白血病的概述',
      chapter: '第六篇 血液系统疾病',
      sub_chapter: '第九章 白血病',
      order_num: 0,
      source_span: { parent_entity: '白血病' },
    },
    {
      id: '2',
      title: '急性白血病的临床表现',
      chapter: '第六篇 血液系统疾病',
      sub_chapter: '第九章 白血病',
      order_num: 1,
      source_span: { parent_entity: '急性白血病' },
    },
    {
      id: '3',
      title: '慢性髓系白血病的治疗',
      chapter: '第六篇 血液系统疾病',
      sub_chapter: '第九章 白血病',
      order_num: 2,
      source_span: { parent_entity: '慢性髓系白血病' },
    },
  ], [
    {
      chapterTitle: '第六篇 血液系统疾病',
      sections: [
        {
          title: '第九章 白血病',
          units: [
            { title: '第一节 | 概述', subsections: [{ title: '白血病' }] },
            { title: '第二节 | 急性白血病', subsections: [{ title: '急性白血病' }] },
            { title: '第三节 | 慢性髓系白血病', subsections: [{ title: '慢性髓系白血病' }] },
            { title: '第四节 | 慢性淋巴细胞白血病', subsections: [{ title: '慢性淋巴细胞白血病' }] },
          ],
        },
      ],
    },
  ])

  const leukemia = tree[0].chapters[0]
  assert.equal(leukemia.name, '第九章 白血病')
  assert.equal(leukemia.sections.length, 4)
  assert.equal(leukemia.sections[0].name, '第一节　概述')
  assert.equal(leukemia.sections[0].subsections[0].name, '白血病')
  assert.equal(leukemia.sections[0].subsections[0].nodeCount, 1)
  assert.equal(leukemia.sections[1].subsections[0].name, '急性白血病')
  assert.equal(leukemia.sections[1].subsections[0].nodeCount, 1)
  assert.equal(leukemia.sections[2].subsections[0].nodeCount, 1)
  assert.equal(leukemia.sections[3].subsections[0].nodeCount, 0)
})

test('buildSubjectKnowledgeTree exposes multiple disease 小节 under one 节', () => {
  const tree = buildSubjectKnowledgeTree([
    {
      id: '1',
      title: '肺炎支原体肺炎的临床表现',
      chapter: '第二篇 呼吸系统疾病',
      sub_chapter: '第六章 肺部感染性疾病',
      order_num: 0,
      source_span: { parent_entity: '肺炎支原体肺炎' },
    },
    {
      id: '2',
      title: '肺炎衣原体肺炎的治疗',
      chapter: '第二篇 呼吸系统疾病',
      sub_chapter: '第六章 肺部感染性疾病',
      order_num: 1,
      source_span: { parent_entity: '肺炎衣原体肺炎' },
    },
  ], [
    {
      chapterTitle: '第二篇 呼吸系统疾病',
      sections: [
        {
          title: '第六章 肺部感染性疾病',
          units: [
            {
              title: '第四节 | 肺炎支原体肺炎、衣原体肺炎与肺军团病',
              subsections: [
                { title: '肺炎支原体肺炎' },
                { title: '衣原体肺炎' },
                { title: '肺军团病' },
              ],
            },
          ],
        },
      ],
    },
  ])

  const section = tree[0].chapters[0].sections[0]
  assert.equal(section.name, '第四节　肺炎支原体肺炎、衣原体肺炎与肺军团病')
  assert.equal(section.subsections.length, 3)
  assert.equal(section.subsections[0].name, '肺炎支原体肺炎')
  assert.equal(section.subsections[0].nodeCount, 1)
  assert.equal(section.subsections[1].name, '衣原体肺炎')
  assert.equal(nodeMatchesSubsection(
    {
      id: 'x',
      title: '肺炎衣原体肺炎的治疗',
      source_span: { parent_entity: '肺炎衣原体肺炎' },
    },
    '第六章 肺部感染性疾病',
    '衣原体肺炎',
  ), true)
})

test('isChapterLeaf and isSectionLeaf adapt navigation depth to catalog shape', () => {
  const asthmaChapter = {
    name: '第四章 支气管哮喘',
    hasCatalogUnits: false,
    hasData: true,
    sections: [{
      name: '支气管哮喘',
      catalogTitle: '第四章 支气管哮喘',
      subsections: [{ name: '支气管哮喘', nodeCount: 3, hasData: true }],
      nodeCount: 3,
      hasData: true,
    }],
  }
  const pneumoniaChapter = {
    name: '第六章 肺部感染性疾病',
    hasCatalogUnits: true,
    hasData: true,
    sections: [{
      name: '第四节　肺炎支原体肺炎、衣原体肺炎与肺军团病',
      catalogTitle: '第四节 | 肺炎支原体肺炎、衣原体肺炎与肺军团病',
      subsections: [
        { name: '肺炎支原体肺炎', nodeCount: 1, hasData: true },
        { name: '衣原体肺炎', nodeCount: 0, hasData: false },
        { name: '肺军团病', nodeCount: 0, hasData: false },
      ],
      nodeCount: 1,
      hasData: true,
    }],
  }

  assert.equal(isChapterLeaf(asthmaChapter), true)
  assert.equal(getChapterEntryTarget(asthmaChapter).subsectionName, '支气管哮喘')
  assert.equal(isChapterLeaf(pneumoniaChapter), false)
  assert.equal(isSectionLeaf(pneumoniaChapter.sections[0]), false)
  assert.equal(getSectionEntryTarget({
    name: '第二节　急性白血病',
    catalogTitle: '第二节 | 急性白血病',
    subsections: [{ name: '急性白血病', nodeCount: 2, hasData: true }],
    nodeCount: 2,
    hasData: true,
  }).subsectionName, '急性白血病')
})

test('nodeMatchesSectionUnit routes overview nodes to 第一节 概述', () => {
  const overviewNode = {
    id: '1',
    title: '白血病的定义',
    source_span: { parent_entity: '白血病' },
  }
  assert.equal(
    nodeMatchesSectionUnit(overviewNode, '第九章 白血病', '第一节 | 概述'),
    true,
  )
  assert.equal(
    nodeMatchesSectionUnit(overviewNode, '第九章 白血病', '第二节 | 急性白血病'),
    false,
  )
})

test('catalog subsections map named pneumonia diseases under a broad bacterial unit', () => {
  const tree = buildSubjectKnowledgeTree([
    {
      id: 'pneumococcus-treatment',
      title: '肺炎链球菌肺炎的治疗',
      chapter: '第二篇 呼吸系统疾病',
      sub_chapter: '第六章 肺部感染性疾病',
      content_class: 'confirmed_disease',
      node_type: 'disease',
      content_status: 'available',
      disease_id: 'pneumococcus',
    },
  ], [{
    chapterTitle: '第二篇 呼吸系统疾病',
    sections: [{
      title: '第六章 肺部感染性疾病',
      units: [{
        title: '第二节 | 细菌性肺炎',
        subsections: [{ title: '肺炎链球菌肺炎' }],
      }],
    }],
  }])

  const subsection = tree[0].chapters[0].sections[0].subsections[0]
  assert.equal(subsection.name, '肺炎链球菌肺炎')
  assert.equal(subsection.nodeCount, 1)
  assert.equal(subsection.target?.disease_id, 'pneumococcus')
})
