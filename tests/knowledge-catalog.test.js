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
      esModuleInterop: true,
    },
  }).outputText

  const module = { exports: {} }
  const wrapper = vm.runInNewContext(`(function (require, module, exports) { ${output} })`)
  wrapper(require, module, module.exports)
  return module.exports
}

const {
  normalizeSubjectLabel,
  buildSubjectCatalog,
  buildSubjectOrFilter,
  displayNodeTitle,
} = loadTypeScriptModule(path.join(__dirname, '..', 'utils', 'knowledgeCatalog.ts'))

test('normalizeSubjectLabel maps textbook variants to 内科学', () => {
  assert.equal(normalizeSubjectLabel('内科学（第10版）'), '内科学')
  assert.equal(normalizeSubjectLabel(null, 'internal-medicine-10'), '内科学')
  assert.equal(normalizeSubjectLabel('第三篇 循环系统疾病', '内科学（第10版）'), '内科学')
})

test('buildSubjectCatalog groups misassigned subjects under 内科学', () => {
  const catalog = buildSubjectCatalog([
    { subject: '内科学（第10版）', textbook: '内科学（第10版）' },
    { subject: '第三篇 循环系统疾病', textbook: '内科学（第10版）' },
    { subject: '第一篇 呼吸系统疾病', textbook: 'internal-medicine-10' },
  ])

  assert.equal(catalog.length, 1)
  assert.equal(catalog[0].name, '内科学')
  assert.equal(catalog[0].nodeCount, 3)
})

test('buildSubjectOrFilter includes textbook aliases for 内科学', () => {
  const filter = buildSubjectOrFilter('内科学')
  assert.match(filter, /subject\.eq\.内科学/)
  assert.match(filter, /textbook\.eq\.internal-medicine-10/)
})

test('displayNodeTitle removes redundant section prefixes', () => {
  assert.equal(
    displayNodeTitle('第一节 | 慢性支气管炎', '第三章 慢性阻塞性肺疾病'),
    '慢性支气管炎',
  )
})