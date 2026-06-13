const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

function loadTypeScriptModule(filePath) {
  const source = fs.readFileSync(filePath, 'utf8')
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
    },
  }).outputText

  const module = { exports: {} }
  const wrapper = vm.runInNewContext(`(function (require, module, exports) { ${output} })`)
  wrapper(require, module, module.exports)
  return module.exports
}

const root = path.resolve(__dirname, '..')
const { getCaseFeedbackFocus, uniqueWeakNodeIds } = loadTypeScriptModule(
  path.join(root, 'utils', 'learningFeedback.ts')
)

function dimension(score, maxScore, analysis = '', details = []) {
  return { score, maxScore, analysis, details }
}

test('feedback focuses the lowest scoring case dimension', () => {
  const focus = getCaseFeedbackFocus({
    totalScore: 65,
    grade: 'fair',
    diagnosis: dimension(35, 40),
    differential: dimension(12, 20),
    evidence: dimension(5, 20, '关键证据覆盖率：25%'),
    treatment: dimension(13, 20),
    strengths: [],
    weaknesses: ['需要更充分地引用证据'],
    recommendations: [],
  })

  assert.equal(focus.key, 'evidence')
  assert.equal(focus.percent, 25)
  assert.match(focus.action, /证据/)
})

test('dangerous treatment feedback overrides ordinary score priority', () => {
  const focus = getCaseFeedbackFocus({
    totalScore: 60,
    grade: 'fair',
    diagnosis: dimension(10, 40),
    differential: dimension(15, 20),
    evidence: dimension(15, 20),
    treatment: dimension(20, 20, '', [
      { submitted: '错误用药', matched: '禁忌用药', matchType: 'none', score: -10, feedback: '危险措施：禁忌用药' },
    ]),
    strengths: [],
    weaknesses: [],
    recommendations: [],
  })

  assert.equal(focus.key, 'treatment')
  assert.match(focus.summary, /危险措施/)
})

test('weak node retry scope is unique and follows wrong questions only', () => {
  const nodes = uniqueWeakNodeIds([0, 2], [
    { related_nodes: ['a', 'b'] },
    { related_nodes: ['ignored'] },
    { related_nodes: ['b', 'c'] },
  ])

  assert.equal(nodes.join(','), 'a,b,c')
})
