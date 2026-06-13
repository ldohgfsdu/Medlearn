export interface SubjectCatalogEntry {
  name: string
  nodeCount: number
  textbooks: string[]
}

const CHINESE_NUM_MAP: Record<string, number> = {
  一: 1,
  二: 2,
  三: 3,
  四: 4,
  五: 5,
  六: 6,
  七: 7,
  八: 8,
  九: 9,
  十: 10,
}

const PART_LEVEL_SUBJECT_RE = /^第[一二三四五六七八九十百零〇\d]+[篇部分]/

const SUBJECT_TEXTBOOKS: Record<string, string[]> = {
  内科学: ['内科学（第10版）', 'internal-medicine-10'],
}

export function isPartLevelSubject(value: string | null | undefined): boolean {
  return !!value && PART_LEVEL_SUBJECT_RE.test(value)
}

export function normalizeSubjectLabel(
  raw: string | null | undefined,
  textbook?: string | null,
): string {
  if (textbook === 'internal-medicine-10' || textbook?.includes('内科学')) {
    return '内科学'
  }

  if (!raw) {
    return textbook?.trim() || '未分类'
  }

  if (isPartLevelSubject(raw)) {
    return '内科学'
  }

  if (raw.includes('内科学')) {
    return '内科学'
  }

  return raw.replace(/（第\d+版）/u, '').trim() || raw
}

export function buildSubjectOrFilter(catalogSubject: string): string {
  const textbooks = SUBJECT_TEXTBOOKS[catalogSubject]
  if (!textbooks?.length) {
    return `subject.eq.${catalogSubject}`
  }

  const clauses = new Set<string>([
    `subject.eq.${catalogSubject}`,
    `subject.eq.${catalogSubject}（第10版）`,
  ])

  for (const textbook of textbooks) {
    clauses.add(`textbook.eq.${textbook}`)
  }

  return Array.from(clauses).join(',')
}

export function subjectMatchesCatalog(
  node: { subject?: string | null; textbook?: string | null },
  catalogSubject: string,
): boolean {
  return normalizeSubjectLabel(node.subject, node.textbook) === catalogSubject
}

export function buildSubjectCatalog(
  nodes: Array<{ subject?: string | null; textbook?: string | null }>,
): SubjectCatalogEntry[] {
  const grouped = new Map<string, { count: number; textbooks: Set<string> }>()

  for (const node of nodes) {
    const name = normalizeSubjectLabel(node.subject, node.textbook)
    const bucket = grouped.get(name) ?? { count: 0, textbooks: new Set<string>() }
    bucket.count += 1
    if (node.textbook) bucket.textbooks.add(node.textbook)
    grouped.set(name, bucket)
  }

  return Array.from(grouped.entries())
    .map(([name, value]) => ({
      name,
      nodeCount: value.count,
      textbooks: Array.from(value.textbooks).sort(),
    }))
    .filter((entry) => entry.name !== '未分类' || entry.nodeCount > 0)
    .sort((a, b) => a.name.localeCompare(b.name, 'zh-CN'))
}

export function getChapterSortWeight(name: string): number {
  const match = name.match(/第([一二三四五六七八九十]+)篇/u)
  if (!match) return 999

  const numStr = match[1]
  if (numStr.length === 1) return CHINESE_NUM_MAP[numStr] ?? 999
  if (numStr.startsWith('十')) return 10 + (CHINESE_NUM_MAP[numStr[1]] ?? 0)
  return 999
}

export function displayNodeTitle(title: string, subChapter?: string | null): string {
  const trimmed = title.trim()
  const withoutSectionPrefix = trimmed.replace(/^第[一二三四五六七八九十\d]+节\s*[|｜]\s*/u, '')
  if (!subChapter) return withoutSectionPrefix

  const normalizedSubChapter = subChapter.replace(/\s+/g, '')
  const normalizedTitle = withoutSectionPrefix.replace(/\s+/g, '')
  if (normalizedTitle === normalizedSubChapter) {
    return withoutSectionPrefix
  }

  return withoutSectionPrefix
}

export function formatNodeType(type: string | null | undefined): string {
  switch (type) {
    case 'disease':
      return '疾病'
    case 'concept':
      return '概念'
    case 'mechanism':
      return '机制'
    case 'symptom':
      return '症状'
    case 'treatment':
      return '治疗'
    case 'exam':
      return '检查'
    default:
      return type || '知识点'
  }
}