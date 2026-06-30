import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const root = process.cwd()

test('disease detail only loads validated causal chains', () => {
  const source = fs.readFileSync(path.join(root, 'hooks/useDiseaseDetail.ts'), 'utf8')
  assert.match(source, /\.eq\('validation_status', 'valid'\)/)
  assert.doesNotMatch(source, /pending.*review_required|review_required.*pending/)
  assert.doesNotMatch(source, /chainsResult\.data\?\.\[0\].*find\(/s)
})

test('profile feedback does not route to generic ask screen', () => {
  const source = fs.readFileSync(path.join(root, 'app/(tabs)/profile.tsx'), 'utf8')
  assert.match(source, /action: 'feedback'/)
  assert.doesNotMatch(source, /\/\(tabs\)\/ask/)
})