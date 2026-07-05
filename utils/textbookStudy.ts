import type {
  TextbookPageReferenceKind,
  TextbookKnowledgeNode,
  TextbookListItem,
  TextbookSectionDetail,
  TextbookSectionSummary,
  TextbookTree,
} from '@/services/textbookService'
import {
  diseaseNamesMatch,
  type TextbookCatalogChapter,
  type TextbookCatalogPart,
  type TextbookCatalogUnit,
} from '@/utils/knowledgeTree'

const INTERNAL_MEDICINE_CATALOG_PARTS = (require('../constants/catalog.internal-medicine.json') as {
  chapters: TextbookCatalogPart[]
}).chapters

export interface TextbookMapChapter {
  id: string
  title: string
  fullTitle: string
  pageRange: string
  pageStart: number
  pageEnd: number
  nodeCount: number
}

export interface TextbookMapPart {
  title: string
  chapterCount: number
  pageRange: string
  chapters: TextbookMapChapter[]
}

export interface TextbookMapSubject {
  id: string
  title: string
  textbookTitle: string
  chapterCount: number
  partCount: number
  parts: TextbookMapPart[]
}

export interface StudyEvidence {
  id: string
  text: string
  pageLabel: string
  sourceOrder: number | null
  sourceLocatorIds?: string[]
  pageReferenceKind: TextbookPageReferenceKind
}

export interface StudyGroupItem {
  id: string
  title: string
  body: string
  pageLabel: string
  evidence: StudyEvidence[]
  evidenceOnly: boolean
  children?: StudyGroupItem[]
  contractItem?: boolean
}

export interface StudyGroup {
  id: string
  title: string
  pageLabel: string
  items: StudyGroupItem[]
}

export interface StudyUnit {
  id: string
  title: string
  catalogTitle?: string
  pageLabel: string
  itemCount: number
  evidenceOnlyCount: number
  groups: StudyGroup[]
}

export interface StudyCatalogSubsection {
  title: string
  node_type?: 'overview'
  content_status?: 'available' | 'in_progress' | 'unavailable'
  overview_slug?: string
}

const MAX_FALLBACK_STUDY_UNIT_ITEMS = 36
const FALLBACK_STUDY_UNIT_CHUNK_SIZE = 24
const MAX_CATALOG_STUDY_UNIT_ITEMS = 36
const TEXTBOOK_CHAPTER_TITLE_RE = /^\u7b2c[\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u96f6\u3007\d]+\u7ae0/u

interface CatalogStudyUnit {
  title: string
  catalogTitle?: string
  match: (node: TextbookKnowledgeNode) => boolean
}

interface CatalogStudyUnitOptions {
  splitOversized?: boolean
}

const CHINESE_DIGIT: Record<string, number> = {
  零: 0,
  〇: 0,
  一: 1,
  二: 2,
  两: 2,
  三: 3,
  四: 4,
  五: 5,
  六: 6,
  七: 7,
  八: 8,
  九: 9,
}

const SEMANTIC_GROUPS = [
  { title: '分类', patterns: ['分类', '分型', '类型', '分级'] },
  { title: '病因与发病机制', patterns: ['病因', '发病机制', '机制', '危险因素', '诱因'] },
  { title: '临床表现', patterns: ['临床表现', '症状', '体征', '表现'] },
  { title: '辅助检查', patterns: ['检查', '实验室', '影像', '血气', '肺功能'] },
  { title: '诊断与鉴别诊断', patterns: ['诊断', '鉴别诊断', '诊断标准'] },
  { title: '治疗', patterns: ['治疗', '处理', '用药', '抗菌', '手术'] },
  { title: '预防与预后', patterns: ['预防', '预后', '随访', '康复'] },
  { title: '并发症', patterns: ['并发症', '合并症'] },
  { title: '病理', patterns: ['病理'] },
  { title: '流行病学', patterns: ['流行病学', '患病率', '发病率'] },
  { title: '定义与概述', patterns: ['定义', '概述', '总论'] },
]

const GROUP_TOPIC_LABELS: Record<string, string> = {
  classification: '分类',
  auxiliary_exam: '实验室和其他检查',
  treatment: '治疗',
  source_evidence: '原文证据',
  definition: '定义',
  overview: '概述',
  etiology: '病因与发病机制',
  pathogenesis: '病因与发病机制',
  clinical: '临床表现',
  manifestation: '临床表现',
  diagnosis: '诊断与鉴别诊断',
  examination: '辅助检查',
  exam: '辅助检查',
  prevention: '预防与预后',
  prognosis: '预防与预后',
  complication: '并发症',
  pathology: '病理',
  epidemiology: '流行病学',
}

const ASPECT_SUFFIXES = [
  '定义与概述',
  '定义',
  '概述',
  '分类',
  '分型',
  '病因和发病机制',
  '病因与发病机制',
  '病因',
  '发病机制',
  '危险因素',
  '流行病学',
  '临床表现',
  '症状',
  '体征',
  '辅助检查',
  '实验室检查',
  '影像学检查',
  '检查',
  '诊断与鉴别诊断',
  '诊断',
  '鉴别诊断',
  '治疗',
  '处理',
  '预防与预后',
  '预防',
  '预后',
  '并发症',
  '病理',
  '特点',
  '常见病原菌',
  '病原菌',
]

function cleanText(value: string | null | undefined): string {
  return (value ?? '').replace(/\s+/g, ' ').trim()
}

/**
 * Normalize textbook display text for frontend rendering.
 *
 * Mirrors Python `scripts/textbook_pipeline/paragraph_reconstruction.py::normalize_display_text`.
 * Rules:
 * - NFC normalization (NOT NFKC — NFKC decomposes full-width CJK punctuation like ，→, which
 *   would modify medical text appearance; NFC preserves full-width punctuation)
 * - Strip zero-width chars (U+200B-U+200D, U+FEFF)
 * - Preserve paragraph boundaries (\n\n) while merging PDF line-wrap breaks
 * - Remove spaces between CJK chars (PDF line-break artifacts)
 * - Remove spaces between CJK and digits (both directions)
 * - Remove spaces before and after Chinese punctuation
 * - Remove spaces after opening brackets / before and after closing brackets
 * - Preserve English word spacing and unit spacing (e.g., "10 mg", "bronchial asthma")
 *
 * Does NOT modify medical text. Does NOT reconstruct truncated sentences.
 */
export function normalizeTextbookDisplayText(value: string | null | undefined): string {
  if (!value) return ''
  let text = (value ?? '').normalize('NFC')
  text = text.replace(/[\u200B-\u200D\uFEFF]/g, '')
  text = text.replace(/\r\n/g, '\n').replace(/\r/g, '\n')
  const segments = text.split(/\n{2,}/)
  const normalized: string[] = []
  for (let segment of segments) {
    segment = segment.replace(/[ \t\u3000]+/g, ' ')
    segment = segment.replace(/(?<=[\u4e00-\u9fff])[ \t\u3000\n]+(?=[\u4e00-\u9fff])/g, '')
    segment = segment.replace(/\n/g, ' ')
    segment = segment.replace(/[ \t]+/g, ' ')
    segment = segment.replace(/(?<=\d)[ \t]+(?=[\u4e00-\u9fff])/g, '')
    segment = segment.replace(/(?<=[\u4e00-\u9fff])[ \t]+(?=\d)/g, '')
    segment = segment.replace(/[ \t]+([，。；：！？、])/g, '$1')
    segment = segment.replace(/([，。；：！？、])[ \t]+/g, '$1')
    segment = segment.replace(/([（【「『])[ \t]+/g, '$1')
    segment = segment.replace(/[ \t]+([）】」』])/g, '$1')
    segment = segment.replace(/([）】」』])[ \t]+/g, '$1')
    const trimmed = segment.trim()
    if (trimmed) normalized.push(trimmed)
  }
  return normalized.join('\n\n')
}

/**
 * Detect truncated textbook text (port of Python is_truncated_sentence).
 *
 * Used by the App to mark body/evidence fields that end mid-clause, so the
 * learner is directed to the PageViewer page image for the complete original.
 * Mirrors scripts/textbook_pipeline/paragraph_reconstruction.py:98-108.
 */
const TRUNCATED_TAIL_RE =
  /(?:或|和|及|以及|包括|如|为|是|有|伴|并|但|而|且|与|在|对|从|向|把|被|将|要|可|应|需|待|的|了|着|过|发|距|射|照|物)\s*$/

function endsSentence(text: string): boolean {
  const value = (text ?? '').trim()
  if (!value) return false
  const last = value[value.length - 1]
  if ('。！？；.!?;」』""%％）)'.includes(last)) return true
  if (last === '.' && !(value.length >= 2 && /\d/.test(value[value.length - 2]))) return true
  return false
}

export function isTruncatedText(text: string | null | undefined): boolean {
  const value = (text ?? '').trim()
  if (!value) return false
  if (endsSentence(value)) return false
  if (TRUNCATED_TAIL_RE.test(value)) return true
  if ('，,:：、'.includes(value[value.length - 1])) return false
  return false
}

function stripSourceAspectPrefix(value: string): string {
  return normalizeTextbookDisplayText(value)
    .replace(/^【[^】]{1,48}】\s*/u, '')
    .replace(/^（[一二三四五六七八九十百零〇\d]+）\s*/u, '')
}

function compareByLocale(a: string, b: string): number {
  return a.localeCompare(b, 'zh-CN')
}

function parseChineseNumber(value: string): number | null {
  const text = value.trim()
  if (/^\d+$/u.test(text)) return Number.parseInt(text, 10)

  let total = 0
  let current = 0
  for (const char of text) {
    if (char === '十') {
      total += (current || 1) * 10
      current = 0
      continue
    }
    if (char === '百') {
      total += (current || 1) * 100
      current = 0
      continue
    }
    const digit = CHINESE_DIGIT[char]
    if (digit == null) return null
    current = digit
  }
  return total + current
}

export function getTextbookOrdinalWeight(title: string, unit: '篇' | '章' | '节'): number {
  const match = cleanText(title).match(new RegExp(`第([一二两三四五六七八九十百零〇\\d]+)${unit}`, 'u'))
  if (!match) return 9999
  return parseChineseNumber(match[1]) ?? 9999
}

function compareTextbookUnit(a: string, b: string, unit: '篇' | '章' | '节'): number {
  const diff = getTextbookOrdinalWeight(a, unit) - getTextbookOrdinalWeight(b, unit)
  return diff || compareByLocale(a, b)
}

function pageRange(start: number, end: number): string {
  if (!start && !end) return '?'
  return start === end ? String(start) : `${start}-${end}`
}

function normalizeTextbookTitle(title: string): string {
  return cleanText(title)
    .replace(/（第\d+版）/u, '')
    .replace(/\(第\d+版\)/u, '')
}

export function stripPartPrefixFromSectionTitle(sectionTitle: string, partTitle: string): string {
  const section = cleanText(sectionTitle)
  const part = cleanText(partTitle)
  if (!part) return section
  if (section === part) return section
  if (section.startsWith(part)) {
    return cleanText(section.slice(part.length))
  }
  return section.replace(new RegExp(`^${escapeRegExp(part)}\\s*`, 'u'), '').trim() || section
}

function escapeRegExp(value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

function compareSections(a: TextbookSectionSummary, b: TextbookSectionSummary): number {
  return compareTextbookUnit(a.partTitle, b.partTitle, '篇')
    || compareTextbookUnit(a.sectionTitle, b.sectionTitle, '章')
    || a.pageStart - b.pageStart
    || compareByLocale(a.sectionTitle, b.sectionTitle)
}

export function buildTextbookKnowledgeMap(tree: TextbookTree): TextbookMapSubject {
  const parts = new Map<string, TextbookSectionSummary[]>()
  for (const section of [...tree.sections].sort(compareSections)) {
    const partTitle = cleanText(section.partTitle) || '未分篇'
    parts.set(partTitle, [...(parts.get(partTitle) ?? []), section])
  }

  const partGroups = Array.from(parts.entries())
    .sort(([a], [b]) => compareTextbookUnit(a, b, '篇'))
    .map(([title, sections]) => {
      const sortedSections = [...sections].sort(compareSections)
      const pageStart = Math.min(...sortedSections.map((section) => section.pageStart).filter(Boolean))
      const pageEnd = Math.max(...sortedSections.map((section) => section.pageEnd).filter(Boolean))
      return {
        title,
        chapterCount: sortedSections.length,
        pageRange: Number.isFinite(pageStart) && Number.isFinite(pageEnd) ? pageRange(pageStart, pageEnd) : '?',
        chapters: sortedSections.map((section) => ({
          id: section.id,
          title: stripPartPrefixFromSectionTitle(section.sectionTitle, section.partTitle),
          fullTitle: section.sectionTitle,
          pageRange: section.pageRange,
          pageStart: section.pageStart,
          pageEnd: section.pageEnd,
          nodeCount: section.nodeCount,
        })),
      }
    })

  return {
    id: tree.textbookId,
    title: normalizeTextbookTitle(tree.textbookTitle) || '内科学',
    textbookTitle: tree.textbookTitle,
    partCount: partGroups.length,
    chapterCount: tree.sections.length,
    parts: partGroups,
  }
}

function semanticGroupTitle(node: TextbookKnowledgeNode): string {
  const groupTopic = cleanText(node.groupTopic)
  if (groupTopic) return GROUP_TOPIC_LABELS[groupTopic] ?? groupTopic

  const haystack = `${node.title} ${node.sourceHeading}`.toLowerCase()
  for (const group of SEMANTIC_GROUPS) {
    if (group.patterns.some((pattern) => haystack.includes(pattern.toLowerCase()))) {
      return group.title
    }
  }
  return cleanText(node.sourceHeading) || '教材要点'
}

function stripTextbookOrdinal(value: string): string {
  return cleanText(value)
    .replace(/^第[一二三四五六七八九十百零〇\d]+篇\s*/u, '')
    .replace(/^第[一二三四五六七八九十百零〇\d]+章\s*/u, '')
    .replace(/^第[一二三四五六七八九十百零〇\d]+节\s*/u, '')
    .replace(/^[（(][一二三四五六七八九十百零〇\d]+[）)]\s*/u, '')
    .trim()
}

function extractStudyChapterLabel(chapterName: string): string {
  return cleanText(chapterName)
    .replace(/^\u7b2c[\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\u767e\u96f6\u3007\d]+\u7ae0\s*/u, '')
    .trim()
}

function normalizeCatalogTitle(value: string): string {
  return stripTextbookOrdinal(value).replace(/\s+/g, '').replace(/[|｜　]/g, '')
}

function catalogUnitEntity(unitTitle: string): string {
  const [, afterPipe] = unitTitle.split(/[|｜]/u)
  return stripTextbookOrdinal(afterPipe ?? unitTitle)
}

function catalogSubsectionIsRedundant(unitTitle: string, subsectionTitle: string): boolean {
  return normalizeCatalogTitle(catalogUnitEntity(unitTitle)) === normalizeCatalogTitle(subsectionTitle)
}

function isDerivedDiseaseSubsectionTitle(title: string, unitEntity: string): boolean {
  const text = stripTextbookOrdinal(title)
  const normalized = normalizeCatalogTitle(text)
  if (!text || !normalized) return false
  if (/^[A-Z0-9/-]{2,12}$/u.test(text)) return false
  if (text.includes('的')) return false
  if (/诊断|检查|治疗|方法|检测|特征|病原体|常见性|别称|分型|趋势/u.test(text)) return false
  if (/肺炎型|肺部感染性疾病|急性细菌性肺炎/u.test(text)) return false

  if (unitEntity.includes('真菌')) {
    return /真菌|念珠菌|曲霉|隐球菌|肺孢子菌|毛霉/u.test(text)
      && /病|肺炎/u.test(text)
  }

  return /病|炎|癌|瘤|症|征|感染|综合征|肺炎/u.test(text)
}

export function deriveCatalogSubsectionsFromStudyGroups(
  unitTitle: string,
  catalogSubsections: StudyCatalogSubsection[] = [],
  studyUnit: StudyUnit | null | undefined,
): StudyCatalogSubsection[] {
  if (catalogSubsections.length !== 1 || !studyUnit) return catalogSubsections
  const [catalogSubsection] = catalogSubsections
  if (!catalogSubsectionIsRedundant(unitTitle, catalogSubsection.title)) return catalogSubsections

  const unitEntity = catalogUnitEntity(unitTitle)
  const seen = new Set<string>()
  const derived = studyUnit.groups
    .map((group) => stripTextbookOrdinal(group.title))
    .filter((title) => isDerivedDiseaseSubsectionTitle(title, unitEntity))
    .filter((title) => {
      const key = normalizeCatalogTitle(title)
      if (seen.has(key)) return false
      seen.add(key)
      return true
    })
    .map((title) => ({ title }))

  return derived.length > 1 ? derived : catalogSubsections
}

function lastHeadingLine(value: string): string {
  const lines = cleanText(value).split(/\s+/u).filter(Boolean)
  return lines.at(-1) ?? ''
}

function normalizedAspectLabel(value: string): string | null {
  const text = cleanText(value)
  if (!text) return null

  for (const group of SEMANTIC_GROUPS) {
    if (group.patterns.some((pattern) => text.includes(pattern))) return group.title
  }
  return ASPECT_SUFFIXES.find((suffix) => text.includes(suffix)) ?? null
}

function isAspectOnlyTitle(value: string): boolean {
  const text = stripTextbookOrdinal(value)
  if (!text) return false
  if (GROUP_TOPIC_LABELS[text]) return true
  return SEMANTIC_GROUPS.some((group) => group.title === text || group.patterns.includes(text))
}

function looksLikeStandaloneTopic(value: string): boolean {
  const text = stripTextbookOrdinal(value)
  if (!text || isAspectOnlyTitle(text)) return false
  if (
    /原文|治疗|处理|检查|诊断|表现|因素|病原体|分类|分布|标准/u.test(text)
    && !/肺炎|疾病|感染|综合征|糖尿病|甲状腺|垂体|肾上腺|癌|瘤/u.test(text)
  ) return false
  if (/^[A-Z][A-Z0-9/-]{1,12}$/u.test(text)) return true
  return /病|炎|癌|瘤|症|征|感染|障碍|疾病|综合征|肺炎|血液|激素|甲状腺|垂体|肾上腺|糖尿病/u.test(text)
}

function splitTopicAndAspect(title: string): { topic: string; aspect: string } | null {
  const text = stripTextbookOrdinal(title)
  const possessive = text.match(/^(.{1,48}?)(?:的|之)(.{1,32})$/u)
  if (possessive && !isAspectOnlyTitle(possessive[1])) {
    return {
      topic: stripTextbookOrdinal(possessive[1]),
      aspect: cleanText(possessive[2]),
    }
  }

  for (const suffix of ASPECT_SUFFIXES) {
    if (text.length > suffix.length + 1 && text.endsWith(suffix)) {
      const topic = stripTextbookOrdinal(text.slice(0, -suffix.length))
      if (!looksLikeStandaloneTopic(topic)) continue
      return {
        topic,
        aspect: suffix,
      }
    }
  }

  return null
}

function sourceTopicFromHeading(node: TextbookKnowledgeNode, sectionTitle: string): string {
  const heading = stripTextbookOrdinal(lastHeadingLine(node.sourceHeading))
  const section = stripTextbookOrdinal(sectionTitle)
  if (!heading || heading === section) return ''
  if (!looksLikeStandaloneTopic(heading)) return ''
  return heading
}

function pulmonaryInfectionOverviewTopic(node: TextbookKnowledgeNode, sectionTitle: string): string {
  if (!sectionTitle.includes('肺部感染性疾病')) return ''
  if (nodeFirstPage(node) >= 81 || nodeOrder(node) >= 119) return ''

  const title = cleanText(node.title)
  const text = nodeHaystack(node)
  const isGenericPneumoniaSign = (
    (title === '临床表现' || title === '肺实变的体征') &&
    text.includes('肺实变时有典型的体征') &&
    text.includes('叩诊呈浊音') &&
    text.includes('支气管呼吸音')
  )

  return isGenericPneumoniaSign ? '肺炎' : ''
}

function inferTopicTitle(node: TextbookKnowledgeNode, sectionTitle: string, fallbackTopic = ''): string {
  if (node.groupTopic === 'auxiliary_exam') {
    return GROUP_TOPIC_LABELS.auxiliary_exam
  }

  if (node.publicationState === 'evidence_only' && node.groupTopic) {
    const semanticTopic = GROUP_TOPIC_LABELS[node.groupTopic] ?? cleanText(node.groupTopic)
    if (semanticTopic) return semanticTopic
  }

  const pulmonaryOverviewTopic = pulmonaryInfectionOverviewTopic(node, sectionTitle)
  if (pulmonaryOverviewTopic) return pulmonaryOverviewTopic

  if (node.publicationState === 'evidence_only' || node.renderType === 'evidence_only') {
    const semantic = semanticGroupTitle(node)
    if (semantic && semantic !== cleanText(node.sourceHeading) && isAspectOnlyTitle(semantic)) {
      return semantic
    }
  }

  const split = splitTopicAndAspect(node.title)
  const sectionTopic = stripTextbookOrdinal(sectionTitle)
  if (split?.topic && split.topic !== sectionTopic) return split.topic
  if (split?.topic === sectionTopic && fallbackTopic) return fallbackTopic

  const sourceTopic = sourceTopicFromHeading(node, sectionTitle)
  if (sourceTopic && !isAspectOnlyTitle(sourceTopic)) return sourceTopic

  const title = stripTextbookOrdinal(node.title)
  if (looksLikeStandaloneTopic(title)) return title

  if (fallbackTopic) return fallbackTopic

  if (title) return title

  return stripTextbookOrdinal(sectionTitle) || '教材要点'
}

function aspectTitleForNode(node: TextbookKnowledgeNode): string {
  const split = splitTopicAndAspect(node.title)
  const fromTitle = normalizedAspectLabel(split?.aspect ?? '')
  if (fromTitle) return fromTitle

  const semantic = semanticGroupTitle(node)
  if (semantic && semantic !== cleanText(node.sourceHeading)) return semantic

  return cleanText(split?.aspect) || cleanText(node.title) || '教材原文'
}

function groupKey(node: TextbookKnowledgeNode, sectionTitle: string, fallbackTopic = ''): string {
  return inferTopicTitle(node, sectionTitle, fallbackTopic)
}

function nodeOrder(node: TextbookKnowledgeNode): number {
  const orders = node.evidenceItems
    .map((item) => item.sourceOrder)
    .filter((value): value is number => typeof value === 'number')
  return orders.length > 0 ? Math.min(...orders) : Number.MAX_SAFE_INTEGER
}

function nodeFirstPage(node: TextbookKnowledgeNode): number {
  const pages = node.evidenceItems
    .flatMap((item) => [item.pageStart, item.pageEnd])
    .filter((value): value is number => typeof value === 'number')
  return pages.length > 0 ? Math.min(...pages) : Number.MAX_SAFE_INTEGER
}

function nodeHaystack(node: TextbookKnowledgeNode): string {
  return [
    node.title,
    node.content,
    node.evidenceFull,
    ...node.listItems.flatMap((item) => [item.title, item.body]),
    ...node.evidenceItems.map((item) => item.text),
  ].join('\n')
}

function containsAny(value: string, needles: string[]): boolean {
  return needles.some((needle) => value.includes(needle))
}

function findCatalogChapterBySectionTitle(sectionTitle: string): TextbookCatalogChapter | null {
  const normalized = normalizeCatalogTitle(sectionTitle)
  for (const part of INTERNAL_MEDICINE_CATALOG_PARTS) {
    const chapter = part.sections.find(
      (candidate) => normalizeCatalogTitle(candidate.title) === normalized,
    )
    if (chapter) return chapter
  }
  return null
}

function catalogUnitEntities(unit: TextbookCatalogUnit): string[] {
  const subsections = unit.subsections ?? []
  if (subsections.length > 0) {
    return subsections.map((item) => item.title.trim()).filter(Boolean)
  }
  return [catalogUnitEntity(unit.title)]
}

function nodeMatchesCatalogEntities(
  node: TextbookKnowledgeNode,
  entities: string[],
  sectionTitle: string,
): boolean {
  const topic = inferTopicTitle(node, sectionTitle)
  const title = stripTextbookOrdinal(node.title)
  const haystack = normalizeCatalogTitle(nodeHaystack(node))

  return entities.some((entity) => {
    const normalizedEntity = normalizeCatalogTitle(entity)
    if (!normalizedEntity) return false
    if (diseaseNamesMatch(topic, entity) || diseaseNamesMatch(title, entity)) return true
    return haystack.includes(normalizedEntity)
      && (/病|炎|感染|综合征/u.test(entity) || looksLikeStandaloneTopic(entity))
  })
}

function getJsonCatalogStudyUnits(detail: TextbookSectionDetail): CatalogStudyUnit[] {
  const catalogChapter = findCatalogChapterBySectionTitle(detail.section.sectionTitle)
  if (!catalogChapter?.units?.length) return []

  const sectionTitle = detail.section.sectionTitle
  return catalogChapter.units.flatMap((unit) => {
    const subsections = unit.subsections ?? []
    if (subsections.length >= 2) {
      return subsections.map((subsection) => ({
        title: subsection.title,
        catalogTitle: unit.title.replace(/\s*[|｜]\s*/u, ' '),
        match: (node) => nodeMatchesCatalogEntities(node, [subsection.title], sectionTitle),
      }))
    }
    return [{
      title: unit.title,
      catalogTitle: unit.title.replace(/\s*[|｜]\s*/u, ' '),
      match: (node) => nodeMatchesCatalogEntities(node, catalogUnitEntities(unit), sectionTitle),
    }]
  })
}

function pulmonaryInfectionCatalogTitle(unitTitle: string): string {
  if (unitTitle === '\u80ba\u708e') return '\u7b2c\u4e00\u8282 \u80ba\u708e\u6982\u8ff0'
  if (
    unitTitle === '\u80ba\u708e\u94fe\u7403\u83cc\u80ba\u708e'
    || unitTitle === '\u8461\u8404\u7403\u83cc\u80ba\u708e'
  ) {
    return '\u7b2c\u4e8c\u8282 \u7ec6\u83cc\u6027\u80ba\u708e'
  }
  if (
    unitTitle === '\u75c5\u6bd2\u6027\u80ba\u708e'
    || unitTitle === '\u4e25\u91cd\u6025\u6027\u547c\u5438\u7efc\u5408\u5f81'
    || unitTitle === '\u9ad8\u81f4\u75c5\u6027\u4eba\u79bd\u6d41\u611f\u75c5\u6bd2\u6027\u80ba\u708e'
    || unitTitle === '2019 \u51a0\u72b6\u75c5\u6bd2\u75c5'
  ) {
    return '\u7b2c\u4e09\u8282 \u75c5\u6bd2\u6027\u80ba\u708e'
  }
  if (
    unitTitle === '\u80ba\u708e\u652f\u539f\u4f53\u80ba\u708e'
    || unitTitle === '\u8863\u539f\u4f53\u80ba\u708e'
    || unitTitle === '\u80ba\u519b\u56e2\u75c5'
  ) {
    return '\u7b2c\u56db\u8282 \u80ba\u708e\u652f\u539f\u4f53\u80ba\u708e\u3001\u8863\u539f\u4f53\u80ba\u708e\u4e0e\u80ba\u519b\u56e2\u75c5'
  }
  return '\u7b2c\u4e94\u8282 \u80ba\u771f\u83cc\u75c5'
}

function getPulmonaryInfectionCatalogStudyUnits(detail: TextbookSectionDetail): CatalogStudyUnit[] {
  if (!detail.section.sectionTitle.includes('肺部感染性疾病')) return []

  const units: CatalogStudyUnit[] = [
    {
      title: '肺炎',
      match: (node) => {
        const page = nodeFirstPage(node)
        const order = nodeOrder(node)
        return page < 81 || (page === 81 && order < 119)
      },
    },
    {
      title: '肺炎链球菌肺炎',
      match: (node) => {
        const text = nodeHaystack(node)
        return containsAny(text, ['肺炎链球菌', '肺炎球菌'])
          || /(?:^|[^A-Za-z])SP(?:[^A-Za-z]|$)/u.test(text)
      },
    },
    {
      title: '葡萄球菌肺炎',
      match: (node) => containsAny(nodeHaystack(node), ['葡萄球菌']),
    },
    {
      title: '病毒性肺炎',
      match: (node) => containsAny(nodeHaystack(node), ['病毒性肺炎', '腺病毒', '呼吸道合胞病毒']),
    },
    {
      title: '严重急性呼吸综合征',
      match: (node) => containsAny(nodeHaystack(node), ['严重急性呼吸综合征', 'SARS']),
    },
    {
      title: '高致病性人禽流感病毒性肺炎',
      match: (node) => containsAny(nodeHaystack(node), ['人禽流感', '禽流感']),
    },
    {
      title: '2019 冠状病毒病',
      match: (node) => containsAny(nodeHaystack(node), ['2019 冠状病毒病', 'COVID', '冠状病毒病']),
    },
    {
      title: '肺炎支原体肺炎',
      match: (node) => containsAny(nodeHaystack(node), ['肺炎支原体', '支原体肺炎']),
    },
    {
      title: '衣原体肺炎',
      match: (node) => containsAny(nodeHaystack(node), ['衣原体肺炎', '肺炎衣原体']),
    },
    {
      title: '肺军团病',
      match: (node) => containsAny(nodeHaystack(node), ['肺军团病', '军团菌', '军团病']),
    },
    {
      title: '肺念珠菌病',
      match: (node) => containsAny(nodeHaystack(node), ['肺念珠菌', '念珠菌']),
    },
    {
      title: '肺曲霉病',
      match: (node) => containsAny(nodeHaystack(node), ['肺曲霉', '曲霉']),
    },
    {
      title: '肺隐球菌病',
      match: (node) => containsAny(nodeHaystack(node), ['肺隐球菌', '隐球菌']),
    },
    {
      title: '肺孢子菌肺炎',
      match: (node) => containsAny(nodeHaystack(node), ['肺孢子菌', '肺孢子虫']),
    },
    {
      title: '肺真菌病',
      match: (node) => nodeFirstPage(node) >= 94,
    },
  ]
  return units.map((unit) => ({
    ...unit,
    catalogTitle: pulmonaryInfectionCatalogTitle(unit.title),
  }))
}

function getCatalogStudyUnits(detail: TextbookSectionDetail): CatalogStudyUnit[] {
  const pulmonaryUnits = getPulmonaryInfectionCatalogStudyUnits(detail)
  if (pulmonaryUnits.length > 0) return pulmonaryUnits
  return getJsonCatalogStudyUnits(detail)
}

export function resolveCatalogOutlineUnit(
  catalogUnitTitle: string,
  studyUnits: StudyUnit[],
): StudyUnit | null {
  const entity = normalizeCatalogTitle(catalogUnitEntity(catalogUnitTitle))
  const directTitle = normalizeCatalogTitle(catalogUnitTitle)
  const matchKey = entity || directTitle
  if (!matchKey) return null

  return studyUnits.find((unit) => {
    const unitEntity = normalizeCatalogTitle(catalogUnitEntity(unit.title))
    const unitTitle = normalizeCatalogTitle(unit.title)
    return unitEntity === matchKey
      || unitTitle === matchKey
      || unitTitle.startsWith(`${matchKey}·`)
      || diseaseNamesMatch(unit.title, catalogUnitEntity(catalogUnitTitle))
  }) ?? null
}

function studyUnitFromCatalogGroups(catalogUnit: CatalogStudyUnit, index: number, groups: StudyGroup[]): StudyUnit {
  const items = groups.flatMap((group) => group.items)
  return {
    id: `unit-${index + 1}-${hashString(catalogUnit.title)}`,
    title: catalogUnit.title,
    catalogTitle: catalogUnit.catalogTitle,
    pageLabel: combinedPageLabel(items),
    itemCount: items.length,
    evidenceOnlyCount: items.filter((item) => item.evidenceOnly).length,
    groups,
  }
}

function catalogSubunitTitle(catalogTitle: string, groupTitle: string): string {
  const title = cleanText(catalogTitle)
  const childTitle = cleanText(groupTitle)
  if (!childTitle || childTitle === title) return title
  return `${title} · ${childTitle}`
}

function studyUnitFromCatalogGroup(
  catalogUnit: CatalogStudyUnit,
  catalogIndex: number,
  group: StudyGroup,
  groupIndex: number,
  chunkIndex = 0,
): StudyUnit {
  const evidenceOnlyCount = group.items.filter((item) => item.evidenceOnly).length
  const chunkSuffix = chunkIndex > 0 ? `-${chunkIndex + 1}` : ''
  return {
    id: `unit-${catalogIndex + 1}-${groupIndex + 1}${chunkSuffix}-${hashString(`${catalogUnit.title}-${group.title}-${group.pageLabel}-${chunkIndex}`)}`,
    title: catalogSubunitTitle(catalogUnit.title, group.title),
    catalogTitle: catalogUnit.catalogTitle,
    pageLabel: group.pageLabel,
    itemCount: group.items.length,
    evidenceOnlyCount,
    groups: [group],
  }
}

function splitCatalogStudyGroup(
  catalogUnit: CatalogStudyUnit,
  catalogIndex: number,
  group: StudyGroup,
  groupIndex: number,
): StudyUnit[] {
  if (group.items.length <= MAX_CATALOG_STUDY_UNIT_ITEMS) {
    return [studyUnitFromCatalogGroup(catalogUnit, catalogIndex, group, groupIndex)]
  }

  const units: StudyUnit[] = []
  for (let start = 0; start < group.items.length; start += FALLBACK_STUDY_UNIT_CHUNK_SIZE) {
    const items = group.items.slice(start, start + FALLBACK_STUDY_UNIT_CHUNK_SIZE)
    units.push(
      studyUnitFromCatalogGroup(
        catalogUnit,
        catalogIndex,
        {
          ...group,
          id: `${group.id}-chunk-${units.length + 1}`,
          pageLabel: combinedPageLabel(items),
          items,
        },
        groupIndex,
        units.length,
      ),
    )
  }
  return units
}

function buildCatalogStudyUnits(
  detail: TextbookSectionDetail,
  options: CatalogStudyUnitOptions = {},
): StudyUnit[] {
  const catalogUnits = getCatalogStudyUnits(detail)
  if (catalogUnits.length === 0) return []

  const splitOversized = options.splitOversized ?? true
  const seenNodeIds = new Set<string>()
  const units: StudyUnit[] = []

  for (const [index, catalogUnit] of catalogUnits.entries()) {
    const nodes = detail.nodes.filter((node) => {
      if (seenNodeIds.has(node.id)) return false
      return catalogUnit.match(node)
    })
    for (const node of nodes) seenNodeIds.add(node.id)

    const groups = compactCatalogStudyGroups(
      buildChapterStudyGroupsInternal(
        { ...detail, nodes },
        { compact: true, preferStructuredSourceGroups: true },
      ),
      catalogUnit.title,
    )
    const aggregateUnit = studyUnitFromCatalogGroups(catalogUnit, index, groups)
    if (
      splitOversized
      && aggregateUnit.itemCount > MAX_CATALOG_STUDY_UNIT_ITEMS
      && groups.length > 1
    ) {
      units.push(...groups.flatMap((group, groupIndex) => (
        splitCatalogStudyGroup(catalogUnit, index, group, groupIndex)
      )))
    } else {
      units.push(aggregateUnit)
    }
  }

  return units.filter((unit) => unit.itemCount > 0)
}

function evidenceForNode(node: TextbookKnowledgeNode): StudyEvidence[] {
  return node.evidenceItems
    .filter((item) => cleanText(item.text))
    .map((item) => ({
      id: item.artifactId,
      text: normalizeTextbookDisplayText(item.text),
      pageLabel: normalizeStudyPageLabel(item.pageLabel),
      sourceOrder: item.sourceOrder,
      sourceLocatorIds: item.sourceLocatorIds?.length ? item.sourceLocatorIds : undefined,
      pageReferenceKind: item.pageReferenceKind,
    }))
}

function normalizeStudyPageLabel(value: string): string {
  const text = cleanText(value)
  if (!text) return ''
  return /^p\.?/iu.test(text) ? text.replace(/^p\.?/iu, 'p.') : `p.${text}`
}

function joinedEvidenceText(evidence: StudyEvidence[]): string {
  return evidence.map((item) => stripSourceAspectPrefix(item.text)).filter(Boolean).join('\n\n')
}

function displayItemsForNode(
  node: TextbookKnowledgeNode,
  options: { preferStructuredSourceGroups?: boolean } = {},
): StudyGroupItem[] {
  const evidence = evidenceForNode(node)
  if (node.listItems.length > 0) {
    if (options.preferStructuredSourceGroups && isStructuredSourceGroupNode(node)) {
      return structuredSourceItemsForNode(node)
    }
    if (shouldNestGroupedList(node)) {
      return [groupedListToStudyItem(node, evidence)]
    }
    return node.listItems.map((item, index) => itemToStudyItem(node, item, index, evidence))
  }

  const evidenceOnly = node.publicationState === 'evidence_only' || node.renderType === 'evidence_only'
  const originalText = joinedEvidenceText(evidence)
  return [{
    id: node.id,
    title: node.title,
    body: originalText || normalizeTextbookDisplayText(evidenceOnly ? node.evidenceFull || node.content : node.content),
    pageLabel: node.pageLabel,
    evidence,
    evidenceOnly,
  }]
}

function shouldNestGroupedList(node: TextbookKnowledgeNode): boolean {
  return node.renderType === 'grouped'
    && (isClassificationGroupedList(node) || isAuxiliaryExamGroupedList(node))
    && (node.listItems.length > 1 || node.listItems.some((item) => (item.children?.length ?? 0) > 0))
}

function isClassificationGroupedList(node: TextbookKnowledgeNode): boolean {
  return node.groupTopic === 'classification'
    || semanticGroupTitle(node) === GROUP_TOPIC_LABELS.classification
}

function isAuxiliaryExamGroupedList(node: TextbookKnowledgeNode): boolean {
  return node.groupTopic === 'auxiliary_exam'
    || semanticGroupTitle(node) === GROUP_TOPIC_LABELS.auxiliary_exam
}

function groupedListToStudyItem(node: TextbookKnowledgeNode, evidence: StudyEvidence[]): StudyGroupItem {
  const contractChildren = buildContractTreeItems(node, evidence)
  const auxiliaryChildren = contractChildren ? null : buildAuxiliaryExamTreeItems(node, evidence)
  const introEvidence = contractChildren || auxiliaryChildren ? [] : evidence[0] ? [evidence[0]] : []
  const introText = joinedEvidenceText(introEvidence)
  const childEvidenceOffset = introText ? 1 : 0
  const children = contractChildren
    ?? auxiliaryChildren
    ?? buildClassificationTreeItems(node, evidence)
    ?? node.listItems.map((item, index) => (
      itemToStudyItem(node, item, index + childEvidenceOffset, evidence)
    ))

  return {
    id: node.id,
    title: cleanText(node.title) || semanticGroupTitle(node),
    body: introText || stripSourceAspectPrefix(node.content),
    pageLabel: cleanText(node.pageLabel) || combinedPageLabel(children),
    evidence: introEvidence.length > 0 ? introEvidence : evidence,
    evidenceOnly: node.publicationState === 'evidence_only',
    children,
  }
}

function buildContractTreeItems(
  node: TextbookKnowledgeNode,
  evidence: StudyEvidence[],
): StudyGroupItem[] | null {
  if (!node.listItems.some((item) => (item.children?.length ?? 0) > 0)) return null
  return node.listItems.map((item, index) => itemToDisplayStudyItem(node, item, index, evidence))
}

function buildClassificationTreeItems(
  node: TextbookKnowledgeNode,
  evidence: StudyEvidence[],
): StudyGroupItem[] | null {
  if (!isClassificationGroupedList(node)) return null

  const previewItems = node.listItems.map((item, index) => itemToDisplayStudyItem(node, item, index, evidence))
  const tbContext = isTuberculosisClassificationContext(previewItems)
  const roots: StudyGroupItem[] = []
  let currentTop: StudyGroupItem | null | undefined = null
  let currentAxis: StudyGroupItem | null = null
  let currentLeaf: StudyGroupItem | null = null

  for (const [index, item] of node.listItems.entries()) {
    const child = itemToDisplayStudyItem(node, item, index, evidence)
    if (isClassificationIntroItem(node, child)) continue

    const topTitle = tbContext ? classificationTopLevelTitle(child) : null
    if (topTitle) {
      currentTop = getOrCreateClassificationBucket(roots, topTitle, child)
      currentAxis = null
      currentLeaf = currentTop
      continue
    }

    const bucketTitle = classificationBucketTitle(child)
    if (bucketTitle) {
      if (tbContext) {
        const parent: StudyGroupItem = currentTop ?? getOrCreateClassificationBucket(roots, '活动性结核病', child)
        currentTop = parent
        currentAxis = getOrCreateClassificationChild(parent, bucketTitle, child)
      } else {
        currentTop = null
        currentAxis = getOrCreateClassificationBucket(roots, displayClassificationAxisLabel(bucketTitle), child)
      }
      currentLeaf = currentAxis
      if (isClassificationBucketHeading(child, bucketTitle)) {
        currentAxis.body = mergeStudyBody(currentAxis.body, child.body)
        currentAxis.evidence = mergeStudyEvidence(currentAxis.evidence, child.evidence)
      }
      continue
    }

    let subtypeTitle = classificationSiteSubtypeTitle(child)
    if (subtypeTitle && tbContext && subtypeTitle.endsWith('肺炎')) {
      subtypeTitle = null
    }
    if (subtypeTitle && currentAxis) {
      currentLeaf = getOrCreateClassificationChild(currentAxis, subtypeTitle, child)
      continue
    }

    if (currentAxis?.title === '按既往治疗史分类') {
      const historyTitle = classificationTreatmentHistoryTitle(child)
      if (historyTitle) {
        currentLeaf = getOrCreateClassificationChild(currentAxis, historyTitle, child)
        continue
      }
    }

    if (currentLeaf) {
      appendToStudyItem(currentLeaf, child)
      continue
    }

    roots.push(child)
    currentLeaf = child
    currentTop = null
    currentAxis = null
  }

  const usefulRoots = roots.filter((item) => item.body || (item.children?.length ?? 0) > 0)
  const hasTree = usefulRoots.some((item) => (item.children?.length ?? 0) > 0)
  if (hasTree || (tbContext && usefulRoots.length >= 2)) return usefulRoots
  return null
}

function getOrCreateClassificationChild(
  parent: StudyGroupItem,
  title: string,
  seed: StudyGroupItem,
): StudyGroupItem {
  parent.children = parent.children ?? []
  const existing = parent.children.find((item) => item.title === title)
  if (existing) {
    appendToStudyItem(existing, seed)
    parent.pageLabel = combinedPageLabel(parent.children)
    parent.evidence = mergeStudyEvidence(parent.evidence, seed.evidence)
    return existing
  }

  const item: StudyGroupItem = {
    ...seed,
    title,
    children: seed.children ?? [],
  }
  parent.children.push(item)
  parent.pageLabel = combinedPageLabel(parent.children)
  parent.evidence = mergeStudyEvidence(parent.evidence, seed.evidence)
  return item
}

function buildAuxiliaryExamTreeItems(
  node: TextbookKnowledgeNode,
  evidence: StudyEvidence[],
): StudyGroupItem[] | null {
  if (!isAuxiliaryExamGroupedList(node)) return null

  const roots: StudyGroupItem[] = []
  let currentTopItem: StudyGroupItem | null = null
  let lungFunctionBucket: StudyGroupItem | null = null
  let currentLungFunctionItem: StudyGroupItem | null = null

  for (const [index, item] of node.listItems.entries()) {
    const child = itemToDisplayStudyItem(node, item, index, evidence)
    const lungFunctionTitle = auxiliaryLungFunctionTitle(child)
    if (lungFunctionTitle) {
      lungFunctionBucket = getOrCreateAuxiliaryContainer(roots, '肺功能检查', child)
      currentTopItem = lungFunctionBucket
      currentLungFunctionItem = getOrCreateAuxiliaryChild(lungFunctionBucket, lungFunctionTitle, child)
      continue
    }

    const topTitle = auxiliaryTopTitle(child)
    if (topTitle) {
      currentTopItem = getOrCreateAuxiliaryTopItem(roots, topTitle, child)
      currentLungFunctionItem = null
      continue
    }

    if (currentLungFunctionItem) {
      appendToStudyItem(currentLungFunctionItem, child)
    } else if (currentTopItem) {
      appendToStudyItem(currentTopItem, child)
    } else {
      roots.push(child)
      currentTopItem = child
    }
  }

  const usefulRoots = roots.filter((item) => item.body || item.evidence.length > 0 || (item.children?.length ?? 0) > 0)
  return usefulRoots.length >= 2 ? usefulRoots : null
}

function auxiliaryTopTitle(item: StudyGroupItem): string | null {
  const text = `${item.title} ${item.body}`
  if (/痰嗜酸性粒细胞计数/u.test(text)) return '痰嗜酸性粒细胞计数'
  if (/外周血嗜酸性粒细胞计数|外周血嗜酸性粒细胞增高/u.test(text)) return '外周血嗜酸性粒细胞计数'
  if (/胸部X\s*线|胸部CT|胸部X线\/CT检查|胸部X线\/CT/u.test(text)) return '胸部X线/CT检查'
  if (/特异性变应原检测|变应原特异性IgE|血清总IgE|变应原皮肤点刺|变应原激发试验/u.test(text)) return '特异性变应原检测'
  if (/动脉血气分析|PaCO2|呼吸性碱中毒|呼吸性酸中毒/u.test(text)) return '动脉血气分析'
  if (/呼出气一氧化氮|FeNO/u.test(text)) return '呼出气一氧化氮（FeNO）检测'
  return null
}

function auxiliaryLungFunctionTitle(item: StudyGroupItem): string | null {
  const text = `${item.title} ${item.body}`
  if (/通气功能检测|FVC|FEV1\/FVC|气流受限|阻塞性通气功能障碍/u.test(text)) return '通气功能检测'
  if (/支气管激发试验|BPT|PD20|PC20|气道高反应性|FEV1\s*下降≥?20/u.test(text)) return '支气管激发试验（BPT）'
  if (/PEF|呼气峰流量|昼夜变异率|周变异率/u.test(text)) return '呼气峰流量（PEF）及其变异率测定'
  if (/支气管舒张试验|BDT|支气管扩张剂|增加≥?12|增加≥?200ml|可逆性的气道阻塞/u.test(text)) return '支气管舒张试验（BDT）'
  return null
}

function getOrCreateAuxiliaryTopItem(
  roots: StudyGroupItem[],
  title: string,
  seed: StudyGroupItem,
): StudyGroupItem {
  const existing = roots.find((item) => item.title === title)
  if (existing) {
    appendToStudyItem(existing, seed)
    return existing
  }

  const item: StudyGroupItem = {
    ...seed,
    title,
  }
  roots.push(item)
  return item
}

function getOrCreateAuxiliaryContainer(
  roots: StudyGroupItem[],
  title: string,
  seed: StudyGroupItem,
): StudyGroupItem {
  const existing = roots.find((item) => item.title === title)
  if (existing) return existing

  const item: StudyGroupItem = {
    id: `${seed.id}-container-${hashString(title)}`,
    title,
    body: '',
    pageLabel: seed.pageLabel,
    evidence: [],
    evidenceOnly: false,
    children: [],
  }
  roots.push(item)
  return item
}

function getOrCreateAuxiliaryChild(
  parent: StudyGroupItem,
  title: string,
  seed: StudyGroupItem,
): StudyGroupItem {
  parent.children = parent.children ?? []
  const existing = parent.children.find((item) => item.title === title)
  if (existing) {
    appendToStudyItem(existing, seed)
    parent.pageLabel = combinedPageLabel(parent.children)
    parent.evidence = mergeStudyEvidence(parent.evidence, seed.evidence)
    return existing
  }

  const item: StudyGroupItem = {
    ...seed,
    title,
  }
  parent.children.push(item)
  parent.pageLabel = combinedPageLabel(parent.children)
  parent.evidence = mergeStudyEvidence(parent.evidence, seed.evidence)
  return item
}

function itemToDisplayStudyItem(
  node: TextbookKnowledgeNode,
  item: TextbookListItem,
  index: number,
  nodeEvidence: StudyEvidence[],
  path = String(index),
): StudyGroupItem {
  const itemEvidence = evidenceForListItem(item, index, nodeEvidence, false)
  return {
    id: `${node.id}-item-${path}`,
    title: cleanText(item.title) || semanticGroupTitle(node),
    body: stripSourceAspectPrefix(item.body),
    pageLabel: cleanText(item.pageLabel),
    evidence: itemEvidence,
    evidenceOnly: item.publicationState === 'evidence_only',
    children: (item.children ?? []).map((child, childIndex) => (
      itemToDisplayStudyItem(node, child, childIndex, nodeEvidence, `${path}-${childIndex}`)
    )),
  }
}

function isClassificationIntroItem(node: TextbookKnowledgeNode, item: StudyGroupItem): boolean {
  const title = cleanText(item.title)
  return title === cleanText(node.title)
    || /分类依据|分类标准/u.test(title)
}

function classificationBucketTitle(item: StudyGroupItem): string | null {
  const text = `${item.title} ${item.body}`
  if (item.title === '肺结核的病变部位' || /按照病变部位/u.test(text)) {
    return '按病变部位分类'
  }
  if (item.title.startsWith('按') && item.title.includes('分类')) {
    return item.title
  }
  if (item.title.endsWith('耐药分类') || /按耐药状况分类/u.test(text)) {
    return '按耐药状况分类'
  }
  const numberedAxis = text.match(/^\d+\.\s*(按[^。；;]+分类)/u)
  if (numberedAxis) return numberedAxis[1]
  return null
}

function isTuberculosisClassificationContext(items: StudyGroupItem[]): boolean {
  return items.some((item) => /潜伏感染|活动性结核|WS 196|按病变部位|结核分枝杆菌/u.test(`${item.title} ${item.body}`))
}

function classificationTopLevelTitle(item: StudyGroupItem): string | null {
  const title = cleanText(item.title)
  if (/结核分枝杆菌潜伏感染|潜伏感染者/u.test(title)) return '结核分枝杆菌潜伏感染者'
  if (/病原学检测阴性肺结核/u.test(title)) return '病原学检测阴性肺结核'
  if (/活动性结核/u.test(title)) return '活动性结核病'
  return null
}

function displayClassificationAxisLabel(title: string): string {
  if (title === '按解剖分类' || title === '按病因分类' || title === '按患病环境分类') {
    return title.replace(/^按/u, '')
  }
  return title
}

function classificationSiteSubtypeTitle(item: StudyGroupItem): string | null {
  const text = `${item.title} ${item.body}`
  if (/原发性肺结核/u.test(text)) return '原发性肺结核'
  if (/血行播散性肺结核/u.test(text) && !/鉴别/u.test(text)) return '血行播散性肺结核'
  if (/继发性肺结核/u.test(text) && !/记录/u.test(text)) return '继发性肺结核'
  if (/气管、支气管结核|气管支气管结核/u.test(text)) return '气管、支气管结核'
  if (item.title === '结核性胸膜炎' || /结核性胸膜炎/u.test(text)) return '结核性胸膜炎'
  if (/肺外结核/u.test(text)) return '肺外结核'
  if (/大叶性/u.test(text)) return '大叶性（肺泡性）肺炎'
  if (/小叶性|支气管性/u.test(text)) return '小叶性（支气管性）肺炎'
  if (/间质性肺炎/u.test(text)) return '间质性肺炎'
  if (/社区获得性/u.test(text)) return '社区获得性肺炎'
  if (/医院获得性/u.test(text)) return '医院获得性肺炎'
  if (/细菌性肺炎/u.test(text)) return '细菌性肺炎'
  return null
}

function classificationTreatmentHistoryTitle(item: StudyGroupItem): string | null {
  const text = `${item.title} ${item.body}`
  if (/初治/u.test(text) && !/复治/u.test(item.title)) return '初治肺结核'
  if (/复治/u.test(text)) return '复治肺结核'
  return null
}

function isClassificationBucketHeading(item: StudyGroupItem, bucketTitle: string): boolean {
  const title = cleanText(item.title)
  const normalizedTitle = title.replace(/^按/u, '')
  const normalizedBucket = bucketTitle.replace(/^按/u, '')
  return title === bucketTitle || normalizedTitle === normalizedBucket
}

function getOrCreateClassificationBucket(
  buckets: StudyGroupItem[],
  title: string,
  seed: StudyGroupItem,
): StudyGroupItem {
  const existing = buckets.find((bucket) => bucket.title === title)
  if (existing) return existing

  const bucket: StudyGroupItem = {
    ...seed,
    id: `${seed.id}-bucket-${hashString(title)}`,
    title,
    children: seed.children ?? [],
  }
  buckets.push(bucket)
  return bucket
}

function appendToStudyItem(target: StudyGroupItem, addition: StudyGroupItem): void {
  target.body = mergeStudyBody(target.body, addition.body)
  target.pageLabel = combinedPageLabel([
    { ...target },
    { ...addition },
  ])
  target.evidence = mergeStudyEvidence(target.evidence, addition.evidence)
  target.evidenceOnly = target.evidenceOnly && addition.evidenceOnly
}

function mergeStudyBody(base: string, extra: string): string {
  const normBase = normalizeTextbookDisplayText(base)
  const normExtra = normalizeTextbookDisplayText(extra)
  // Use cleanText for structural comparison only (flattens for includes-check)
  const cleanBase = cleanText(normBase)
  const cleanExtra = cleanText(normExtra)
  if (!cleanBase) return normExtra
  if (!cleanExtra || cleanBase.includes(cleanExtra)) return normBase
  return `${normBase} ${normExtra}`
}

function mergeStudyEvidence(base: StudyEvidence[], extra: StudyEvidence[]): StudyEvidence[] {
  const byId = new Map<string, StudyEvidence>()
  for (const item of [...base, ...extra]) {
    byId.set(item.id, item)
  }
  return Array.from(byId.values())
}

function itemToStudyItem(
  node: TextbookKnowledgeNode,
  item: TextbookListItem,
  index: number,
  nodeEvidence: StudyEvidence[],
): StudyGroupItem {
  const itemEvidence = evidenceForListItem(item, index, nodeEvidence, true)
  const originalText = joinedEvidenceText(itemEvidence)
  return {
    id: `${node.id}-${index}`,
    title: cleanText(item.title) || node.title,
    body: originalText || stripSourceAspectPrefix(item.body),
    pageLabel: cleanText(item.pageLabel) || node.pageLabel,
    evidence: itemEvidence,
    evidenceOnly: item.publicationState === 'evidence_only',
    children: (item.children ?? []).map((child, childIndex) => (
      itemToDisplayStudyItem(node, child, childIndex, nodeEvidence, `${index}-${childIndex}`)
    )),
  }
}

function evidenceForListItem(
  item: TextbookListItem,
  index: number,
  nodeEvidence: StudyEvidence[],
  fallbackToNodeEvidence: boolean,
): StudyEvidence[] {
  const artifactIds = new Set((item.evidenceArtifactIds ?? []).filter(Boolean))
  if (artifactIds.size > 0) {
    return nodeEvidence.filter((evidence) => artifactIds.has(evidence.id))
  }
  if ((item.children?.length ?? 0) > 0) return []
  if (nodeEvidence[index]) return [nodeEvidence[index]]
  return fallbackToNodeEvidence ? nodeEvidence : []
}

function pageLabelBounds(labels: string[]): { start: number; end: number } | null {
  let start = Number.POSITIVE_INFINITY
  let end = 0
  for (const label of labels) {
    for (const match of label.matchAll(/p\.(\d+)(?:-(\d+))?/gu)) {
      const pageStart = Number(match[1])
      const pageEnd = Number(match[2] ?? match[1])
      if (!Number.isFinite(pageStart) || !Number.isFinite(pageEnd)) continue
      start = Math.min(start, pageStart)
      end = Math.max(end, pageEnd)
    }
  }
  if (!Number.isFinite(start) || end <= 0) return null
  return { start, end }
}

function combinedPageLabel(items: StudyGroupItem[]): string {
  const labels = Array.from(new Set(items.map((item) => item.pageLabel).filter(Boolean)))
  if (labels.length === 0) return ''
  const bounds = pageLabelBounds(labels)
  if (bounds) {
    return bounds.start === bounds.end ? `p.${bounds.start}` : `p.${bounds.start}-${bounds.end}`
  }
  if (labels.length <= 2) return labels.join('、')
  return `${labels[0]}-${labels[labels.length - 1].replace(/^p+\./u, '')}`
}

function isAddressableAspectGroupTitle(title: string): boolean {
  return title === '治疗'
    || title === '处理'
    || title === GROUP_TOPIC_LABELS.auxiliary_exam
    || title === GROUP_TOPIC_LABELS.examination
}

function looksLikeMajorStudyGroupTitle(value: string): boolean {
  const title = stripTextbookOrdinal(value)
  if (!title || isAspectOnlyTitle(title)) return false
  if (/^[A-Z][A-Z0-9/-]{1,12}$/u.test(title)) return true
  if (/病死率|严重性|取决|因素|指标|表现|检查|治疗|诊断|标准|病原体|机制|传播|检测|使用|关系|影响|方法|情况|指征|病灶|健康威胁|分类依据/u.test(title)) {
    return false
  }
  return /肺炎$|肺炎|感染$|感染性疾病$|综合征$|冠状病毒病$|流行性感冒$|肺脓肿$|肺结核$|肺癌$|肺栓塞$/u.test(title)
}

function looksLikeCatalogStudyGroupTitle(value: string, catalogTitle = ''): boolean {
  const title = stripTextbookOrdinal(value)
  const catalogEntity = catalogUnitEntity(catalogTitle)
  if (!title) return false
  if (title === '治疗' || title === '处理') return true
  if (/^[A-Z][A-Z0-9/-]{1,12}$/u.test(title)) {
    return /^(?:CAP|HAP|VAP|ABPA)$/u.test(title)
  }
  if (/[和与及的]$/u.test(title)) return false
  if (title === '肺炎' && !catalogEntity.includes('肺炎概述')) return false
  if (catalogEntity.includes('肺真菌病') && title === '急性细菌性肺炎') return false
  if (
    /评估因素|病理变化|病原学|肺部体征|全身感染中毒|移植病例|中型|具有|重症高危人群|原文证据|自然病程|吸氧指征|并发症|诊断方法|模式选择|培养分离|分泌物中|非特异性抗体|可能无阳性|种与人类疾病|外感染|呼吸系统疾病中|确定肺炎|应做|导致肺炎/u.test(title)
  ) {
    return false
  }
  if (
    /因素|指标|表现|检查|诊断|标准|病原体|机制|传播|检测|使用|关系|影响|方法|情况|指征|病灶|健康威胁|分类依据|特定人群/u.test(title)
    && !/肺炎$|感染$|感染性疾病$|综合征$|冠状病毒病$|流行性感冒$|肺脓肿$|肺结核$|肺癌$|肺栓塞$/u.test(title)
  ) {
    return false
  }
  if (/对|中|导致|结合|产生|分泌物|种类|型$/u.test(title)) return false
  return /肺炎$|感染$|感染性疾病$|综合征$|冠状病毒病$|流行性感冒$|肺脓肿$|肺结核$|肺癌$|肺栓塞$|军团病$|真菌病$|念珠菌病$|曲霉病$|隐球菌病$/u.test(title)
}

function mergeStudyGroupItems(target: StudyGroup, addition: StudyGroup, placement: 'append' | 'prepend'): void {
  target.items = placement === 'prepend'
    ? [...addition.items, ...target.items]
    : [...target.items, ...addition.items]
  target.pageLabel = combinedPageLabel(target.items)
}

function compactCatalogStudyGroups(groups: StudyGroup[], catalogTitle: string): StudyGroup[] {
  const compacted: StudyGroup[] = []
  const pendingLeading: StudyGroup[] = []

  for (const group of groups) {
    const addressable = looksLikeCatalogStudyGroupTitle(group.title, catalogTitle)
    if (addressable) {
      const nextGroup: StudyGroup = { ...group, items: [...group.items] }
      for (const pending of pendingLeading) {
        mergeStudyGroupItems(nextGroup, pending, 'prepend')
      }
      pendingLeading.length = 0
      compacted.push(nextGroup)
      continue
    }

    const previous = compacted.at(-1)
    if (previous) {
      mergeStudyGroupItems(previous, group, 'append')
    } else {
      pendingLeading.push(group)
    }
  }

  if (pendingLeading.length > 0 && compacted.length > 0) {
    const first = compacted[0]
    for (const pending of pendingLeading.reverse()) {
      mergeStudyGroupItems(first, pending, 'prepend')
    }
  }

  return compacted.length > 0 ? compacted : groups
}

function compactMinorStudyGroups(groups: StudyGroup[]): StudyGroup[] {
  const compacted: StudyGroup[] = []
  for (const group of groups) {
    const previous = compacted.at(-1)
    const isAddressableAspectGroup = isAddressableAspectGroupTitle(group.title)
    const previousIsAddressableAspectGroup = previous
      ? isAddressableAspectGroupTitle(previous.title)
      : false
    const isSemanticEvidenceOnlyGroup = isAspectOnlyTitle(group.title)
      && group.items.some((item) => item.evidenceOnly)
    const shouldFoldIntoPrevious = previous
      && group.items.length <= 2
      && !previousIsAddressableAspectGroup
      && !isAddressableAspectGroup
      && !isSemanticEvidenceOnlyGroup
      && !looksLikeMajorStudyGroupTitle(group.title)

    if (shouldFoldIntoPrevious) {
      previous.items.push(...group.items)
      previous.pageLabel = combinedPageLabel(previous.items)
    } else {
      compacted.push(group)
    }
  }
  return compacted
}

function hashString(value: string): string {
  let hash = 0
  for (let index = 0; index < value.length; index += 1) {
    hash = ((hash << 5) - hash + value.charCodeAt(index)) | 0
  }
  return Math.abs(hash).toString(36)
}

function endsWithSentenceBoundary(value: string): boolean {
  return /[。！？；.!?;]$/u.test(cleanText(value))
}

function startsAsContinuation(value: string): boolean {
  return /^[，。、；：,.!?;:)）]|^(或|及|和|与|为|以|使|致|而|并|且|其|该|此)/u.test(cleanText(value))
}

function areAdjacentEvidenceItems(previous: StudyGroupItem, current: StudyGroupItem): boolean {
  const previousOrder = previous.evidence.at(-1)?.sourceOrder
  const currentOrder = current.evidence[0]?.sourceOrder
  if (previous.pageLabel && previous.pageLabel === current.pageLabel && startsAsContinuation(current.body)) {
    return true
  }
  if (typeof previousOrder !== 'number' || typeof currentOrder !== 'number') return false
  return currentOrder === previousOrder || currentOrder === previousOrder + 1
}

function mergePageLabel(previous: string, current: string): string {
  if (!previous) return current
  if (!current || current === previous) return previous
  return `${previous}、${current}`
}

function mergeContinuationItems(items: StudyGroupItem[]): StudyGroupItem[] {
  const merged: StudyGroupItem[] = []
  for (const item of items) {
    const previous = merged.at(-1)
    const shouldMerge = previous
      && areAdjacentEvidenceItems(previous, item)
      && !previous.contractItem
      && !item.contractItem
      && (!endsWithSentenceBoundary(previous.body) || startsAsContinuation(item.body))

    if (shouldMerge) {
      previous.body = `${previous.body}${startsAsContinuation(item.body) ? '' : ' '}${item.body}`.trim()
      previous.pageLabel = mergePageLabel(previous.pageLabel, item.pageLabel)
      previous.evidence = [...previous.evidence, ...item.evidence]
      previous.evidenceOnly = previous.evidenceOnly && item.evidenceOnly
    } else {
      merged.push({ ...item, evidence: [...item.evidence] })
    }
  }
  return merged
}

interface SourceEvidenceRow {
  evidence: StudyEvidence
  node: TextbookKnowledgeNode
  index: number
}

interface SourceHeading {
  title: string
  body: string
  startsGroup: boolean
}

function uniqueSourceEvidenceRows(detail: TextbookSectionDetail): SourceEvidenceRow[] {
  const rows: SourceEvidenceRow[] = []
  const seen = new Set<string>()
  let index = 0
  for (const node of detail.nodes) {
    for (const evidence of evidenceForNode(node)) {
      const key = evidence.id || `${evidence.pageLabel}-${evidence.sourceOrder ?? 'na'}-${evidence.text}`
      if (seen.has(key)) continue
      seen.add(key)
      rows.push({ evidence, node, index })
      index += 1
    }
  }
  return rows.sort((a, b) => {
    const pageDiff = firstPageNumber(a.evidence.pageLabel) - firstPageNumber(b.evidence.pageLabel)
    if (pageDiff) return pageDiff
    const aOrder = a.evidence.sourceOrder ?? Number.MAX_SAFE_INTEGER
    const bOrder = b.evidence.sourceOrder ?? Number.MAX_SAFE_INTEGER
    return aOrder - bOrder || a.index - b.index
  })
}

function firstPageNumber(pageLabel: string): number {
  const match = cleanText(pageLabel).match(/p\.?(\d+)/iu)
  return match ? Number(match[1]) : Number.MAX_SAFE_INTEGER
}

function normalizeSourceHeadingTitle(value: string): string {
  return stripTextbookOrdinal(value)
    .replace(/^[\uff08(][\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\d]+[\uff09)]\s*/u, '')
    .replace(/^\d+[.．、]\s*/u, '')
    .replace(/[：:]\s*$/u, '')
    .trim()
}

function canonicalSourceHeadingTitle(title: string): string {
  if (/\u6c14\u9053\u9ad8\u53cd\u5e94\u6027[\uff08(]\s*airway$/iu.test(title)) return '\u6c14\u9053\u9ad8\u53cd\u5e94\u6027'
  if (/^\u4e34\u5e8a\u63a7\u5236\u671f\s+\u6307/u.test(title)) return '\u4e34\u5e8a\u63a7\u5236\u671f'
  if (/^\u7279\u5f02\u6027\u53d8\u5e94\u539f\u68c0\u6d4b\s+\u5916\u5468\u8840/u.test(title)) return '\u7279\u5f02\u6027\u53d8\u5e94\u539f\u68c0\u6d4b'
  return title
}

function sourceHeadingFromEvidenceText(value: string): SourceHeading | null {
  const text = cleanText(value)
  const bracket = text.match(/^【([^】]{1,24})】\s*(.*)$/u)
  if (bracket) {
    return {
      title: canonicalSourceHeadingTitle(normalizeSourceHeadingTitle(bracket[1])),
      body: cleanText(bracket[2]),
      startsGroup: true,
    }
  }

  const parenthesized = text.match(/^[\uff08(]([\u4e00\u4e8c\u4e09\u56db\u4e94\u516d\u4e03\u516b\u4e5d\u5341\d]+)[\uff09)]\s*([^：:。；;]{2,26})(?:[：:]\s*|\s+)(.*)$/u)
  if (parenthesized) {
    return {
      title: canonicalSourceHeadingTitle(normalizeSourceHeadingTitle(parenthesized[2])),
      body: cleanText(parenthesized[3]),
      startsGroup: true,
    }
  }

  const numbered = text.match(/^(\d+)[.．、]\s*([^：:。；;]{2,30})(?:[：:]\s*|\s+)(.*)$/u)
  if (numbered) {
    return {
      title: canonicalSourceHeadingTitle(normalizeSourceHeadingTitle(numbered[2])),
      body: cleanText(numbered[3]),
      startsGroup: false,
    }
  }

  return null
}

function sourceGroupTitleFromText(value: string): string | null {
  const text = normalizeSourceHeadingTitle(value)
  if (!text) return null
  if (/定义|概述/u.test(text)) return '定义与概述'
  if (/流行病学/u.test(text)) return '流行病学'
  if (/病因|发病机制|气道炎症|气道高反应性|神经调节/u.test(text)) return '病因与发病机制'
  if (/病理/u.test(text)) return '病理'
  if (/临床表现|症状|体征/u.test(text)) return '临床表现'
  if (/实验室|其他检查|辅助检查|肺功能|影像|血气|变应原|FeNO/u.test(text)) return '实验室和其他检查'
  if (/诊断|鉴别诊断|分期|控制水平|评估|严重程度/u.test(text)) return '诊断与鉴别诊断'
  if (/并发症/u.test(text)) return '并发症'
  if (/^治疗|^管理|^药物治疗|^非药物治疗|治疗原则|治疗目标/u.test(text)) return '治疗'
  if (/教育与管理|病人的教育|自我管理/u.test(text)) return '教育与管理'
  if (/预后/u.test(text)) return '预后'
  if (/预防|随访/u.test(text)) return '预防与预后'
  return null
}

function sourceGroupTitleForNode(node: TextbookKnowledgeNode): string | null {
  const title = normalizeSourceHeadingTitle(node.title)
  if (!title) return null
  if (node.groupTopic === 'auxiliary_exam') return '实验室和其他检查'
  if (/^定义与概述$|^概述$|^定义$/u.test(title)) return '定义与概述'
  if (/^流行病学$/u.test(title)) return '流行病学'
  if (/^病因与发病机制$|^病因$|^发病机制$/u.test(title)) return '病因与发病机制'
  if (/^病理$/u.test(title)) return '病理'
  if (/治疗目标|治疗原则|治疗药物|药物治疗|非药物治疗|长期.*治疗方案|初始.*治疗|治疗方案|ICS|SABA|LABA|LAMA|白三烯|茶碱|抗胆碱|生物制剂|糖皮质激素/u.test(title)) return '治疗'
  if (/^典型症状$|^运动性哮喘$|^体征$/u.test(title)) return '临床表现'
  if (/^实验室和其他检查$|^辅助检查$/u.test(title)) return '实验室和其他检查'
  if (/典型哮喘|可变气流受限的客观检查|诊断|鉴别|分期|控制水平|急性发作期|慢性持续期|临床控制期|^轻度$|^中度$|^重度$|^危重度$|变异性哮喘|哮喘合并|上气道阻塞|曲霉病/u.test(title)) return '诊断与鉴别诊断'
  if (/并发症/u.test(title)) return '并发症'
  if (/教育与管理|病人的教育|自我管理/u.test(title)) return '教育与管理'
  if (/^预后$/u.test(title)) return '预后'
  if (/^预防$|^预防与预后$/u.test(title)) return '预防与预后'
  return null
}

function sourceItemTitleForNode(node: TextbookKnowledgeNode, groupTitle: string): string {
  const title = normalizeSourceHeadingTitle(node.title)
  if (!title) return groupTitle
  if (groupTitle === '\u6cbb\u7597' && /\u6cbb\u7597\u76ee\u6807|\u6cbb\u7597\u539f\u5219|\u6cbb\u7597\u65b9\u6848|\u6cbb\u7597\u836f\u7269|\u836f\u7269\u6cbb\u7597|\u975e\u836f\u7269\u6cbb\u7597|\u957f\u671f.*\u6cbb\u7597|\u521d\u59cb.*\u6cbb\u7597|ICS|SABA|LABA|LAMA/u.test(title)) return title
  if (groupTitle === '\u6559\u80b2\u4e0e\u7ba1\u7406' && /\u6559\u80b2|\u7ba1\u7406/u.test(title)) return title
  if (groupTitle === '\u8bca\u65ad\u4e0e\u9274\u522b\u8bca\u65ad' && /\u8bca\u65ad|\u9274\u522b|\u5206\u671f|\u63a7\u5236|\u6025\u6027\u53d1\u4f5c|\u6162\u6027\u6301\u7eed|\u4e34\u5e8a\u63a7\u5236|\u53d8\u5f02\u6027\u54ee\u5598|\u4e0a\u6c14\u9053\u963b\u585e/u.test(title)) return title
  if (groupTitle === '\u5e76\u53d1\u75c7' && /\u5e76\u53d1\u75c7/u.test(title)) return title
  if (groupTitle === '\u5b9e\u9a8c\u5ba4\u548c\u5176\u4ed6\u68c0\u67e5' && /\u5b9e\u9a8c\u5ba4|\u68c0\u67e5|\u8bd5\u9a8c|\u8840\u6c14|\u53d8\u5e94\u539f/u.test(title)) return title
  if (groupTitle === '\u9884\u540e' && /\u9884\u540e/u.test(title)) return title
  return groupTitle
}

function appendEvidenceToSourceItem(item: StudyGroupItem, evidence: StudyEvidence, body: string): void {
  const text = stripSourceAspectPrefix(body)
  const previousPageLabel = item.pageLabel
  if (text && !item.body.includes(text)) {
    // Join evidence fragments with paragraph boundary and normalize the result
    // so CJK-CJK spaces at fragment boundaries are cleaned up
    item.body = item.body
      ? normalizeTextbookDisplayText(`${item.body}\n\n${text}`)
      : text
  }
  item.evidence = mergeStudyEvidence(item.evidence, [evidence])
  item.pageLabel = combinedPageLabel([
    { ...item, pageLabel: previousPageLabel },
    { ...item, pageLabel: evidence.pageLabel },
  ])
}

function getOrCreateSourceGroup(groups: StudyGroup[], title: string): StudyGroup {
  const existing = groups.find((group) => group.title === title)
  if (existing) return existing
  const group: StudyGroup = {
    id: `source-${hashString(title)}`,
    title,
    pageLabel: '',
    items: [],
  }
  groups.push(group)
  return group
}

function getOrCreateSourceItem(group: StudyGroup, title: string, evidence: StudyEvidence): StudyGroupItem {
  const existing = group.items.at(-1)
  if (existing?.title === title) return existing
  const item: StudyGroupItem = {
    id: `source-${hashString(`${group.title}-${title}-${evidence.id || group.items.length}`)}`,
    title,
    body: '',
    pageLabel: evidence.pageLabel,
    evidence: [],
    evidenceOnly: true,
  }
  group.items.push(item)
  return item
}

function isStructuredSourceGroupNode(node: TextbookKnowledgeNode): boolean {
  return node.renderType === 'grouped'
    && node.listItems.length > 0
    && cleanText(node.groupTopic) !== ''
    && node.groupTopic !== 'source_evidence'
}

function pulmonaryFunctionChildBucket(evidence: StudyEvidence): { title: string; order: number } | null {
  const text = cleanText(evidence.text)
  if (!text) return null
  if (/图\d|示意图|NOTES/u.test(text)) return null
  if (/通气功能|阻塞性通气功能|FVC|FEV1|FEV1\/FVC|气流受限|通气功能可逐渐/u.test(text)) {
    return { title: '通气功能检测', order: 10 }
  }
  if (/支气管激发试验|醋甲胆碱|组胺|PD20|PC20|BPT/u.test(text)) {
    return { title: '支气管激发试验（BPT）', order: 20 }
  }
  if (/支气管舒张试验|支气管扩张剂|沙丁胺醇|特布他林|增加≥?12%|增加≥?200ml|可逆性的气道阻塞|BDT/u.test(text)) {
    return { title: '支气管舒张试验（BDT）', order: 30 }
  }
  if (/呼气峰流量|PEF|昼夜变异率|周变异率/u.test(text)) {
    return { title: '呼气峰流量（PEF）及其变异率测定', order: 40 }
  }
  return null
}

function pulmonaryFunctionChildrenFromEvidence(
  node: TextbookKnowledgeNode,
  usedEvidenceIds: Set<string>,
): StudyGroupItem[] {
  const buckets = new Map<string, { order: number; evidence: StudyEvidence[] }>()
  for (const evidence of evidenceForNode(node)) {
    if (usedEvidenceIds.has(evidence.id)) continue
    const bucket = pulmonaryFunctionChildBucket(evidence)
    if (!bucket) continue
    const current = buckets.get(bucket.title)
    if (current) {
      current.evidence.push(evidence)
    } else {
      buckets.set(bucket.title, { order: bucket.order, evidence: [evidence] })
    }
  }

  return Array.from(buckets.entries())
    .sort((a, b) => a[1].order - b[1].order)
    .map(([title, bucket]) => {
      const evidence = bucket.evidence.sort((a, b) => (
        (a.sourceOrder ?? Number.MAX_SAFE_INTEGER) - (b.sourceOrder ?? Number.MAX_SAFE_INTEGER)
      ))
      return {
        id: `${node.id}-pulmonary-${hashString(title)}`,
        title,
        body: joinedEvidenceText(evidence),
        pageLabel: combinedPageLabel(evidence.map((item) => ({
        id: item.id,
        title,
        body: item.text,
        pageLabel: item.pageLabel,
        evidence: [item],
        evidenceOnly: true,
      }))),
        evidence,
        evidenceOnly: true,
      }
    })
}

function structuredSourceItemsForNode(node: TextbookKnowledgeNode): StudyGroupItem[] {
  const nodeEvidence = evidenceForNode(node)
  const usedEvidenceIds = new Set<string>()
  for (const item of node.listItems) {
    for (const id of item.evidenceArtifactIds ?? []) usedEvidenceIds.add(id)
  }

  return node.listItems
    .map((item, index) => {
      const artifactIds = new Set((item.evidenceArtifactIds ?? []).filter(Boolean))
      const itemEvidence = artifactIds.size > 0
        ? nodeEvidence.filter((evidence) => artifactIds.has(evidence.id))
        : []
      const studyItem: StudyGroupItem = {
        id: `${node.id}-structured-${index}`,
        title: cleanText(item.title) || node.title,
        body: joinedEvidenceText(itemEvidence) || stripSourceAspectPrefix(item.body),
        pageLabel: cleanText(item.pageLabel) || node.pageLabel,
        evidence: itemEvidence,
        evidenceOnly: item.publicationState === 'evidence_only',
        contractItem: true,
        children: (item.children ?? []).map((child, childIndex) => (
          itemToDisplayStudyItem(node, child, childIndex, nodeEvidence, `${index}-${childIndex}`)
        )),
      }
      let generatedPulmonaryChildren = false
      if (!cleanText(studyItem.body) && itemEvidence.length === 0) {
        const pulmonaryChildren = pulmonaryFunctionChildrenFromEvidence(node, usedEvidenceIds)
        if (pulmonaryChildren.length > 0) {
          studyItem.children = pulmonaryChildren
          generatedPulmonaryChildren = true
        }
      }
      if (node.groupTopic === 'auxiliary_exam' && !generatedPulmonaryChildren && studyItem.children && studyItem.children.length > 0) {
        const continuationChildren = studyItem.children.filter((child) => !/图\d|示意图|NOTES/u.test(child.body))
        for (const child of continuationChildren) {
          studyItem.body = mergeStudyBody(studyItem.body, child.body)
          studyItem.evidence = mergeStudyEvidence(studyItem.evidence, child.evidence)
        }
        studyItem.pageLabel = combinedPageLabel([studyItem, ...continuationChildren])
        studyItem.children = []
      }
      return studyItem
    })
    .filter((item) => cleanText(item.title) || cleanText(item.body) || (item.children?.length ?? 0) > 0)
}

function sourceGroupTitleForStructuredNode(node: TextbookKnowledgeNode): string {
  return sourceGroupTitleForNode(node)
    ?? GROUP_TOPIC_LABELS[cleanText(node.groupTopic)]
    ?? cleanText(node.title)
    ?? '教材原文'
}

function sourceItemOrder(title: string): number {
  const text = normalizeSourceHeadingTitle(title)
  if (/^痰嗜酸性粒细胞计数$/u.test(text)) return 111
  if (/^外周血嗜酸性粒细胞计数$/u.test(text)) return 112
  if (/^肺功能检查$/u.test(text)) return 113
  if (/^通气功能检测$/u.test(text)) return 114
  if (/^支气管激发试验/u.test(text)) return 115
  if (/^支气管舒张试验/u.test(text)) return 116
  if (/^呼气峰流量/u.test(text)) return 117
  if (/^胸部X线\/CT检查$|^胸部 X 线\/CT 检查$/u.test(text)) return 118
  if (/^特异性变应原检测$/u.test(text)) return 119
  if (/^动脉血气分析$/u.test(text)) return 120
  if (/^呼出气一氧化氮/u.test(text)) return 121
  if (/^定义与概述$|^定义$|^概述$/u.test(text)) return 0
  if (/流行病学/u.test(text)) return 10
  if (/^病因$/u.test(text)) return 20
  if (/^发病机制$/u.test(text)) return 30
  if (/气道免疫/u.test(text)) return 40
  if (/气道炎症/u.test(text)) return 50
  if (/气道高反应/u.test(text)) return 60
  if (/神经调节/u.test(text)) return 70
  if (/病理/u.test(text)) return 80
  if (/症状|临床表现/u.test(text)) return 90
  if (/体征/u.test(text)) return 100
  if (/实验室和其他检查/u.test(text)) return 110
  if (/支气管激发/u.test(text)) return 120
  if (/支气管舒张/u.test(text)) return 130
  if (/变应原/u.test(text)) return 140
  if (/血气/u.test(text)) return 150
  if (/典型哮喘/u.test(text)) return 160
  if (/可变气流受限/u.test(text)) return 170
  if (/分期|急性发作|慢性持续|临床控制/u.test(text)) return 180
  if (/轻度/u.test(text)) return 190
  if (/中度/u.test(text)) return 200
  if (/重度/u.test(text)) return 210
  if (/危重/u.test(text)) return 220
  if (/并发症/u.test(text)) return 230
  if (/治疗目标/u.test(text)) return 240
  if (/危险因素/u.test(text)) return 250
  if (/β2|SABA|LABA/u.test(text)) return 260
  if (/糖皮质激素|ICS/u.test(text)) return 270
  if (/白三烯/u.test(text)) return 280
  if (/茶碱/u.test(text)) return 290
  if (/抗胆碱|LAMA|SAMA/u.test(text)) return 300
  if (/生物制剂|抗IL|抗IgE|TSLP/u.test(text)) return 310
  if (/教育|管理/u.test(text)) return 320
  if (/预后/u.test(text)) return 330
  return 999
}

function sourceGroupOrder(title: string): number {
  switch (title) {
    case '定义与概述': return 0
    case '概述': return 1
    case '流行病学': return 10
    case '分类': return 15
    case '病因与发病机制': return 20
    case '病理': return 30
    case '临床表现': return 40
    case '实验室和其他检查': return 50
    case '辅助检查': return 50
    case '诊断与鉴别诊断': return 60
    case '诊断': return 60
    case '并发症': return 70
    case '治疗': return 80
    case '教育与管理': return 90
    case '预防与预后': return 100
    case '预后': return 110
    default: return 999
  }
}

function compareSourceItems(groupTitle: string, a: StudyGroupItem, b: StudyGroupItem): number {
  if (groupTitle === '治疗') {
    return firstPageNumber(a.pageLabel) - firstPageNumber(b.pageLabel)
      || sourceItemOrder(a.title) - sourceItemOrder(b.title)
  }
  if (groupTitle === '诊断与鉴别诊断') {
    return firstPageNumber(a.pageLabel) - firstPageNumber(b.pageLabel)
      || sourceItemOrder(a.title) - sourceItemOrder(b.title)
  }
  return sourceItemOrder(a.title) - sourceItemOrder(b.title)
    || firstPageNumber(a.pageLabel) - firstPageNumber(b.pageLabel)
}

function normalizeSourceStudyGroup(group: StudyGroup): StudyGroup {
  const items = group.items
    .filter((item) => item.contractItem || cleanText(item.body) || (item.children?.length ?? 0) > 0)
    .sort((a, b) => compareSourceItems(group.title, a, b))
  return {
    ...group,
    items,
    pageLabel: combinedPageLabel(items),
  }
}

function buildSourceEvidenceStudyGroups(detail: TextbookSectionDetail): StudyGroup[] {
  const groups: StudyGroup[] = []
  for (const node of detail.nodes) {
    if (!isStructuredSourceGroupNode(node)) continue
    const groupTitle = sourceGroupTitleForStructuredNode(node)
    if (!groupTitle) continue
    const group = getOrCreateSourceGroup(groups, groupTitle)
    group.items.push(...structuredSourceItemsForNode(node))
    group.pageLabel = combinedPageLabel(group.items)
  }

  let activeGroupTitle = '定义与概述'
  let activeItemTitle = activeGroupTitle

  for (const row of uniqueSourceEvidenceRows(detail)) {
    if (isStructuredSourceGroupNode(row.node)) continue
    const heading = sourceHeadingFromEvidenceText(row.evidence.text)
    const headingGroup = heading?.startsGroup ? sourceGroupTitleFromText(heading.title) : null
    const nodeGroup = sourceGroupTitleForNode(row.node)
    const nextGroupTitle = headingGroup ?? nodeGroup
    if (nextGroupTitle && nextGroupTitle !== activeGroupTitle) {
      activeGroupTitle = nextGroupTitle
      activeItemTitle = heading?.title || sourceItemTitleForNode(row.node, activeGroupTitle)
    }

    if (heading && !heading.startsGroup) {
      activeItemTitle = heading.title || activeGroupTitle
    } else if (heading?.startsGroup) {
      activeItemTitle = heading.title || activeGroupTitle
    }

    const group = getOrCreateSourceGroup(groups, activeGroupTitle)
    const item = getOrCreateSourceItem(group, activeItemTitle, row.evidence)
    appendEvidenceToSourceItem(item, row.evidence, heading?.body || row.evidence.text)
    group.pageLabel = combinedPageLabel(group.items)
  }

  return groups
    .map(normalizeSourceStudyGroup)
    .filter((group) => group.items.length > 0)
    .sort((a, b) => (
      sourceGroupOrder(a.title) - sourceGroupOrder(b.title)
      || firstPageNumber(a.pageLabel) - firstPageNumber(b.pageLabel)
    ))
}

function buildChapterStudyGroupsInternal(
  detail: TextbookSectionDetail,
  options: { compact: boolean; preferStructuredSourceGroups?: boolean },
): StudyGroup[] {
  const grouped = new Map<string, StudyGroup>()
  const orderedNodes = [...detail.nodes].sort((a, b) => nodeOrder(a) - nodeOrder(b))
  let activeTopic = ''

  for (const node of orderedNodes) {
    const title = inferTopicTitle(node, detail.section.sectionTitle, activeTopic)
    const key = groupKey(node, detail.section.sectionTitle, activeTopic)
    if (isAddressableAspectGroupTitle(title)) {
      activeTopic = ''
    } else if (looksLikeStandaloneTopic(title) || !activeTopic) {
      activeTopic = title
    }
    const current = grouped.get(key)
    const aspectTitle = aspectTitleForNode(node)
    const preserveListItemTitles = node.listItems.length > 0
    const items = displayItemsForNode(node, {
      preferStructuredSourceGroups: options.preferStructuredSourceGroups,
    })
      .map((item) => ({
        ...item,
        title: preserveListItemTitles || item.evidenceOnly ? item.title : aspectTitle,
      }))
      .filter((item) => cleanText(item.title) || cleanText(item.body))
    if (items.length === 0) continue

    if (current) {
      current.items.push(...items)
      current.pageLabel = combinedPageLabel(current.items)
    } else {
      grouped.set(key, {
        id: key,
        title,
        pageLabel: combinedPageLabel(items),
        items,
      })
    }
  }

  const groups = Array.from(grouped.values())
    .map((group) => {
      const items = mergeContinuationItems(group.items)
      return {
        ...group,
        items,
        pageLabel: combinedPageLabel(items),
      }
    })
    .filter((group) => group.items.length > 0)

  return options.compact ? compactMinorStudyGroups(groups) : groups
}

export function buildChapterStudyGroups(detail: TextbookSectionDetail): StudyGroup[] {
  return buildChapterStudyGroupsInternal(detail, { compact: true })
}

function studyUnitFromGroup(group: StudyGroup, index: number, chunkIndex = 0): StudyUnit {
  const evidenceOnlyCount = group.items.filter((item) => item.evidenceOnly).length
  const chunkSuffix = chunkIndex > 0 ? `-${chunkIndex + 1}` : ''
  return {
    id: `unit-${index + 1}${chunkSuffix}-${hashString(`${group.title}-${group.pageLabel}-${chunkIndex}`)}`,
    title: group.title,
    pageLabel: group.pageLabel,
    itemCount: group.items.length,
    evidenceOnlyCount,
    groups: [group],
  }
}

function shouldUseChapterLevelStudyUnit(detail: TextbookSectionDetail): boolean {
  return TEXTBOOK_CHAPTER_TITLE_RE.test(cleanText(detail.section.sectionTitle))
}

function chapterLevelStudyUnit(detail: TextbookSectionDetail): StudyUnit | null {
  const groups = buildSourceEvidenceStudyGroups(detail)
  const items = groups.flatMap((group) => group.items)
  if (items.length === 0) return null
  const title = extractStudyChapterLabel(detail.section.sectionTitle) || cleanText(detail.section.sectionTitle)
  return {
    id: `unit-chapter-${hashString(detail.section.id || detail.section.sectionTitle)}`,
    title,
    pageLabel: combinedPageLabel(items) || (detail.section.pageRange ? `p.${detail.section.pageRange}` : ''),
    itemCount: items.length,
    evidenceOnlyCount: items.filter((item) => item.evidenceOnly).length,
    groups,
  }
}

function splitOversizedFallbackGroup(group: StudyGroup, index: number): StudyUnit[] {
  if (group.items.length <= MAX_FALLBACK_STUDY_UNIT_ITEMS) {
    return [studyUnitFromGroup(group, index)]
  }

  const units: StudyUnit[] = []
  for (let start = 0; start < group.items.length; start += FALLBACK_STUDY_UNIT_CHUNK_SIZE) {
    const items = group.items.slice(start, start + FALLBACK_STUDY_UNIT_CHUNK_SIZE)
    const pageLabel = combinedPageLabel(items)
    units.push(
      studyUnitFromGroup(
        {
          ...group,
          id: `${group.id}-chunk-${units.length + 1}`,
          pageLabel,
          items,
        },
        index,
        units.length,
      ),
    )
  }
  return units
}

export function buildChapterStudyUnits(detail: TextbookSectionDetail): StudyUnit[] {
  const catalogUnits = buildCatalogStudyUnits(detail)
  if (catalogUnits.length > 0) return catalogUnits

  if (shouldUseChapterLevelStudyUnit(detail)) {
    const chapterUnit = chapterLevelStudyUnit(detail)
    return chapterUnit ? [chapterUnit] : []
  }

  return buildChapterStudyGroupsInternal(
    detail,
    { compact: true, preferStructuredSourceGroups: true },
  ).flatMap((group, index) => (
    splitOversizedFallbackGroup(group, index)
  ))
}

export function buildChapterCatalogStudyUnits(detail: TextbookSectionDetail): StudyUnit[] {
  const catalogUnits = buildCatalogStudyUnits(detail, { splitOversized: false })
  return catalogUnits.length > 0 ? catalogUnits : buildChapterStudyUnits(detail)
}

export function findChapterStudyUnit(detail: TextbookSectionDetail, unitId: string): StudyUnit | null {
  const currentUnit = buildChapterStudyUnits(detail).find((unit) => unit.id === unitId)
  if (currentUnit) return currentUnit
  return buildCatalogStudyUnits(detail, { splitOversized: false }).find((unit) => unit.id === unitId) ?? null
}
