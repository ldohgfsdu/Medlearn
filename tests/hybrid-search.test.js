const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTypeScriptModule } = require('./loadTsModule')

const root = path.resolve(__dirname, '..')
const { escapeIlikePattern } = loadTypeScriptModule(path.join(root, 'utils', 'hybridSearch.ts'))

test('escapeIlikePattern escapes wildcard and punctuation characters', () => {
  assert.equal(escapeIlikePattern('a%b_c\\d'), 'a\\%b\\_c\\\\d')
})

test('escapeIlikePattern strips PostgREST filter punctuation', () => {
  assert.equal(escapeIlikePattern('胸痛,(呼吸)'), '胸痛呼吸')
})

test('escapeIlikePattern truncates long queries', () => {
  const longQuery = 'a'.repeat(150)
  assert.equal(escapeIlikePattern(longQuery).length, 100)
})

test('escapeIlikePattern preserves regular Chinese medical terms', () => {
  assert.equal(escapeIlikePattern('急性心肌梗死'), '急性心肌梗死')
})