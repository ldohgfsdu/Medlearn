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
const {
  recommendStretchDifficulty,
  getCalibrationFeedback,
} = loadTypeScriptModule(path.join(root, 'utils', 'learningChallenge.ts'))

test('stretch difficulty advances only after demonstrated performance', () => {
  assert.equal(recommendStretchDifficulty(null), 'beginner')
  assert.equal(recommendStretchDifficulty(45), 'beginner')
  assert.equal(recommendStretchDifficulty(72), 'intermediate')
  assert.equal(recommendStretchDifficulty(90), 'advanced')
})

test('high confidence with a low score triggers calibration', () => {
  const feedback = getCalibrationFeedback(3, 42, '治疗顺序')
  assert.match(feedback.title, /确定感/)
  assert.match(feedback.summary, /治疗顺序/)
  assert.match(feedback.action, /证据/)
})

test('low confidence with a high score recognizes underestimation', () => {
  const feedback = getCalibrationFeedback(1, 88)
  assert.match(feedback.title, /掌握/)
  assert.match(feedback.summary, /低确定感/)
})
