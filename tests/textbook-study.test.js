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
  buildChapterStudyGroups,
  buildChapterStudyUnits,
  buildTextbookKnowledgeMap,
  deriveCatalogSubsectionsFromStudyGroups,
  findChapterStudyUnit,
  stripPartPrefixFromSectionTitle,
} = loadTypeScriptModule(path.join(__dirname, '..', 'utils', 'textbookStudy.ts'))
const {
  evidencePageLabel,
} = loadTypeScriptModule(path.join(__dirname, '..', 'services', 'textbookService.ts'))

function section(overrides) {
  return {
    id: overrides.id,
    sectionTitle: overrides.sectionTitle,
    nodeCount: overrides.nodeCount ?? 10,
    organizedCount: overrides.organizedCount ?? 8,
    evidenceOnlyCount: overrides.evidenceOnlyCount ?? 2,
    mergedCount: 0,
    groupedCount: 0,
    pageRange: overrides.pageRange,
    pageStart: overrides.pageStart,
    pageEnd: overrides.pageEnd,
    partTitle: overrides.partTitle,
    systemTitle: overrides.systemTitle ?? '',
  }
}

function node(overrides) {
  return {
    id: overrides.id,
    title: overrides.title,
    content: overrides.content ?? overrides.title,
    renderType: overrides.renderType ?? 'normal',
    publicationState: overrides.publicationState ?? 'organized',
    qualityBadges: [],
    listItems: overrides.listItems ?? [],
    evidenceItems: overrides.evidenceItems ?? [{
      artifactId: `${overrides.id}-ev`,
      text: overrides.evidenceText ?? overrides.content ?? overrides.title,
      pageStart: overrides.pageStart ?? 77,
      pageEnd: overrides.pageEnd ?? overrides.pageStart ?? 77,
      sourceOrder: overrides.sourceOrder ?? 0,
      pageLabel: overrides.pageLabel ?? 'p.77',
    }],
    evidenceExcerpt: overrides.evidenceText ?? '',
    evidenceFull: overrides.evidenceText ?? overrides.content ?? overrides.title,
    pageLabel: overrides.pageLabel ?? 'p.77',
    sourceHeading: overrides.sourceHeading ?? '第六章 肺部感染性疾病',
    groupTopic: overrides.groupTopic,
    artifactIds: [],
    sourceNodeIds: [overrides.id],
  }
}

function hashString(value) {
  let hash = 0
  for (let index = 0; index < value.length; index += 1) {
    hash = ((hash << 5) - hash + value.charCodeAt(index)) | 0
  }
  return Math.abs(hash).toString(36)
}

test('evidencePageLabel uses the app display page range format', () => {
  assert.equal(evidencePageLabel({ page_start: 83, page_end: 83 }), 'p.83')
  assert.equal(evidencePageLabel({ page_start: 83, page_end: 84 }), 'p.83-84')
  assert.equal(evidencePageLabel({ page_start: null, page_end: null }), 'p.?')
})

test('buildTextbookKnowledgeMap orders parts and chapters by textbook sequence', () => {
  const map = buildTextbookKnowledgeMap({
    textbookId: 'internal-medicine-10',
    textbookTitle: '内科学（第10版）',
    systemTitle: '内科学',
    partTitle: '',
    sections: [
      section({
        id: 'cardio-2',
        partTitle: '第三篇 循环系统疾病',
        sectionTitle: '第二章 心力衰竭',
        pageRange: '160-170',
        pageStart: 160,
        pageEnd: 170,
      }),
      section({
        id: 'resp-6',
        partTitle: '第二篇 呼吸系统疾病',
        sectionTitle: '第六章 肺部感染性疾病',
        pageRange: '77-98',
        pageStart: 77,
        pageEnd: 98,
      }),
      section({
        id: 'resp-1',
        partTitle: '第二篇 呼吸系统疾病',
        sectionTitle: '第一章 总论',
        pageRange: '41-48',
        pageStart: 41,
        pageEnd: 48,
      }),
    ],
  })

  assert.equal(map.title, '内科学')
  assert.equal(map.parts[0].title, '第二篇 呼吸系统疾病')
  assert.equal(map.parts[0].chapters[0].title, '第一章 总论')
  assert.equal(map.parts[0].chapters[1].title, '第六章 肺部感染性疾病')
  assert.equal(map.parts[1].title, '第三篇 循环系统疾病')
})

test('stripPartPrefixFromSectionTitle removes duplicate part text from child labels', () => {
  assert.equal(
    stripPartPrefixFromSectionTitle(
      '第七篇 内分泌和代谢性疾病 第一章 总论',
      '第七篇 内分泌和代谢性疾病',
    ),
    '第一章 总论',
  )
})

test('buildChapterStudyGroups renders grouped classification as one numbered group', () => {
  const groups = buildChapterStudyGroups({
    textbookTitle: '内科学（第10版）',
    systemTitle: '呼吸系统疾病',
    partTitle: '第二篇 呼吸系统疾病',
    section: section({
      id: 'resp-6',
      partTitle: '第二篇 呼吸系统疾病',
      sectionTitle: '第六章 肺部感染性疾病',
      pageRange: '77-98',
      pageStart: 77,
      pageEnd: 98,
    }),
    nodes: [
      node({
        id: 'classification',
        renderType: 'grouped',
        title: '肺炎的分类',
        content: '',
        groupTopic: '分类',
        evidenceItems: [
          {
            artifactId: 'classification-1',
            text: '肺炎可按解剖、病因或患病环境加以分类。',
            pageStart: 77,
            pageEnd: 77,
            sourceOrder: 1,
            pageLabel: 'p.77',
          },
          {
            artifactId: 'classification-2',
            text: '按解剖分类可分为大叶性、小叶性和间质性肺炎。',
            pageStart: 77,
            pageEnd: 77,
            sourceOrder: 2,
            pageLabel: 'p.77',
          },
          {
            artifactId: 'classification-3',
            text: '按患病环境分类可分为社区获得性肺炎和医院获得性肺炎。',
            pageStart: 77,
            pageEnd: 77,
            sourceOrder: 3,
            pageLabel: 'p.77',
          },
        ],
        listItems: [
          { title: '按解剖分类', body: '肺炎按解剖分类如下。', pageLabel: 'p.77', publicationState: 'organized' },
          { title: '大叶性（肺泡性）肺炎', body: '病原体先在肺泡引起炎症。', pageLabel: 'p.77', publicationState: 'organized' },
          { title: '小叶性（支气管性）肺炎', body: '病原体经支气管入侵。', pageLabel: 'p.77', publicationState: 'organized' },
          { title: '间质性肺炎', body: '以肺间质受累为主。', pageLabel: 'p.77', publicationState: 'organized' },
          { title: '按病因分类', body: '肺炎按病因分类如下。', pageLabel: 'p.77', publicationState: 'organized' },
          { title: '细菌性肺炎', body: '如肺炎链球菌等。', pageLabel: 'p.78', publicationState: 'organized' },
          { title: '按患病环境分类', body: '肺炎按患病环境分类如下。', pageLabel: 'p.78', publicationState: 'organized' },
          { title: '社区获得性肺炎', body: '在医院外罹患。', pageLabel: 'p.78', publicationState: 'organized' },
        ],
      }),
    ],
  })

  assert.equal(groups.length, 1)
  assert.equal(groups[0].title, '肺炎')
  assert.equal(groups[0].items.length, 1)
  assert.equal(groups[0].items[0].title, '肺炎的分类')
  assert.match(groups[0].items[0].body, /肺炎可按解剖/)
  assert.equal(groups[0].items[0].children.length, 3)
  assert.equal(groups[0].items[0].children[0].title, '解剖分类')
  assert.equal(groups[0].items[0].children[0].children.length, 3)
  assert.equal(groups[0].items[0].children[0].children[0].title, '大叶性（肺泡性）肺炎')
  assert.match(groups[0].items[0].children[0].children[0].body, /肺泡引起炎症/)
})

test('buildChapterStudyGroups nests tuberculosis classification axes and subtypes', () => {
  const groups = buildChapterStudyGroups({
    textbookTitle: '内科学（第10版）',
    systemTitle: '呼吸系统疾病',
    partTitle: '第二篇 呼吸系统疾病',
    section: section({
      id: 'tb',
      partTitle: '第二篇 呼吸系统疾病',
      sectionTitle: '第八章 肺结核',
      pageRange: '106-109',
      pageStart: 106,
      pageEnd: 109,
    }),
    nodes: [
      node({
        id: 'tb-classification',
        renderType: 'grouped',
        title: '结核病的分类标准',
        content: '根据我国实施的《结核病分类》（WS 196—2017）标准，肺结核可按不同',
        groupTopic: 'classification',
        evidenceItems: [
          {
            artifactId: 'tb-class-intro',
            text: '根据我国实施的《结核病分类》（WS 196—2017）标准，肺结核可按不同',
            pageStart: 106,
            pageEnd: 106,
            sourceOrder: 156,
            pageLabel: 'p.106',
          },
        ],
        listItems: [
          { title: '结核病的分类标准', body: '根据我国实施的《结核病分类》（WS 196—2017）标准，肺结核可按不同', pageLabel: 'p.106', publicationState: 'organized' },
          { title: '结核分枝杆菌潜伏感染者', body: '机体内感染了结核分枝杆菌，但没有发生临床结核病。', pageLabel: 'p.107', publicationState: 'organized' },
          { title: '活动性结核病的定义', body: '具有结核病相关的临床症状和体征。', pageLabel: 'p.107', publicationState: 'organized' },
          { title: '肺结核的病变部位', body: '按照病变部位，分为', pageLabel: 'p.107', publicationState: 'organized' },
          { title: '原发性肺结核', body: '包括原发综合征和胸内淋巴结结核。', pageLabel: 'p.107', publicationState: 'organized' },
          { title: '血行播散性肺结核', body: '含急性、亚急性和慢性血行播散性肺结核。', pageLabel: 'p.108', publicationState: 'organized' },
          { title: '按病原学检查结果分类', body: '分为病原学阳性、病原学阴性和病原学未查肺结核。', pageLabel: 'p.109', publicationState: 'organized' },
          { title: '肺结核的耐药分类', body: '按耐药状况分类，分为敏感肺结核和耐药肺结核。', pageLabel: 'p.109', publicationState: 'organized' },
          { title: '按既往治疗史分类', body: '分为初治肺结核和复治肺结核。', pageLabel: 'p.109', publicationState: 'organized' },
        ],
      }),
    ],
  })

  assert.equal(groups[0].items[0].title, '结核病的分类标准')
  assert.equal(groups[0].items[0].children.length, 2)
  assert.equal(groups[0].items[0].children[0].title, '结核分枝杆菌潜伏感染者')
  assert.equal(groups[0].items[0].children[1].title, '活动性结核病')
  const axisTitles = groups[0].items[0].children[1].children.map((item) => item.title)
  assert.equal(axisTitles.length, 4)
  assert.equal(axisTitles[0], '按病变部位分类')
  assert.equal(axisTitles[1], '按病原学检查结果分类')
  assert.equal(axisTitles[2], '按耐药状况分类')
  assert.equal(axisTitles[3], '按既往治疗史分类')
  const siteTitles = groups[0].items[0].children[1].children[0].children.map((item) => item.title)
  assert.equal(siteTitles.length, 2)
  assert.equal(siteTitles[0], '原发性肺结核')
  assert.equal(siteTitles[1], '血行播散性肺结核')
})

test('buildChapterStudyGroups nests auxiliary exam subitems without promoting them', () => {
  const auxiliaryExam = '\u5b9e\u9a8c\u5ba4\u548c\u5176\u4ed6\u68c0\u67e5'
  const lungFunction = '\u80ba\u529f\u80fd\u68c0\u67e5'
  const bpt = '\u652f\u6c14\u7ba1\u6fc0\u53d1\u8bd5\u9a8c\uff08BPT\uff09'
  const bdt = '\u652f\u6c14\u7ba1\u8212\u5f20\u8bd5\u9a8c\uff08BDT\uff09'
  const pef = '\u547c\u6c14\u5cf0\u6d41\u91cf\uff08PEF\uff09\u53ca\u5176\u53d8\u5f02\u7387\u6d4b\u5b9a'
  const listItems = [
    ['\u75f0\u55dc\u9178\u6027\u7c92\u7ec6\u80de\u8ba1\u6570', '\u5927\u591a\u6570\u54ee\u5598\u75c5\u4eba\u8bf1\u5bfc\u75f0\u4e2d\u55dc\u9178\u6027\u7c92\u7ec6\u80de\u8ba1\u6570\u589e\u9ad8\u3002'],
    ['\u8bf1\u5bfc\u75f0\u55dc\u9178\u6027\u7c92\u7ec6\u80de\u8ba1\u6570', '\u53ef\u4f5c\u4e3a\u8bc4\u4ef7\u54ee\u5598\u6c14\u9053\u708e\u75c7\u6307\u6807\u4e4b\u4e00\u3002'],
    ['\u5916\u5468\u8840\u55dc\u9178\u6027\u7c92\u7ec6\u80de\u8ba1\u6570', '\u5916\u5468\u8840\u55dc\u9178\u6027\u7c92\u7ec6\u80de\u589e\u9ad8\u53ef\u4ee5\u4f5c\u4e3a\u5224\u5b9a\u54ee\u5598\u4e34\u5e8a\u8868\u578b\u7684\u6307\u6807\u3002'],
    ['\u901a\u6c14\u529f\u80fd\u68c0\u6d4b', '\u54ee\u5598\u53d1\u4f5c\u65f6\u5448\u963b\u585e\u6027\u901a\u6c14\u529f\u80fd\u969c\u788d\u8868\u73b0\u3002'],
    ['\u80ba\u529f\u80fd\u6307\u6807\u53d8\u5316', 'FEV1/FVC\uff1c70%\u4e3a\u5224\u65ad\u6c14\u6d41\u53d7\u9650\u7684\u91cd\u8981\u6307\u6807\u3002'],
    ['\u652f\u6c14\u7ba1\u6fc0\u53d1\u8bd5\u9a8c', '\u7528\u4e8e\u6d4b\u5b9a\u6c14\u9053\u53cd\u5e94\u6027\uff0c\u7ed3\u679c\u53ef\u4ee5PD20-FEV1\u6216PC20-FEV1\u8868\u793a\u3002'],
    ['\u539f\u6587\u8bc1\u636e', 'FEV1\u4e0b\u964d\u226520%\uff0c\u5224\u65ad\u7ed3\u679c\u4e3a\u9633\u6027\uff0c\u63d0\u793a\u5b58\u5728\u6c14\u9053\u9ad8\u53cd\u5e94\u6027\u3002', 'evidence_only'],
    ['\u6c14\u9053\u963b\u585e\u7684\u5224\u65ad\u6807\u51c6', '\u5438\u5165\u652f\u6c14\u7ba1\u6269\u5f20\u5242\u540eFEV1\u8f83\u7528\u836f\u524d\u589e\u52a0\u226512%\uff0c\u4e14\u7edd\u5bf9\u503c\u589e\u52a0\u2265200ml\u3002'],
    ['\u547c\u6c14\u5cf0\u6d41\u91cf\u53ca\u5176\u53d8\u5f02\u7387\u6d4b\u5b9a', '\u76d1\u6d4bPEF\u65e5\u95f4\u3001\u5468\u95f4\u53d8\u5f02\u7387\u6709\u52a9\u4e8e\u54ee\u5598\u7684\u8bca\u65ad\u548c\u75c5\u60c5\u8bc4\u4f30\u3002'],
    ['\u652f\u6c14\u7ba1\u8212\u5f20\u8bd5\u9a8c\uff08BDT\uff09', '\u7528\u4e8e\u6d4b\u5b9a\u6c14\u9053\u7684\u53ef\u9006\u6027\u6539\u53d8\u3002', 'evidence_only'],
    ['\u80f8\u90e8X\u7ebf/CT\u68c0\u67e5', '\u54ee\u5598\u53d1\u4f5c\u65f6\u80f8\u90e8X\u7ebf\u53ef\u89c1\u4e24\u80ba\u900f\u4eae\u5ea6\u589e\u52a0\u3002'],
    ['\u7279\u5f02\u6027\u53d8\u5e94\u539f\u68c0\u6d4b', '\u5916\u5468\u8840\u53d8\u5e94\u539f\u7279\u5f02\u6027IgE\u589e\u9ad8\u7ed3\u5408\u75c5\u53f2\u6709\u52a9\u4e8e\u75c5\u56e0\u8bca\u65ad\u3002'],
    ['\u52a8\u8109\u8840\u6c14\u5206\u6790', '\u4e25\u91cd\u54ee\u5598\u53d1\u4f5c\u65f6\u53ef\u51fa\u73b0\u7f3a\u6c27\uff0c\u8fc7\u5ea6\u901a\u6c14\u53ef\u8868\u73b0\u4e3a\u547c\u5438\u6027\u78b1\u4e2d\u6bd2\u3002'],
    ['\u547c\u51fa\u6c14\u4e00\u6c27\u5316\u6c2e\uff08FeNO\uff09\u68c0\u6d4b', 'FeNO\u6d4b\u5b9a\u53ef\u4f5c\u4e3a\u8bc4\u4f30\u54ee\u5598\u63a7\u5236\u6c34\u5e73\u7684\u6307\u6807\u3002'],
  ].map(([title, body, publicationState = 'organized']) => ({
    title,
    body,
    pageLabel: 'p.64',
    publicationState,
  }))
  const groups = buildChapterStudyGroups({
    textbookTitle: '\u5185\u79d1\u5b66\uff08\u7b2c10\u7248\uff09',
    systemTitle: '\u547c\u5438\u7cfb\u7edf\u75be\u75c5',
    partTitle: '\u7b2c\u4e8c\u7bc7 \u547c\u5438\u7cfb\u7edf\u75be\u75c5',
    section: section({
      id: 'asthma',
      partTitle: '\u7b2c\u4e8c\u7bc7 \u547c\u5438\u7cfb\u7edf\u75be\u75c5',
      sectionTitle: '\u7b2c\u56db\u7ae0 \u652f\u6c14\u7ba1\u54ee\u5598',
      pageRange: '63-64',
      pageStart: 63,
      pageEnd: 64,
    }),
    nodes: [
      node({
        id: 'asthma-exam',
        renderType: 'grouped',
        publicationState: 'organized',
        title: auxiliaryExam,
        content: '',
        groupTopic: 'auxiliary_exam',
        sourceHeading: '\u7b2c\u56db\u7ae0 \u652f\u6c14\u7ba1\u54ee\u5598',
        pageLabel: 'p.63-64',
        listItems,
        evidenceItems: listItems.map((item, index) => ({
          artifactId: `asthma-exam-${index}`,
          text: item.body,
          pageStart: 64,
          pageEnd: 64,
          sourceOrder: 60 + index,
          pageLabel: 'p.64',
        })),
      }),
      node({
        id: 'post-exam-clinical',
        title: '\u5178\u578b\u54ee\u5598\u7684\u4e34\u5e8a\u75c7\u72b6\u548c\u4f53\u5f81',
        content: '\u5178\u578b\u54ee\u5598\u7684\u4e34\u5e8a\u75c7\u72b6\u548c\u4f53\u5f81\u4e0d\u5e94\u6298\u5165\u8f85\u52a9\u68c0\u67e5\u3002',
        evidenceText: '\u5178\u578b\u54ee\u5598\u7684\u4e34\u5e8a\u75c7\u72b6\u548c\u4f53\u5f81\u4e0d\u5e94\u6298\u5165\u8f85\u52a9\u68c0\u67e5\u3002',
        sourceOrder: 100,
        sourceHeading: '\u7b2c\u56db\u7ae0 \u652f\u6c14\u7ba1\u54ee\u5598',
        pageLabel: 'p.64',
        pageStart: 64,
      }),
    ],
  })

  const examGroup = groups.find((group) => group.title === auxiliaryExam)
  assert.ok(examGroup)
  assert.equal(examGroup.items.length, 1)
  assert.equal(examGroup.items.some((item) => item.title.includes('\u4e34\u5e8a')), false)
  assert.equal(examGroup.items[0].title, auxiliaryExam)
  assert.equal(JSON.stringify(examGroup.items[0].children.map((item) => item.title)), JSON.stringify([
    '\u75f0\u55dc\u9178\u6027\u7c92\u7ec6\u80de\u8ba1\u6570',
    '\u5916\u5468\u8840\u55dc\u9178\u6027\u7c92\u7ec6\u80de\u8ba1\u6570',
    lungFunction,
    '\u80f8\u90e8X\u7ebf/CT\u68c0\u67e5',
    '\u7279\u5f02\u6027\u53d8\u5e94\u539f\u68c0\u6d4b',
    '\u52a8\u8109\u8840\u6c14\u5206\u6790',
    '\u547c\u51fa\u6c14\u4e00\u6c27\u5316\u6c2e\uff08FeNO\uff09\u68c0\u6d4b',
  ]))

  const lungFunctionItem = examGroup.items[0].children.find((item) => item.title === lungFunction)
  assert.ok(lungFunctionItem)
  assert.equal(JSON.stringify(lungFunctionItem.children.map((item) => item.title)), JSON.stringify([
    '\u901a\u6c14\u529f\u80fd\u68c0\u6d4b',
    bpt,
    bdt,
    pef,
  ]))
  assert.match(lungFunctionItem.children[1].body, /PD20-FEV1/)
  assert.match(lungFunctionItem.children[2].body, /\u589e\u52a0\u2265200ml/)
  assert.match(lungFunctionItem.children[3].body, /PEF/)
  assert.equal(examGroup.items[0].children.some((item) => item.title === bpt || item.title === bdt || item.title === pef), false)
})

test('buildChapterStudyGroups preserves display-contract children and evidence bindings', () => {
  const auxiliaryExam = '\u5b9e\u9a8c\u5ba4\u548c\u5176\u4ed6\u68c0\u67e5'
  const lungFunction = '\u80ba\u529f\u80fd\u68c0\u67e5'
  const bpt = '\u652f\u6c14\u7ba1\u6fc0\u53d1\u8bd5\u9a8c\uff08BPT\uff09'
  const groups = buildChapterStudyGroups({
    textbookTitle: '\u5185\u79d1\u5b66\uff08\u7b2c10\u7248\uff09',
    systemTitle: '\u547c\u5438\u7cfb\u7edf\u75be\u75c5',
    partTitle: '\u7b2c\u4e8c\u7bc7 \u547c\u5438\u7cfb\u7edf\u75be\u75c5',
    section: section({
      id: 'asthma',
      partTitle: '\u7b2c\u4e8c\u7bc7 \u547c\u5438\u7cfb\u7edf\u75be\u75c5',
      sectionTitle: '\u7b2c\u56db\u7ae0 \u652f\u6c14\u7ba1\u54ee\u5598',
      pageRange: '63-64',
      pageStart: 63,
      pageEnd: 64,
    }),
    nodes: [
      node({
        id: 'contract-exam',
        renderType: 'grouped',
        title: auxiliaryExam,
        content: '',
        groupTopic: 'auxiliary_exam',
        pageLabel: 'p.63-64',
        listItems: [
          {
            title: lungFunction,
            body: '',
            pageLabel: 'p.64',
            publicationState: 'organized',
            children: [
              {
                title: '\u901a\u6c14\u529f\u80fd\u68c0\u6d4b',
                body: '\u901a\u6c14\u529f\u80fd\u68c0\u6d4b\u539f\u6587\u6458\u8981\u3002',
                pageLabel: 'p.64',
                publicationState: 'organized',
                evidenceArtifactIds: ['ev-ventilation'],
              },
              {
                title: bpt,
                body: 'BPT \u539f\u6587\u6458\u8981\u3002',
                pageLabel: 'p.64',
                publicationState: 'organized',
                evidenceArtifactIds: ['ev-bpt'],
              },
            ],
          },
        ],
        evidenceItems: [
          {
            artifactId: 'ev-ventilation',
            text: '\u901a\u6c14\u529f\u80fd\u68c0\u6d4b\u539f\u6587\u3002',
            pageStart: 64,
            pageEnd: 64,
            sourceOrder: 70,
            pageLabel: 'p.64',
          },
          {
            artifactId: 'ev-bpt',
            text: 'BPT \u539f\u6587\u3002',
            pageStart: 64,
            pageEnd: 64,
            sourceOrder: 71,
            pageLabel: 'p.64',
          },
        ],
      }),
    ],
  })

  const root = groups[0].items[0]
  assert.equal(root.children.length, 1)
  assert.equal(root.children[0].title, lungFunction)
  assert.equal(root.children[0].evidence.length, 0)
  assert.equal(root.children[0].children[1].title, bpt)
  assert.equal(root.children[0].children[1].evidence[0].id, 'ev-bpt')
})

test('buildChapterStudyGroups gathers treatment rows and preserves evidence-only original text', () => {
  const groups = buildChapterStudyGroups({
    textbookTitle: '内科学（第10版）',
    systemTitle: '呼吸系统疾病',
    partTitle: '第二篇 呼吸系统疾病',
    section: section({
      id: 'resp-6',
      partTitle: '第二篇 呼吸系统疾病',
      sectionTitle: '第六章 肺部感染性疾病',
      pageRange: '77-98',
      pageStart: 77,
      pageEnd: 98,
    }),
    nodes: [
      node({
        id: 'treat-1',
        title: '肺炎的抗感染治疗',
        content: '根据病原学和病情选择治疗方案。',
        sourceOrder: 20,
        sourceHeading: '治疗',
      }),
      node({
        id: 'treat-2',
        title: '肺炎的支持治疗',
        content: '必要时给予氧疗和支持治疗。',
        sourceOrder: 21,
        sourceHeading: '治疗',
      }),
      node({
        id: 'raw',
        title: '重症治疗原文',
        content: '',
        evidenceText: '重症患者应根据病情进行监护和治疗。',
        publicationState: 'evidence_only',
        renderType: 'evidence_only',
        sourceOrder: 22,
        sourceHeading: '治疗',
      }),
    ],
  })

  assert.equal(groups.length, 1)
  assert.equal(groups[0].title, '肺炎')
  assert.equal(groups[0].items.length, 3)
  assert.equal(groups[0].items[2].evidenceOnly, true)
  assert.match(groups[0].items[2].body, /重症患者/)
  assert.equal(groups[0].items[2].evidence[0].pageLabel, 'p.77')
})

test('buildChapterStudyGroups keeps evidence-only treatment under treatment group', () => {
  const groups = buildChapterStudyGroups({
    textbookTitle: '内科学（第10版）',
    systemTitle: '呼吸系统疾病',
    partTitle: '第二篇 呼吸系统疾病',
    section: section({
      id: 'resp-6',
      partTitle: '第二篇 呼吸系统疾病',
      sectionTitle: '第六章 肺部感染性疾病',
      pageRange: '77-98',
      pageStart: 77,
      pageEnd: 98,
    }),
    nodes: [
      node({
        id: 'course',
        title: '肺炎链球菌肺炎自然病程',
        content: '自然病程相关原文。',
        sourceOrder: 100,
        sourceHeading: '自然病程',
      }),
      node({
        id: 'penicillin',
        title: '抗菌药物治疗',
        content: '',
        evidenceText: '抗菌药物治疗 首选青霉素G，用药途径及剂量视病情轻重及有无并发症而定。',
        publicationState: 'evidence_only',
        renderType: 'grouped',
        groupTopic: 'treatment',
        sourceOrder: 101,
        sourceHeading: '第六章 肺部感染性疾病',
        pageLabel: 'p.83',
        pageStart: 83,
        listItems: [
          {
            title: '抗菌药物治疗',
            body: '抗菌药物治疗 首选青霉素G，用药途径及剂量视病情轻重及有无并发症而定。',
            pageLabel: 'p.83',
            publicationState: 'evidence_only',
          },
        ],
      }),
    ],
  })

  const treatmentGroup = groups.find((group) => group.title === '治疗')
  assert.ok(treatmentGroup)
  assert.equal(treatmentGroup.items[0].title, '抗菌药物治疗')
  assert.equal(treatmentGroup.items[0].evidenceOnly, true)
  assert.equal(groups.some((group) =>
    group.title === '自然病程' &&
    group.items.some((item) => item.title === '抗菌药物治疗')
  ), false)
})

test('buildChapterStudyGroups labels generic source evidence groups as original evidence', () => {
  const originalEvidence = '\u539f\u6587\u8bc1\u636e'
  const groups = buildChapterStudyGroups({
    textbookTitle: '\u5185\u79d1\u5b66\uff08\u7b2c10\u7248\uff09',
    systemTitle: '\u547c\u5438\u7cfb\u7edf\u75be\u75c5',
    partTitle: '\u7b2c\u4e8c\u7bc7 \u547c\u5438\u7cfb\u7edf\u75be\u75c5',
    section: section({
      id: 'resp-6',
      partTitle: '\u7b2c\u4e8c\u7bc7 \u547c\u5438\u7cfb\u7edf\u75be\u75c5',
      sectionTitle: '\u7b2c\u516d\u7ae0 \u80ba\u90e8\u611f\u67d3\u6027\u75be\u75c5',
      pageRange: '77-98',
      pageStart: 77,
      pageEnd: 98,
    }),
    nodes: [
      node({
        id: 'source-evidence',
        title: originalEvidence,
        content: '',
        evidenceText: '\u7b2c\u4e00\u6bb5\u539f\u6587\u3002\n\n\u7b2c\u4e8c\u6bb5\u539f\u6587\u3002',
        publicationState: 'evidence_only',
        renderType: 'grouped',
        groupTopic: 'source_evidence',
        sourceHeading: '\u4e34\u5e8a\u8868\u73b0',
        sourceOrder: 20,
        pageLabel: 'p.10',
        pageStart: 10,
        listItems: [
          {
            title: originalEvidence,
            body: '\u7b2c\u4e00\u6bb5\u539f\u6587\u3002\u7b2c\u4e8c\u6bb5\u539f\u6587\u3002',
            pageLabel: 'p.10',
            publicationState: 'evidence_only',
          },
        ],
      }),
    ],
  })

  assert.equal(groups.length, 1)
  assert.equal(groups[0].title, originalEvidence)
  assert.equal(groups[0].items[0].evidenceOnly, true)
})

test('buildChapterStudyGroups preserves evidence-only title and infers treatment group', () => {
  const respiratoryPart = '\u7b2c\u4e8c\u7bc7 \u547c\u5438\u7cfb\u7edf\u75be\u75c5'
  const pulmonaryInfection = '\u7b2c\u516d\u7ae0 \u80ba\u90e8\u611f\u67d3\u6027\u75be\u75c5'
  const treatment = '\u6cbb\u7597'
  const antibacterialTreatment = '\u6297\u83cc\u836f\u7269\u6cbb\u7597'
  const groups = buildChapterStudyGroups({
    textbookTitle: '\u5185\u79d1\u5b66\uff08\u7b2c10\u7248\uff09',
    systemTitle: '\u547c\u5438\u7cfb\u7edf\u75be\u75c5',
    partTitle: respiratoryPart,
    section: section({
      id: 'resp-6',
      partTitle: respiratoryPart,
      sectionTitle: pulmonaryInfection,
      pageRange: '77-98',
      pageStart: 77,
      pageEnd: 98,
    }),
    nodes: [
      node({
        id: 'penicillin-source',
        title: antibacterialTreatment,
        content: '',
        evidenceText: `${antibacterialTreatment} \u9996\u9009\u9752\u9709\u7d20G\uff0c\u7528\u836f\u9014\u5f84\u53ca\u5242\u91cf\u89c6\u75c5\u60c5\u8f7b\u91cd\u53ca\u6709\u65e0\u5e76\u53d1\u75c7\u800c\u5b9a\u3002`,
        publicationState: 'evidence_only',
        renderType: 'evidence_only',
        sourceOrder: 230,
        sourceHeading: pulmonaryInfection,
        pageLabel: 'p.83',
        pageStart: 83,
      }),
    ],
  })

  const treatmentGroup = groups.find((group) => group.title === treatment)
  assert.ok(treatmentGroup)
  assert.equal(treatmentGroup.items[0].title, antibacterialTreatment)
  assert.equal(treatmentGroup.items[0].pageLabel, 'p.83')
  assert.equal(treatmentGroup.items[0].evidenceOnly, true)
})

test('buildChapterStudyGroups keeps different diseases in separate study groups', () => {
  const groups = buildChapterStudyGroups({
    textbookTitle: '内科学（第10版）',
    systemTitle: '呼吸系统疾病',
    partTitle: '第二篇 呼吸系统疾病',
    section: section({
      id: 'resp-6',
      partTitle: '第二篇 呼吸系统疾病',
      sectionTitle: '第六章 肺部感染性疾病',
      pageRange: '77-98',
      pageStart: 77,
      pageEnd: 98,
    }),
    nodes: [
      node({
        id: 'staph-definition',
        title: '葡萄球菌肺炎的定义',
        evidenceText: '葡萄球菌肺炎为葡萄球菌引起的急性肺部感染。',
        sourceOrder: 30,
      }),
      node({
        id: 'viral-definition',
        title: '病毒性肺炎的定义',
        evidenceText: '病毒性肺炎为病毒感染引起的肺部炎症。',
        sourceOrder: 60,
      }),
    ],
  })

  assert.equal(groups.length, 2)
  assert.equal(groups[0].title, '葡萄球菌肺炎')
  assert.equal(groups[1].title, '病毒性肺炎')
  assert.equal(groups[0].items[0].title, '定义与概述')
  assert.equal(groups[1].items[0].title, '定义与概述')
})

test('buildChapterStudyGroups does not inherit a previous topic for standalone disease titles', () => {
  const groups = buildChapterStudyGroups({
    textbookTitle: '内科学（第10版）',
    systemTitle: '呼吸系统疾病',
    partTitle: '第二篇 呼吸系统疾病',
    section: section({
      id: 'resp-6',
      partTitle: '第二篇 呼吸系统疾病',
      sectionTitle: '第六章 肺部感染性疾病',
      pageRange: '77-98',
      pageStart: 77,
      pageEnd: 98,
    }),
    nodes: [
      node({
        id: 'pneumonia-definition',
        title: '肺炎的定义',
        evidenceText: '肺炎指终末气道、肺泡和肺间质的炎症。',
        sourceOrder: 1,
      }),
      node({
        id: 'viral-pneumonia',
        title: '病毒性肺炎',
        evidenceText: '病毒性肺炎如冠状病毒、腺病毒、呼吸道合胞病毒等。',
        sourceOrder: 2,
      }),
      node({
        id: 'viral-treatment',
        title: '治疗',
        evidenceText: '病毒性肺炎治疗应依据教材原文。',
        sourceOrder: 3,
        sourceHeading: '治疗',
      }),
    ],
  })

  assert.equal(groups.length, 2)
  assert.equal(groups[0].title, '肺炎')
  assert.equal(groups[1].title, '病毒性肺炎')
  assert.equal(groups[1].items.length, 2)
})

test('buildChapterStudyGroups treats chapter-title topics as fallback, not a large mixed bucket', () => {
  const groups = buildChapterStudyGroups({
    textbookTitle: '内科学（第10版）',
    systemTitle: '呼吸系统疾病',
    partTitle: '第二篇 呼吸系统疾病',
    section: section({
      id: 'resp-6',
      partTitle: '第二篇 呼吸系统疾病',
      sectionTitle: '第六章 肺部感染性疾病',
      pageRange: '77-98',
      pageStart: 77,
      pageEnd: 98,
    }),
    nodes: [
      node({
        id: 'cap-definition',
        title: '社区获得性肺炎',
        evidenceText: '社区获得性肺炎为医院外罹患的感染性肺实质炎症。',
        sourceOrder: 10,
      }),
      node({
        id: 'chapter-generic-treatment',
        title: '肺部感染性疾病的治疗',
        evidenceText: '治疗内容仍应归入当前教材小节。',
        sourceOrder: 11,
      }),
    ],
  })

  assert.equal(groups.length, 1)
  assert.equal(groups[0].title, '社区获得性肺炎')
  assert.equal(groups[0].items.length, 2)
})

test('buildChapterStudyGroups stitches adjacent evidence fragments without inventing text', () => {
  const groups = buildChapterStudyGroups({
    textbookTitle: '内科学（第10版）',
    systemTitle: '呼吸系统疾病',
    partTitle: '第二篇 呼吸系统疾病',
    section: section({
      id: 'resp-6',
      partTitle: '第二篇 呼吸系统疾病',
      sectionTitle: '第六章 肺部感染性疾病',
      pageRange: '77-98',
      pageStart: 77,
      pageEnd: 98,
    }),
    nodes: [
      node({
        id: 'hap-1',
        title: 'HAP的定义',
        content: '整理短句一',
        evidenceText: 'HAP指病人住院期间没有接受有创机械通气，且入院≥48小时',
        sourceOrder: 10,
      }),
      node({
        id: 'hap-2',
        title: 'HAP的定义',
        content: '整理短句二',
        evidenceText: '后发生的肺炎。',
        sourceOrder: 11,
      }),
    ],
  })

  assert.equal(groups[0].items.length, 1)
  assert.match(groups[0].items[0].body, /入院≥48小时 后发生的肺炎。/)
  assert.equal(groups[0].items[0].evidence.length, 2)
})

test('buildChapterStudyGroups normalizes combined page labels into one range', () => {
  const groups = buildChapterStudyGroups({
    textbookTitle: 'Internal Medicine',
    systemTitle: 'Cardiology',
    partTitle: 'Cardiology',
    section: section({
      id: 'cardio-3',
      partTitle: 'Cardiology',
      sectionTitle: 'Chapter 3',
      pageRange: '226-249',
      pageStart: 226,
      pageEnd: 249,
    }),
    nodes: [
      node({
        id: 'ecg-1',
        title: 'ECG',
        content: 'First point.',
        pageStart: 226,
        pageLabel: 'p.226',
        sourceOrder: 1,
      }),
      node({
        id: 'ecg-2',
        title: 'ECG',
        content: 'Later point.',
        pageStart: 248,
        pageEnd: 249,
        pageLabel: 'p.248-249',
        sourceOrder: 2,
      }),
    ],
  })

  assert.equal(groups[0].pageLabel, 'p.226-249')
})

test('buildChapterStudyUnits exposes chapter topics as separate addressable units', () => {
  const detail = {
    textbookTitle: 'Internal Medicine',
    systemTitle: 'Respiratory',
    partTitle: 'Respiratory',
    section: section({
      id: 'resp-6',
      partTitle: 'Respiratory',
      sectionTitle: 'Chapter 6',
      pageRange: '77-98',
      pageStart: 77,
      pageEnd: 98,
    }),
    nodes: [
      node({
        id: 'cap-overview',
        title: 'CAP',
        evidenceText: 'CAP source text.',
        sourceOrder: 1,
        sourceHeading: 'Chapter 6',
      }),
      node({
        id: 'cap-treatment',
        title: 'CAP',
        evidenceText: 'CAP treatment source text.',
        sourceOrder: 2,
        sourceHeading: 'Chapter 6',
      }),
      node({
        id: 'hap-overview',
        title: 'HAP',
        evidenceText: 'HAP source text.',
        sourceOrder: 20,
        sourceHeading: 'Chapter 6',
      }),
    ],
  }

  const units = buildChapterStudyUnits(detail)

  assert.equal(units.length, 2)
  assert.equal(units[0].title, 'CAP')
  assert.equal(units[0].itemCount, 2)
  assert.equal(units[1].title, 'HAP')
  assert.equal(units[1].itemCount, 1)
  assert.equal(findChapterStudyUnit(detail, units[1].id)?.title, 'HAP')
})

test('buildChapterStudyUnits splits oversized fallback units into readable chunks', () => {
  const detail = {
    textbookTitle: 'Internal Medicine',
    systemTitle: 'Cardiology',
    partTitle: 'Cardiology',
    section: section({
      id: 'cardio-4',
      partTitle: 'Cardiology',
      sectionTitle: 'Chapter 4',
      pageRange: '258-287',
      pageStart: 258,
      pageEnd: 287,
    }),
    nodes: Array.from({ length: 42 }, (_, index) => node({
      id: `minoca-${index}`,
      title: 'MINOCA',
      content: `Source grounded item ${index + 1}.`,
      evidenceText: `Original evidence ${index + 1}.`,
      pageStart: 258 + Math.floor(index / 12),
      pageLabel: `p.${258 + Math.floor(index / 12)}`,
      sourceOrder: index,
      sourceHeading: 'Chapter 4',
    })),
  }

  const units = buildChapterStudyUnits(detail)

  assert.equal(units.length, 2)
  assert.equal(units[0].title, 'MINOCA')
  assert.equal(units[0].itemCount, 24)
  assert.equal(units[1].title, 'MINOCA')
  assert.equal(units[1].itemCount, 18)
  assert.equal(findChapterStudyUnit(detail, units[1].id)?.itemCount, 18)
})

test('buildChapterStudyUnits exposes single-disease textbook chapters as one chapter unit', () => {
  const asthmaChapter = '\u7b2c\u56db\u7ae0 \u652f\u6c14\u7ba1\u54ee\u5598'
  const detail = {
    textbookTitle: '\u5185\u79d1\u5b66\uff08\u7b2c10\u7248\uff09',
    systemTitle: '\u547c\u5438\u7cfb\u7edf\u75be\u75c5',
    partTitle: '\u7b2c\u4e8c\u7bc7 \u547c\u5438\u7cfb\u7edf\u75be\u75c5',
    section: section({
      id: 'asthma',
      partTitle: '\u7b2c\u4e8c\u7bc7 \u547c\u5438\u7cfb\u7edf\u75be\u75c5',
      sectionTitle: asthmaChapter,
      pageRange: '62-70',
      pageStart: 62,
      pageEnd: 70,
    }),
    nodes: [
      node({
        id: 'asthma-definition',
        title: '\u652f\u6c14\u7ba1\u54ee\u5598\u7684\u5b9a\u4e49',
        evidenceText: '\u54ee\u5598\u662f\u4e00\u79cd\u4ee5\u6162\u6027\u6c14\u9053\u708e\u75c7\u548c\u6c14\u9053\u9ad8\u53cd\u5e94\u6027\u4e3a\u7279\u5f81\u7684\u75be\u75c5\u3002',
        sourceOrder: 1,
        sourceHeading: asthmaChapter,
        pageLabel: 'p.62',
        pageStart: 62,
      }),
      node({
        id: 'asthma-exam',
        title: '\u5b9e\u9a8c\u5ba4\u548c\u5176\u4ed6\u68c0\u67e5',
        evidenceText: '\u652f\u6c14\u7ba1\u8212\u5f20\u8bd5\u9a8c\u53ef\u7528\u4e8e\u6d4b\u5b9a\u6c14\u9053\u53ef\u9006\u6027\u6539\u53d8\u3002',
        groupTopic: 'auxiliary_exam',
        sourceOrder: 60,
        sourceHeading: asthmaChapter,
        pageLabel: 'p.64',
        pageStart: 64,
      }),
    ],
  }

  const units = buildChapterStudyUnits(detail)

  assert.equal(units.length, 1)
  assert.equal(units[0].title, '\u652f\u6c14\u7ba1\u54ee\u5598')
  assert.equal(units[0].pageLabel, 'p.62-64')
  assert.equal(JSON.stringify(units[0].groups.map((group) => group.title)), JSON.stringify([
    '\u5b9a\u4e49\u4e0e\u6982\u8ff0',
    '\u5b9e\u9a8c\u5ba4\u548c\u5176\u4ed6\u68c0\u67e5',
  ]))
})

test('chapter-level textbook units render each source evidence artifact once', () => {
  const asthmaChapter = '\u7b2c\u56db\u7ae0 \u652f\u6c14\u7ba1\u54ee\u5598'
  const repeatedEvidence = {
    artifactId: 'shared-asthma-ev',
    text: '\u3010\u6d41\u884c\u75c5\u5b66\u3011 \u54ee\u5598\u662f\u4e16\u754c\u4e0a\u6700\u5e38\u89c1\u7684\u6162\u6027\u75be\u75c5\u4e4b\u4e00\u3002',
    pageStart: 62,
    pageEnd: 62,
    sourceOrder: 3,
    pageLabel: '62',
  }
  const detail = {
    textbookTitle: '\u5185\u79d1\u5b66\uff08\u7b2c10\u7248\uff09',
    systemTitle: '\u547c\u5438\u7cfb\u7edf\u75be\u75c5',
    partTitle: '\u7b2c\u4e8c\u7bc7 \u547c\u5438\u7cfb\u7edf\u75be\u75c5',
    section: section({
      id: 'asthma-dedup',
      partTitle: '\u7b2c\u4e8c\u7bc7 \u547c\u5438\u7cfb\u7edf\u75be\u75c5',
      sectionTitle: asthmaChapter,
      pageRange: '62-70',
      pageStart: 62,
      pageEnd: 70,
    }),
    nodes: [
      node({
        id: 'asthma-epidemiology-a',
        title: '\u54ee\u5598\u7684\u6d41\u884c\u75c5\u5b66\u7279\u5f81',
        sourceHeading: asthmaChapter,
        evidenceItems: [repeatedEvidence],
        pageLabel: 'p.62',
        pageStart: 62,
      }),
      node({
        id: 'asthma-epidemiology-b',
        title: '\u539f\u6587\u8bc1\u636e',
        sourceHeading: asthmaChapter,
        evidenceItems: [repeatedEvidence],
        pageLabel: 'p.62',
        pageStart: 62,
      }),
    ],
  }

  const [unit] = buildChapterStudyUnits(detail)
  const evidenceIds = unit.groups.flatMap((group) => (
    group.items.flatMap((item) => item.evidence.map((evidence) => evidence.id))
  ))

  assert.equal(unit.itemCount, 1)
  assert.equal(unit.groups[0].title, '\u6d41\u884c\u75c5\u5b66')
  assert.equal(JSON.stringify(evidenceIds), JSON.stringify(['shared-asthma-ev']))
  assert.equal(unit.groups[0].items[0].pageLabel, 'p.62')
})

test('chapter-level textbook units keep asthma source aspects in textbook order', () => {
  const asthmaChapter = '\u7b2c\u56db\u7ae0 \u652f\u6c14\u7ba1\u54ee\u5598'
  const detail = {
    textbookTitle: '\u5185\u79d1\u5b66\uff08\u7b2c10\u7248\uff09',
    systemTitle: '\u547c\u5438\u7cfb\u7edf\u75be\u75c5',
    partTitle: '\u7b2c\u4e8c\u7bc7 \u547c\u5438\u7cfb\u7edf\u75be\u75c5',
    section: section({
      id: 'asthma-source-order',
      partTitle: '\u7b2c\u4e8c\u7bc7 \u547c\u5438\u7cfb\u7edf\u75be\u75c5',
      sectionTitle: asthmaChapter,
      pageRange: '62-70',
      pageStart: 62,
      pageEnd: 70,
    }),
    nodes: [
      node({
        id: 'asthma-exam',
        title: '\u5b9e\u9a8c\u5ba4\u548c\u5176\u4ed6\u68c0\u67e5',
        groupTopic: 'auxiliary_exam',
        evidenceText: '\u8bf1\u5bfc\u75f0\u55dc\u9178\u6027\u7c92\u7ec6\u80de\u8ba1\u6570\u589e\u9ad8\u3002',
        sourceOrder: 60,
        sourceHeading: asthmaChapter,
        pageLabel: 'p.63',
        pageStart: 63,
      }),
      node({
        id: 'asthma-diagnosis',
        title: '\u53ef\u53d8\u6c14\u6d41\u53d7\u9650\u7684\u5ba2\u89c2\u68c0\u67e5',
        evidenceText: '\u652f\u6c14\u7ba1\u8212\u5f20\u8bd5\u9a8c\u9633\u6027\u3002',
        sourceOrder: 89,
        sourceHeading: asthmaChapter,
        pageLabel: 'p.64',
        pageStart: 64,
      }),
      node({
        id: 'asthma-variant-treatment',
        title: '\u54b3\u55fd\u53d8\u5f02\u6027\u54ee\u5598\u548c\u80f8\u95f7\u53d8\u5f02\u6027\u54ee\u5598\u7684\u6cbb\u7597\u539f\u5219',
        evidenceText: '\u54b3\u55fd\u53d8\u5f02\u6027\u54ee\u5598\u548c\u80f8\u95f7\u53d8\u5f02\u6027\u54ee\u5598\u7684\u6cbb\u7597\u539f\u5219\u4e0e\u5178\u578b\u54ee\u5598\u76f8\u540c\u3002',
        sourceOrder: 168,
        sourceHeading: asthmaChapter,
        pageLabel: 'p.68',
        pageStart: 68,
      }),
      node({
        id: 'asthma-education',
        title: '\u54ee\u5598\u75c5\u4eba\u7684\u6559\u80b2\u4e0e\u7ba1\u7406',
        evidenceText: '\u3010\u54ee\u5598\u7684\u6559\u80b2\u4e0e\u7ba1\u7406\u3011 \u54ee\u5598\u75c5\u4eba\u7684\u6559\u80b2\u4e0e\u7ba1\u7406\u662f\u63d0\u9ad8\u7597\u6548\u7684\u91cd\u8981\u5185\u5bb9\u3002',
        sourceOrder: 172,
        sourceHeading: asthmaChapter,
        pageLabel: 'p.69',
        pageStart: 69,
      }),
      node({
        id: 'asthma-long-term-treatment-table',
        title: '\u54ee\u5598\u75c5\u4eba\u957f\u671f\uff08\u9636\u68af\u5f0f\uff09\u6cbb\u7597\u65b9\u6848',
        evidenceText: '\u88682-4-3 \u54ee\u5598\u75c5\u4eba\u957f\u671f\uff08\u9636\u68af\u5f0f\uff09\u6cbb\u7597\u65b9\u6848\u3002',
        sourceOrder: 249,
        sourceHeading: asthmaChapter,
        pageLabel: 'p.69',
        pageStart: 69,
      }),
      node({
        id: 'asthma-prognosis',
        title: '\u9884\u540e',
        evidenceText: '\u3010\u9884\u540e\u3011 \u901a\u8fc7\u957f\u671f\u89c4\u8303\u5316\u6cbb\u7597\uff0c\u513f\u7ae5\u54ee\u5598\u4e34\u5e8a\u63a7\u5236\u7387\u53ef\u8fbe95%\u3002',
        sourceOrder: 272,
        sourceHeading: asthmaChapter,
        pageLabel: 'p.70',
        pageStart: 70,
      }),
    ],
  }

  const [unit] = buildChapterStudyUnits(detail)
  const groupTitles = unit.groups.map((group) => group.title)
  const treatment = unit.groups.find((group) => group.title === '\u6cbb\u7597')
  const education = unit.groups.find((group) => group.title === '\u6559\u80b2\u4e0e\u7ba1\u7406')

  assert.equal(JSON.stringify(groupTitles), JSON.stringify([
    '\u5b9e\u9a8c\u5ba4\u548c\u5176\u4ed6\u68c0\u67e5',
    '\u8bca\u65ad\u4e0e\u9274\u522b\u8bca\u65ad',
    '\u6cbb\u7597',
    '\u6559\u80b2\u4e0e\u7ba1\u7406',
    '\u9884\u540e',
  ]))
  assert.ok(treatment)
  assert.match(treatment.items.map((item) => item.title).join('|'), /\u6cbb\u7597\u539f\u5219/)
  assert.match(treatment.items.map((item) => item.title).join('|'), /\u6cbb\u7597\u65b9\u6848/)
  assert.ok(education)
  assert.equal(education.items.length, 1)
})

test('chapter-level textbook units preserve structured asthma auxiliary exam items', () => {
  const asthmaChapter = '第四章 哮喘结构测试'
  const evidenceItems = [
    { artifactId: 'sputum-a', text: '大多数哮喘病人诱导痰中嗜酸性粒细胞计数增高（＞2.5%）', pageStart: 63, pageEnd: 63, sourceOrder: 60, pageLabel: 'p.63' },
    { artifactId: 'sputum-b', text: '诱导痰嗜酸性粒细胞计数可作为评价哮喘气道炎症指标之一', pageStart: 63, pageEnd: 63, sourceOrder: 61, pageLabel: 'p.63' },
    { artifactId: 'blood-a', text: '部分哮喘病人外周血嗜酸性粒细胞计数增高', pageStart: 63, pageEnd: 63, sourceOrder: 62, pageLabel: 'p.63' },
    { artifactId: 'vent-a', text: '哮喘发作时呈阻塞性通气功能障碍表现，用力肺活量（FVC）正常或下降', pageStart: 64, pageEnd: 64, sourceOrder: 64, pageLabel: 'p.64' },
    { artifactId: 'bpt-a', text: '2. 支气管激发试验（BPT） 用于测定气道反应性。常用吸入激发剂为醋甲胆碱和组胺。', pageStart: 64, pageEnd: 64, sourceOrder: 68, pageLabel: 'p.64' },
    { artifactId: 'bdt-a', text: '3. 支气管舒张试验（BDT） 用于测定气道的可逆性改变。', pageStart: 64, pageEnd: 64, sourceOrder: 76, pageLabel: 'p.64' },
    { artifactId: 'pef-a', text: '哮喘发作时PEF下降。监测PEF日间、周间变异率有助于哮喘的诊断和病情评估。', pageStart: 64, pageEnd: 64, sourceOrder: 72, pageLabel: 'p.64' },
    { artifactId: 'xray-a', text: '哮喘发作时胸部X线可见两肺透亮度增加，呈过度通气状态', pageStart: 64, pageEnd: 64, sourceOrder: 76, pageLabel: 'p.64' },
    { artifactId: 'allergen-a', text: '（五）特异性变应原检测 外周血变应原特异性IgE增高结合病史有助于病因诊断', pageStart: 64, pageEnd: 64, sourceOrder: 78, pageLabel: 'p.64' },
    { artifactId: 'abg-a', text: '（六）动脉血气分析 严重哮喘发作时可出现缺氧。', pageStart: 64, pageEnd: 64, sourceOrder: 80, pageLabel: 'p.64' },
    { artifactId: 'feno-a', text: 'FeNO测定可作为评估哮喘控制水平的指标，可用于预判', pageStart: 64, pageEnd: 64, sourceOrder: 83, pageLabel: 'p.64' },
  ]
  const detail = {
    textbookTitle: 'Internal Medicine',
    systemTitle: 'Respiratory',
    partTitle: '第二篇 呼吸系统疾病',
    section: section({
      id: 'asthma',
      partTitle: '第二篇 呼吸系统疾病',
      sectionTitle: asthmaChapter,
      pageRange: '900-901',
      pageStart: 900,
      pageEnd: 901,
    }),
    nodes: [
      node({
        id: 'asthma-exam',
        title: '实验室和其他检查',
        groupTopic: 'auxiliary_exam',
        renderType: 'grouped',
        pageLabel: 'p.63-64',
        sourceHeading: asthmaChapter,
        evidenceItems,
        listItems: [
          { title: '痰嗜酸性粒细胞计数', body: '大多数哮喘病人诱导痰中嗜酸性粒细胞计数增高', pageLabel: 'p.63', publicationState: 'organized', evidenceArtifactIds: ['sputum-a', 'sputum-b'] },
          { title: '外周血嗜酸性粒细胞计数', body: '部分哮喘病人外周血嗜酸性粒细胞计数增高', pageLabel: 'p.63', publicationState: 'organized', evidenceArtifactIds: ['blood-a'] },
          { title: '肺功能检查', body: '', pageLabel: 'p.64', publicationState: 'organized', evidenceArtifactIds: [] },
          { title: '胸部X线/CT检查', body: '哮喘发作时胸部X线可见两肺透亮度增加', pageLabel: 'p.64', publicationState: 'organized', evidenceArtifactIds: ['xray-a'] },
          { title: '特异性变应原检测', body: '外周血变应原特异性IgE增高结合病史有助于病因诊断', pageLabel: 'p.64', publicationState: 'organized', evidenceArtifactIds: ['allergen-a'] },
          { title: '动脉血气分析', body: '严重哮喘发作时可出现缺氧', pageLabel: 'p.64', publicationState: 'organized', evidenceArtifactIds: ['abg-a'] },
          { title: '呼出气一氧化氮（FeNO）检测', body: 'FeNO测定可作为评估哮喘控制水平的指标', pageLabel: 'p.64', publicationState: 'organized', evidenceArtifactIds: ['feno-a'] },
        ],
      }),
    ],
  }

  const [unit] = buildChapterStudyUnits(detail)
  const exam = unit.groups.find((group) => group.title === '实验室和其他检查')
  const pulmonary = exam.items.find((item) => item.title === '肺功能检查')

  assert.ok(exam)
  assert.equal(JSON.stringify(exam.items.map((item) => item.title)), JSON.stringify([
    '痰嗜酸性粒细胞计数',
    '外周血嗜酸性粒细胞计数',
    '肺功能检查',
    '胸部X线/CT检查',
    '特异性变应原检测',
    '动脉血气分析',
    '呼出气一氧化氮（FeNO）检测',
  ]))
  assert.ok(pulmonary)
  assert.equal(JSON.stringify(pulmonary.children.map((child) => child.title)), JSON.stringify([
    '通气功能检测',
    '支气管激发试验（BPT）',
    '支气管舒张试验（BDT）',
    '呼气峰流量（PEF）及其变异率测定',
  ]))
})

test('buildChapterStudyUnits uses textbook catalog units for pulmonary infection chapter', () => {
  const detail = {
    textbookTitle: 'Internal Medicine',
    systemTitle: 'Respiratory',
    partTitle: '第二篇 呼吸系统疾病',
    section: section({
      id: 'resp-6',
      partTitle: '第二篇 呼吸系统疾病',
      sectionTitle: '第六章 肺部感染性疾病',
      pageRange: '77-98',
      pageStart: 77,
      pageEnd: 98,
    }),
    nodes: [
      node({
        id: 'overview',
        title: '肺炎的定义',
        evidenceText: '肺炎指终末气道、肺泡和肺间质的炎症。',
        pageStart: 77,
        pageLabel: 'p.77',
        sourceOrder: 0,
      }),
      node({
        id: 'pneumococcus',
        title: '肺炎链球菌肺炎的病原体',
        evidenceText: '肺炎链球菌肺炎是由肺炎链球菌引起的肺炎。',
        pageStart: 81,
        pageLabel: 'p.81',
        sourceOrder: 119,
      }),
      node({
        id: 'viral',
        title: '病毒性肺炎的定义',
        evidenceText: '病毒性肺炎由病毒侵入呼吸道上皮及肺泡上皮细胞引起。',
        pageStart: 84,
        pageLabel: 'p.84',
        sourceOrder: 199,
      }),
      node({
        id: 'mycoplasma',
        title: '肺炎支原体肺炎',
        evidenceText: '肺炎支原体肺炎由肺炎支原体引起。',
        pageStart: 91,
        pageLabel: 'p.91',
        sourceOrder: 351,
      }),
      node({
        id: 'fungal',
        title: '肺真菌病的病因',
        evidenceText: '肺真菌病有增多的趋势。',
        pageStart: 94,
        pageLabel: 'p.94',
        sourceOrder: 441,
      }),
    ],
  }

  const units = buildChapterStudyUnits(detail)

  assert.equal(units.length, 5)
  assert.equal(
    JSON.stringify(units.map((unit) => unit.title)),
    JSON.stringify([
      '第一节 肺炎概述',
      '第二节 细菌性肺炎',
      '第三节 病毒性肺炎',
      '第四节 肺炎支原体肺炎、衣原体肺炎与肺军团病',
      '第五节 肺真菌病',
    ]),
  )
  assert.equal(units[1].groups[0].title, '肺炎链球菌肺炎')
})

test('buildChapterStudyUnits splits oversized pulmonary catalog units by evidence groups', () => {
  const catalogTitle = '\u7b2c\u4e00\u8282 \u80ba\u708e\u6982\u8ff0'
  const topics = ['CAP', 'HAP', 'VAP', 'ABPA']
  const detail = {
    textbookTitle: 'Internal Medicine',
    systemTitle: 'Respiratory',
    partTitle: '\u7b2c\u4e8c\u7bc7 \u547c\u5438\u7cfb\u7edf\u75be\u75c5',
    section: section({
      id: 'resp-6',
      partTitle: '\u7b2c\u4e8c\u7bc7 \u547c\u5438\u7cfb\u7edf\u75be\u75c5',
      sectionTitle: '\u7b2c\u516d\u7ae0 \u80ba\u90e8\u611f\u67d3\u6027\u75be\u75c5',
      pageRange: '77-98',
      pageStart: 77,
      pageEnd: 98,
    }),
    nodes: Array.from({ length: 40 }, (_, index) => {
      const topic = topics[Math.floor(index / 10)]
      return node({
        id: `pulmonary-overview-${index}`,
        title: topic,
        evidenceText: `${topic} source evidence ${index + 1}.`,
        pageStart: 77 + Math.floor(index / 16),
        pageLabel: `p.${77 + Math.floor(index / 16)}`,
        sourceOrder: index,
        sourceHeading: '\u7b2c\u516d\u7ae0 \u80ba\u90e8\u611f\u67d3\u6027\u75be\u75c5',
      })
    }),
  }

  const units = buildChapterStudyUnits(detail)

  assert.equal(units.length, 4)
  assert.equal(
    JSON.stringify(units.map((unit) => unit.title)),
    JSON.stringify(topics.map((topic) => `${catalogTitle} · ${topic}`)),
  )
  assert.equal(JSON.stringify(units.map((unit) => unit.itemCount)), JSON.stringify([10, 10, 10, 10]))
  assert.ok(units.every((unit) => unit.itemCount <= 36))
  assert.equal(findChapterStudyUnit(detail, units[2].id)?.title, `${catalogTitle} · VAP`)

  const legacyUnitId = `unit-1-${hashString(catalogTitle)}`
  const legacyUnit = findChapterStudyUnit(detail, legacyUnitId)
  assert.equal(legacyUnit?.title, catalogTitle)
  assert.equal(legacyUnit?.itemCount, 40)
  assert.equal(legacyUnit?.groups.length, 4)
})

test('buildChapterStudyUnits folds noisy pulmonary catalog group titles into nearby study units', () => {
  const catalogTitle = '\u7b2c\u56db\u8282 \u80ba\u708e\u652f\u539f\u4f53\u80ba\u708e\u3001\u8863\u539f\u4f53\u80ba\u708e\u4e0e\u80ba\u519b\u56e2\u75c5'
  const sectionTitle = '\u7b2c\u516d\u7ae0 \u80ba\u90e8\u611f\u67d3\u6027\u75be\u75c5'
  const topicRuns = [
    ['ECMO\u6a21\u5f0f\u9009\u62e9', 2],
    ['\u80ba\u708e\u652f\u539f\u4f53\u80ba\u708e', 15],
    ['\u75c5\u56e0\u548c', 2],
    ['\u80ba\u708e', 2],
    ['\u8863\u539f\u4f53\u80ba\u708e', 15],
    ['SARS\u75c5\u6bd2\u4e0e\u80ba\u6ce1\u4e0a\u76ae\u7ec6\u80de\u7ed3\u5408\u5bfc\u81f4\u80ba\u708e', 2],
    ['RBD', 2],
    ['\u6cbb\u7597', 4],
  ]
  let sourceOrder = 351
  const detail = {
    textbookTitle: 'Internal Medicine',
    systemTitle: 'Respiratory',
    partTitle: '\u7b2c\u4e8c\u7bc7 \u547c\u5438\u7cfb\u7edf\u75be\u75c5',
    section: section({
      id: 'resp-6',
      partTitle: '\u7b2c\u4e8c\u7bc7 \u547c\u5438\u7cfb\u7edf\u75be\u75c5',
      sectionTitle,
      pageRange: '77-98',
      pageStart: 77,
      pageEnd: 98,
    }),
    nodes: topicRuns.flatMap(([topic, count]) => (
      Array.from({ length: count }, (_, index) => {
        sourceOrder += 1
        return node({
          id: `pulmonary-noisy-${topic}-${index}`,
          title: topic,
          evidenceText: `${topic} source evidence ${index + 1}.`,
          groupTopic: topic === '\u6cbb\u7597' ? 'treatment' : undefined,
          publicationState: topic === '\u6cbb\u7597' ? 'evidence_only' : 'organized',
          renderType: topic === '\u6cbb\u7597' ? 'evidence_only' : 'normal',
          pageStart: 91,
          pageLabel: 'p.91',
          sourceOrder,
          sourceHeading: sectionTitle,
        })
      })
    )),
  }

  const units = buildChapterStudyUnits(detail)
  const unitTitles = units.map((unit) => unit.title)

  assert.equal(JSON.stringify(unitTitles), JSON.stringify([
    `${catalogTitle} · \u80ba\u708e\u652f\u539f\u4f53\u80ba\u708e`,
    `${catalogTitle} · \u8863\u539f\u4f53\u80ba\u708e`,
    `${catalogTitle} · \u6cbb\u7597`,
  ]))
  assert.equal(units[0].itemCount, 21)
  assert.equal(units[1].itemCount, 19)
  assert.ok(unitTitles.every((title) => !/ECMO|RBD|\u75c5\u56e0\u548c|SARS|\u00b7 \u80ba\u708e$/u.test(title)))
})

test('buildChapterStudyUnits chunks oversized pulmonary catalog study groups', () => {
  const catalogTitle = '\u7b2c\u56db\u8282 \u80ba\u708e\u652f\u539f\u4f53\u80ba\u708e\u3001\u8863\u539f\u4f53\u80ba\u708e\u4e0e\u80ba\u519b\u56e2\u75c5'
  const sectionTitle = '\u7b2c\u516d\u7ae0 \u80ba\u90e8\u611f\u67d3\u6027\u75be\u75c5'
  const detail = {
    textbookTitle: 'Internal Medicine',
    systemTitle: 'Respiratory',
    partTitle: '\u7b2c\u4e8c\u7bc7 \u547c\u5438\u7cfb\u7edf\u75be\u75c5',
    section: section({
      id: 'resp-6',
      partTitle: '\u7b2c\u4e8c\u7bc7 \u547c\u5438\u7cfb\u7edf\u75be\u75c5',
      sectionTitle,
      pageRange: '77-98',
      pageStart: 77,
      pageEnd: 98,
    }),
    nodes: [
      ...Array.from({ length: 5 }, (_, index) => node({
        id: `mycoplasma-${index}`,
        title: '\u80ba\u708e\u652f\u539f\u4f53\u80ba\u708e',
        evidenceText: `mycoplasma source evidence ${index + 1}.`,
        pageStart: 91,
        pageLabel: 'p.91',
        sourceOrder: 351 + index,
        sourceHeading: sectionTitle,
      })),
      ...Array.from({ length: 50 }, (_, index) => node({
        id: `treatment-${index}`,
        title: '\u6cbb\u7597',
        evidenceText: `treatment source evidence ${index + 1}.`,
        groupTopic: 'treatment',
        publicationState: 'evidence_only',
        renderType: 'evidence_only',
        pageStart: 92 + Math.floor(index / 25),
        pageLabel: `p.${92 + Math.floor(index / 25)}`,
        sourceOrder: 400 + index,
        sourceHeading: sectionTitle,
      })),
    ],
  }

  const units = buildChapterStudyUnits(detail)

  assert.equal(JSON.stringify(units.map((unit) => unit.itemCount)), JSON.stringify([5, 24, 24, 2]))
  assert.ok(units.every((unit) => unit.itemCount <= 36))
  assert.equal(units[1].title, `${catalogTitle} · \u6cbb\u7597`)
  assert.equal(units[2].title, `${catalogTitle} · \u6cbb\u7597`)
})

test('deriveCatalogSubsectionsFromStudyGroups expands redundant fungal catalog subsection from evidence groups', () => {
  const subsections = deriveCatalogSubsectionsFromStudyGroups(
    '第五节 | 肺真菌病',
    [{ title: '肺真菌病' }],
    {
      id: 'unit-fungal',
      title: '第五节 肺真菌病',
      pageLabel: 'p.94-98',
      itemCount: 10,
      evidenceOnlyCount: 0,
      groups: [
        { id: 'overview', title: '肺真菌病', pageLabel: 'p.94', items: [{}] },
        { id: 'candida', title: '肺念珠菌病', pageLabel: 'p.94', items: [{}] },
        { id: 'aspergillus', title: '肺曲霉病', pageLabel: 'p.95', items: [{}] },
        { id: 'ipa', title: '侵袭性肺曲霉病', pageLabel: 'p.95', items: [{}] },
        { id: 'crypto', title: '肺隐球菌病', pageLabel: 'p.97', items: [{}] },
        { id: 'pcp', title: '肺孢子菌肺炎', pageLabel: 'p.97', items: [{}] },
        { id: 'pal', title: 'PAL', pageLabel: 'p.94', items: [{}] },
        { id: 'diagnosis', title: '肺部感染性疾病的诊断方法', pageLabel: 'p.94', items: [{}] },
        { id: 'abpa', title: 'ABPA', pageLabel: 'p.98', items: [{}] },
      ],
    },
  )

  assert.deepEqual(subsections.map((item) => item.title), [
    '肺真菌病',
    '肺念珠菌病',
    '肺曲霉病',
    '侵袭性肺曲霉病',
    '肺隐球菌病',
    '肺孢子菌肺炎',
  ])
})

test('buildChapterStudyGroups removes leading source aspect brackets from display body', () => {
  const groups = buildChapterStudyGroups({
    textbookTitle: 'Internal Medicine',
    systemTitle: 'Respiratory',
    partTitle: 'Respiratory',
    section: section({
      id: 'resp-6',
      partTitle: 'Respiratory',
      sectionTitle: 'Chapter 6',
      pageRange: '77-98',
      pageStart: 77,
      pageEnd: 98,
    }),
    nodes: [
      node({
        id: 'pathology',
        title: 'Pathology',
        evidenceText: '\u3010\u75c5\u56e0\u3001\u53d1\u75c5\u673a\u5236\u548c\u75c5\u7406\u3011 Normal body text.',
        sourceOrder: 1,
        sourceHeading: 'Chapter 6',
      }),
    ],
  })

  assert.equal(groups[0].items[0].body, 'Normal body text.')
  assert.match(groups[0].items[0].evidence[0].text, /^\u3010/)
})
