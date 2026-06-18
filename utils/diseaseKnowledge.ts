export interface KnowledgeSourceSpan {
  evidence?: string | null
  evidence_items?: string[] | null
  page_start?: number | null
  page_end?: number | null
  provenance?: {
    page_start?: number | null
    page_end?: number | null
  } | null
}

export interface DiseaseKnowledgeListNode {
  id: string
  title: string
  display_title?: string | null
  aspect?: string | null
  raw_aspect?: string | null
  content?: string | null
  key_points?: string[] | null
  structured_sections?: { title?: string; content?: string }[] | null
  order_num?: number | null
  source_span?: KnowledgeSourceSpan | null
}

export function hasKnowledgeEvidence(
  sourceSpan: KnowledgeSourceSpan | null | undefined,
): boolean {
  const evidenceItems = sourceSpan?.evidence_items?.filter((item) => item.trim()) ?? []
  if (evidenceItems.length > 0) return true
  return Boolean(sourceSpan?.evidence?.trim())
}

export interface DiseaseKnowledgeGroup<T extends DiseaseKnowledgeListNode> {
  key: string
  title: string
  nodes: T[]
}

const ASPECT_ORDER: Record<string, number> = {
  definition: 10,
  epidemiology: 20,
  etiology: 30,
  pathogenesis: 40,
  clinical_manifestation: 50,
  diagnosis: 60,
  differential_diagnosis: 70,
  treatment: 80,
  prognosis: 90,
  prevention: 100,
  other: 200,
}

const ASPECT_LABELS: Record<string, string> = {
  definition: '定义',
  epidemiology: '流行病学',
  etiology: '病因',
  pathogenesis: '发病机制',
  clinical_manifestation: '临床表现',
  diagnosis: '诊断与检查',
  differential_diagnosis: '鉴别诊断',
  treatment: '治疗方案',
  prognosis: '预后',
  prevention: '预防',
  other: '其他',
}

function firstSectionTitle(node: DiseaseKnowledgeListNode): string {
  return node.structured_sections?.find((section) => section.title?.trim())?.title?.trim() ?? ''
}

function groupIdentity(node: DiseaseKnowledgeListNode): { key: string; title: string; order: number } {
  const aspect = node.aspect?.trim()
  if (aspect === 'other') {
    const rawAspect = node.raw_aspect?.trim() || firstSectionTitle(node)
    if (rawAspect && rawAspect !== ASPECT_LABELS.other) {
      return {
        key: `other:${rawAspect}`,
        title: rawAspect,
        order: ASPECT_ORDER.other,
      }
    }
    const title = node.display_title?.trim() || node.title.trim()
    return { key: `node:${node.id}`, title, order: ASPECT_ORDER.other }
  }
  if (aspect) {
    return {
      key: `aspect:${aspect}`,
      title: ASPECT_LABELS[aspect] || node.raw_aspect?.trim() || firstSectionTitle(node) || aspect,
      order: ASPECT_ORDER[aspect] ?? ASPECT_ORDER.other,
    }
  }

  const rawAspect = node.raw_aspect?.trim() || firstSectionTitle(node)
  if (rawAspect) {
    return {
      key: `raw:${rawAspect}`,
      title: rawAspect,
      order: ASPECT_ORDER.other,
    }
  }

  const title = node.display_title?.trim() || node.title.trim()
  return { key: `node:${node.id}`, title, order: ASPECT_ORDER.other }
}

export function knowledgeNodeText(node: DiseaseKnowledgeListNode): string {
  const sections = node.structured_sections?.filter((item) => item.content?.trim()) ?? []
  if (sections.length) {
    return sections
      .map((item, index) => {
        const title = item.title?.trim()
        if (!title) return item.content
        return sections.length > 1
          ? `${index + 1}. ${title}\n${item.content}`
          : `${title}\n${item.content}`
      })
      .join('\n\n')
  }
  if (node.content?.trim()) return node.content.trim()
  return node.key_points?.join('\n') ?? ''
}

export function knowledgeNodeItemText(node: DiseaseKnowledgeListNode): string {
  const sections = node.structured_sections?.filter((item) => item.content?.trim()) ?? []
  if (sections.length === 1) return sections[0].content?.trim() ?? ''
  return knowledgeNodeText(node)
}

export function groupDiseaseKnowledgeNodes<T extends DiseaseKnowledgeListNode>(
  nodes: T[],
): DiseaseKnowledgeGroup<T>[] {
  const groups = new Map<string, DiseaseKnowledgeGroup<T> & { order: number; firstOrder: number }>()

  for (const node of nodes) {
    const identity = groupIdentity(node)
    const existing = groups.get(identity.key)
    if (existing) {
      existing.nodes.push(node)
      existing.firstOrder = Math.min(existing.firstOrder, node.order_num ?? 0)
      continue
    }
    groups.set(identity.key, {
      key: identity.key,
      title: identity.title,
      nodes: [node],
      order: identity.order,
      firstOrder: node.order_num ?? 0,
    })
  }

  return [...groups.values()]
    .sort((a, b) => a.order - b.order || a.firstOrder - b.firstOrder)
    .map(({ order: _order, firstOrder: _firstOrder, ...group }) => ({
      ...group,
      nodes: [...group.nodes].sort((a, b) => (a.order_num ?? 0) - (b.order_num ?? 0)),
    }))
}
