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

/** 解析中文数字（含 十一、二十、二十三 等） */
export function parseChineseNumber(value: string): number | null {
  const trimmed = value.trim()
  if (/^\d+$/u.test(trimmed)) return Number.parseInt(trimmed, 10)

  let total = 0
  let current = 0

  for (const char of trimmed) {
    if (char === '十') {
      const multiplier = current === 0 ? 1 : current
      total += multiplier * 10
      current = 0
      continue
    }
    if (char === '百') {
      const multiplier = current === 0 ? 1 : current
      total += multiplier * 100
      current = 0
      continue
    }
    if (char === '零' || char === '〇') continue

    const digit = CHINESE_NUM_MAP[char]
    if (digit == null) return null
    current = digit
  }

  return total + current
}

/** 按教材「第X篇 / 第X章」提取排序权重，无序号则排到最后 */
export function getTextbookSortWeight(name: string, unit: '篇' | '章' = '篇'): number {
  const match = name.match(new RegExp(`第([一二三四五六七八九十百零〇\\d]+)${unit}`))
  if (!match) return 9999
  return parseChineseNumber(match[1]) ?? 9999
}

export function compareTextbookOrder(a: string, b: string, unit: '篇' | '章' = '篇'): number {
  const diff = getTextbookSortWeight(a, unit) - getTextbookSortWeight(b, unit)
  return diff !== 0 ? diff : a.localeCompare(b, 'zh-CN')
}

export function getChapterSortWeight(name: string): number {
  return getTextbookSortWeight(name, '篇')
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