/* global __dirname */
const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { loadTypeScriptModule } = require('./loadTsModule')

const {
  groupDiseaseKnowledgeNodes,
  hasKnowledgeEvidence,
  knowledgeNodeItemText,
  knowledgeNodeText,
} = loadTypeScriptModule(path.join(__dirname, '..', 'utils', 'diseaseKnowledge.ts'))

test('groups repeated disease nodes under one aspect card', () => {
  const groups = groupDiseaseKnowledgeNodes([
    { id: '1', title: '高血压的定义', aspect: 'definition', order_num: 0, content: '定义正文' },
    { id: '2', title: 'ACEI 类药物', aspect: 'treatment', order_num: 3, content: 'ACEI 正文' },
    { id: '3', title: '利尿剂', aspect: 'treatment', order_num: 2, content: '利尿剂正文' },
  ])

  assert.equal(groups.length, 2)
  assert.equal(groups[0].title, '定义')
  assert.equal(groups[1].title, '治疗方案')
  assert.equal(JSON.stringify(groups[1].nodes.map((node) => node.id)), JSON.stringify(['3', '2']))
})

test('keeps unclassified nodes as independent cards', () => {
  const groups = groupDiseaseKnowledgeNodes([
    { id: '1', title: 'ERCP 技术原理', aspect: 'other', order_num: 0, content: '原理正文' },
    { id: '2', title: 'ERCP 操作要点', aspect: 'other', order_num: 1, content: '操作正文' },
  ])

  assert.equal(groups.length, 2)
  assert.equal(
    JSON.stringify(groups.map((group) => group.title)),
    JSON.stringify(['ERCP 技术原理', 'ERCP 操作要点']),
  )
})

test('prefers structured sections when rendering node text', () => {
  const text = knowledgeNodeText({
    id: '1',
    title: '治疗方案',
    content: '旧正文',
    structured_sections: [
      { title: '一般治疗', content: '限制钠盐。' },
      { title: '药物治疗', content: '按适应证选择药物。' },
    ],
  })

  assert.equal(text, '1. 一般治疗\n限制钠盐。\n\n2. 药物治疗\n按适应证选择药物。')
})

test('hasKnowledgeEvidence requires non-empty evidence or evidence_items', () => {
  assert.equal(hasKnowledgeEvidence(null), false)
  assert.equal(hasKnowledgeEvidence({}), false)
  assert.equal(hasKnowledgeEvidence({ evidence: '   ' }), false)
  assert.equal(hasKnowledgeEvidence({ evidence: '教材原文片段' }), true)
  assert.equal(hasKnowledgeEvidence({ evidence_items: ['  ', '页内连续原文'] }), true)
})

test('omits a repeated section heading inside a grouped item', () => {
  const text = knowledgeNodeItemText({
    id: '1',
    title: 'ACEI 类药物',
    structured_sections: [{ title: '治疗方案', content: '抑制肾素-血管紧张素系统。' }],
  })

  assert.equal(text, '抑制肾素-血管紧张素系统。')
})
