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
  parseChineseNumber,
  compareTextbookOrder,
  getTextbookSortWeight,
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

test('parseChineseNumber handles compound numerals', () => {
  assert.equal(parseChineseNumber('十'), 10)
  assert.equal(parseChineseNumber('十一'), 11)
  assert.equal(parseChineseNumber('十七'), 17)
  assert.equal(parseChineseNumber('二十'), 20)
  assert.equal(parseChineseNumber('23'), 23)
})

test('compareTextbookOrder sorts chapters by number not alphabet', () => {
  const sections = [
    '第九章 肺癌',
    '第七章 肺脓肿',
    '第十二章 肺动脉高压',
    '第四章 支气管哮喘',
    '第十一章 肺血栓栓塞症',
  ].sort((a, b) => compareTextbookOrder(a, b, '章'))

  assert.deepEqual(sections, [
    '第四章 支气管哮喘',
    '第七章 肺脓肿',
    '第九章 肺癌',
    '第十一章 肺血栓栓塞症',
    '第十二章 肺动脉高压',
  ])
})

test('getTextbookSortWeight orders 篇 correctly', () => {
  assert.ok(getTextbookSortWeight('第一篇 绪论', '篇') < getTextbookSortWeight('第二篇 呼吸系统疾病', '篇'))
  assert.ok(getTextbookSortWeight('第九篇 理化因素所致疾病', '篇') < getTextbookSortWeight('第十篇 其他', '篇'))
})

test('displayNodeTitle removes redundant section prefixes', () => {
  assert.equal(
    displayNodeTitle('第一节 | 慢性支气管炎', '第三章 慢性阻塞性肺疾病'),
    '慢性支气管炎',
  )
})