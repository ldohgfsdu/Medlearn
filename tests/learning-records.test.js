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
const { calculateLearningRecordStats } = loadTypeScriptModule(
  path.join(root, 'utils', 'learningRecords.ts')
)

test('learning records count active days without requiring a streak', () => {
  const now = new Date(2026, 5, 11, 18, 0, 0)
  const records = [
    { completed_at: new Date(2026, 5, 11, 9, 0, 0).toISOString() },
    { completed_at: new Date(2026, 5, 11, 12, 0, 0).toISOString() },
    { completed_at: new Date(2026, 5, 8, 20, 0, 0).toISOString() },
    { completed_at: null },
  ]

  const result = calculateLearningRecordStats(records, now)
  assert.equal(result.completedToday, 2)
  assert.equal(result.learningDays, 2)
})

test('a break never erases previously recorded learning days', () => {
  const now = new Date(2026, 5, 11, 18, 0, 0)
  const records = [
    { completed_at: new Date(2026, 4, 1, 9, 0, 0).toISOString() },
    { completed_at: new Date(2026, 4, 20, 9, 0, 0).toISOString() },
  ]

  const result = calculateLearningRecordStats(records, now)
  assert.equal(result.completedToday, 0)
  assert.equal(result.learningDays, 2)
})
