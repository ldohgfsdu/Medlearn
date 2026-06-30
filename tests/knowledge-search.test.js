import test from 'node:test'
import assert from 'node:assert/strict'
import { createRequire } from 'node:module'

const require = createRequire(import.meta.url)
const { loadTypeScriptModule } = require('./loadTsModule.js')
const {
  diseaseSearchScore,
  parseKnowledgeSearchIntent,
} = loadTypeScriptModule('utils/knowledgeSearch.ts')

test('parses disease plus aspect into a navigation intent', () => {
  const intent = parseKnowledgeSearchIntent('支气管哮喘的治疗方案')
  assert.equal(intent.diseaseQuery, '支气管哮喘')
  assert.equal(intent.aspect, 'treatment')
  assert.equal(intent.aspectLabel, '治疗方案')
})

test('matches canonical names and aliases without answering the query', () => {
  const intent = parseKnowledgeSearchIntent('COPD 治疗')
  assert.equal(
    diseaseSearchScore(intent, '慢性阻塞性肺疾病', ['COPD', '慢阻肺']),
    1,
  )
  assert.equal(
    diseaseSearchScore(intent, '支气管哮喘', ['哮喘']),
    null,
  )
})
