const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

function loadTypeScriptModule(filePath, mocks = {}) {
  const source = fs.readFileSync(filePath, 'utf8')
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      esModuleInterop: true,
    },
  }).outputText

  const module = { exports: {} }
  const localRequire = (request) => {
    if (Object.prototype.hasOwnProperty.call(mocks, request)) return mocks[request]
    return require(request)
  }
  const wrapper = vm.runInNewContext(`(function (require, module, exports) { ${output} })`)
  wrapper(localRequire, module, module.exports)
  return module.exports
}

const root = path.resolve(__dirname, '..')
const structuredContent = loadTypeScriptModule(
  path.join(root, 'utils', 'structuredContent.ts')
)
const { buildKnowledgeOutline } = loadTypeScriptModule(
  path.join(root, 'utils', 'knowledgeOutline.ts'),
  { './structuredContent': structuredContent }
)

test('composite textbook sections retain subtopic hierarchy', () => {
  const content = `
    农药中毒包括多种毒物，处理原则不能混用。
    一、急性有机磷杀虫药中毒
    有机磷抑制胆碱酯酶，可导致胆碱能危象。
    【病因】常见于生产暴露、喷洒污染和误服。
    【临床表现】主要表现为毒蕈碱样、烟碱样和中枢神经系统症状。
    【治疗】应尽快去污，按病情使用阿托品和胆碱酯酶复活剂。
    二、急性百草枯中毒
    百草枯中毒以进行性肺损伤为突出表现。
    【病因和发病机制】氧自由基损伤可导致多器官功能障碍。
    【临床表现】数日至两周可出现进行性肺纤维化和呼吸衰竭。
    【治疗】目前无特效解毒药，应尽早清除毒物并进行器官支持。
    三、氨基甲酸酯类杀虫剂中毒
    该类毒物可逆性抑制胆碱酯酶。
    【病因】常见于生产、使用暴露或误服。
    【临床表现】表现与有机磷中毒相似，但病程通常更短。
    【治疗】去污并按胆碱能症状使用阿托品。
    四、灭鼠药中毒
    不同灭鼠药的中毒机制和解毒剂差异明显。
    【病因】可由误食、投毒、二次中毒或职业暴露引起。
    【治疗】先稳定气道、呼吸和循环，再根据毒物使用特效解毒剂。
  `

  const outline = buildKnowledgeOutline(content)

  assert.equal(outline.grouped, true)
  assert.equal(
    outline.groups.map((group) => group.title).join('|'),
    ['急性有机磷杀虫药中毒', '急性百草枯中毒', '氨基甲酸酯类杀虫剂中毒', '灭鼠药中毒'].join('|')
  )
  assert.equal(
    outline.groups[0].sections.map((section) => section.title).join('|'),
    ['核心概念', '病因', '临床表现', '治疗'].join('|')
  )
  assert.equal(
    outline.groups[1].sections.map((section) => section.title).join('|'),
    ['核心概念', '病因与机制', '临床表现', '治疗'].join('|')
  )
  assert.ok(outline.groups.every((group) => (
    group.sections.every((section) => (
      section.digest.length > 0
      && section.digest.length <= 4
      && section.digest.every((point) => point.length <= 79)
    ))
  )))
})

test('duplicate section titles merge only inside the same topic', () => {
  const outline = buildKnowledgeOutline('普通疾病内容', [
    { title: '病因', content: '主要病因是感染，可通过飞沫传播。' },
    { title: '病因', content: '常见危险因素包括免疫功能低下。' },
    { title: '临床表现', content: '主要表现为发热、咳嗽和乏力。' },
  ])

  assert.equal(outline.grouped, false)
  assert.equal(
    outline.groups[0].sections.map((section) => section.title).join('|'),
    ['病因', '临床表现'].join('|')
  )
  assert.match(outline.groups[0].sections[0].content, /感染/)
  assert.match(outline.groups[0].sections[0].content, /免疫功能低下/)
})
