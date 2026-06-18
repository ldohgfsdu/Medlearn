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
  path.join(root, 'utils', 'structuredContent.ts'),
)
const knowledgeOutline = loadTypeScriptModule(
  path.join(root, 'utils', 'knowledgeOutline.ts'),
  { './structuredContent': structuredContent },
)
const { buildFeynmanScaffold } = loadTypeScriptModule(
  path.join(root, 'utils', 'feynmanOutline.ts'),
  { './knowledgeOutline': knowledgeOutline },
)
const {
  buildFeynmanEvaluationUserPrompt,
  FEYNMAN_EVALUATION_SYSTEM_PROMPT,
} = loadTypeScriptModule(path.join(root, 'services', 'feynman-prompt.ts'))

test('buildFeynmanScaffold prefers structured section titles', () => {
  const scaffold = buildFeynmanScaffold({
    title: '急性心肌梗死',
    type: 'disease',
    content: '概述内容',
    structuredSections: [
      { title: '定义', content: '心肌梗死是……' },
      { title: '临床表现', content: '胸痛……' },
      { title: '诊断', content: '心电图……' },
      { title: '治疗', content: '再灌注……' },
    ],
  })

  assert.deepEqual(scaffold.mustCover, ['定义', '临床表现', '诊断', '治疗'])
  assert.match(scaffold.intro, /急性心肌梗死/)
  assert.equal(scaffold.tips.length, 3)
})

test('buildFeynmanScaffold falls back to disease prompts without sections', () => {
  const scaffold = buildFeynmanScaffold({
    title: '肺炎',
    type: 'disease',
    content: '',
  })

  assert.equal(scaffold.mustCover.length, 5)
  assert.equal(scaffold.mustCover[0], '定义与本质')
  assert.equal(scaffold.mustCover[4], '治疗原则')
})

test('feynman evaluation prompt includes coach fields and revision hint', () => {
  assert.match(FEYNMAN_EVALUATION_SYSTEM_PROMPT, /费曼教练/)
  assert.match(FEYNMAN_EVALUATION_SYSTEM_PROMPT, /下一句可以这样说/)

  const prompt = buildFeynmanEvaluationUserPrompt({
    nodeTitle: '房颤',
    textbookContext: '【教材：内科学 第12页】 房颤是……',
    userTranscript: '房颤就是心跳不规则。',
    attempt: 2,
  })

  assert.match(prompt, /知识点：房颤/)
  assert.match(prompt, /"strengths"/)
  assert.match(prompt, /"nextSentence"/)
  assert.match(prompt, /第 2 次复述/)
})