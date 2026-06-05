/**
 * 知识图谱工具类
 */

/**
 * 寻找两个知识点之间的关联（用于疾病对比或思维导图）
 */
export function findRelationships(targetNode: any, allNodes: any[]) {
  const relatedIds = targetNode.related_nodes || []
  return allNodes.filter(n => relatedIds.includes(n.id))
}

/**
 * 为 AI 评估生成上下文：包含关联知识点
 * 帮助 AI 进行"发散式"提问
 */
export function getGraphContext(node: any, relatedNodes: any[]) {
  if (!relatedNodes.length) return ''

  const relatedTitles = relatedNodes.map(n => n.title).join('、')
  return `此知识点与以下内容密切相关：${relatedTitles}。在提问时可以引导学生思考它们之间的联系。`
}
