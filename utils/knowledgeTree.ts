import { compareTextbookOrder } from '@/utils/knowledgeCatalog'
import type { KnowledgeNavigationNode } from '@/utils/routeBuilders'

export interface KnowledgeTreeNode extends KnowledgeNavigationNode {
  id: string
  title: string
  chapter?: string | null
  sub_chapter?: string | null
  level?: number | null
  order_num?: number | null
  content?: string | null
  key_points?: string[] | null
  structured_sections?: Array<{ title?: string; content?: string }> | null
  /** 展示层解析后的方面标签（过滤跨病种节点、消解泛化 aspect 后写入） */
  displayAspect?: string
}

export interface TopicAspect {
  label: string
  nodeId: string
  title: string
  order_num: number
}

/** 教材目录「节」下的「小节」——独立疾病（如「肺炎支原体肺炎」） */
export interface KnowledgeSubsection {
  name: string
  nodeCount: number
  hasData: boolean
  target?: KnowledgeNavigationNode
}

/** 教材目录中的「节」——章下的学习单元（如「第四节 肺炎支原体…」） */
export interface KnowledgeSection {
  name: string
  catalogTitle: string
  subsections: KnowledgeSubsection[]
  nodeCount: number
  hasData: boolean
  target?: KnowledgeNavigationNode
}

export interface DiseaseEntryTarget {
  sectionName: string
  subsectionName: string
  catalogUnit?: string
}

/** @deprecated 使用 KnowledgeSection */
export type KnowledgeTreeSection = KnowledgeSection
/** @deprecated 使用 KnowledgeSection */
export type KnowledgeTopic = KnowledgeSection

export interface KnowledgeChapter {
  name: string
  /** 章下的节 */
  sections: KnowledgeSection[]
  /** PDF 目录中该章是否拆分为「节」 */
  hasCatalogUnits: boolean
  hasData: boolean
  target?: KnowledgeNavigationNode
}

export interface KnowledgePart {
  name: string
  chapters: KnowledgeChapter[]
}

export interface TextbookCatalogSubsection {
  title: string
  node_type?: 'overview'
  content_status?: 'available' | 'in_progress' | 'unavailable'
  overview_slug?: string
}

export interface TextbookCatalogUnit {
  title: string
  subsections?: TextbookCatalogSubsection[]
}

export interface TextbookCatalogChapter {
  title: string
  units?: TextbookCatalogUnit[]
}

export interface TextbookCatalogPart {
  chapterTitle: string
  sections: TextbookCatalogChapter[]
}

const SECTION_UNIT_TITLE_RE = /^第[一二三四五六七八九十百零\d]+节\s*[|｜]\s*(.+)$/u

function sortKnowledgeNodes(nodes: KnowledgeTreeNode[]): KnowledgeTreeNode[] {
  return [...nodes].sort((a, b) => {
    const orderDiff = (a.order_num ?? 0) - (b.order_num ?? 0)
    if (orderDiff !== 0) return orderDiff
    return a.title.localeCompare(b.title, 'zh-CN')
  })
}

/** 从「第X章 标题」提取章名主体，如「支气管哮喘」 */
export function extractChapterLabel(chapterName: string): string {
  return chapterName.replace(/^第[一二三四五六七八九十百零\d]+章\s*/u, '').trim()
}

/** 教材目录「节」标题转展示名：「第一节 | 概述」→「第一节　概述」 */
export function formatSectionUnitTitle(unitTitle: string): string {
  return unitTitle.replace(/\s*[|｜]\s*/u, '　').trim()
}

/** 从教材目录「节」标题提取匹配用主体，如「第二节 | 急性白血病」→「急性白血病」 */
export function extractSectionUnitEntity(unitTitle: string): string {
  const match = unitTitle.trim().match(SECTION_UNIT_TITLE_RE)
  return match ? match[1].trim() : unitTitle.trim()
}

/** 将节标题中的疾病组拆成多个小节，如「肺炎支原体肺炎、衣原体肺炎与肺军团病」 */
export function splitDiseaseGroup(entity: string): string[] {
  const parts = entity
    .replace(/与/g, '、')
    .split('、')
    .map((part) => part.trim())
    .filter(Boolean)
  return parts.length > 0 ? parts : [entity.trim()]
}

/** 从教材目录「节」推导其下的小节（独立疾病）列表 */
export function deriveSubsectionEntities(
  unitTitle: string,
  chapterName: string,
  catalogSubsections: TextbookCatalogSubsection[] = [],
): string[] {
  if (catalogSubsections.length > 0) {
    return catalogSubsections.map((item) => item.title.trim()).filter(Boolean)
  }

  const entity = extractSectionUnitEntity(unitTitle)
  if (/概述|总论/u.test(entity)) {
    return [extractChapterLabel(chapterName)]
  }

  const split = splitDiseaseGroup(entity)
  return split.length > 1 ? split : [entity]
}

const DISEASE_SUBTYPE_PREFIX_RE = /^(急性|慢性|原发|继发|早期|晚期|难治性|初治|复发)(.+)$/u

/** 目录匹配只做规范化精确匹配；疾病别名合并由实体解析层负责。 */
export function diseaseNamesMatch(left: string, right: string): boolean {
  const a = left.trim()
  const b = right.trim()
  if (!a || !b) return false
  if (a === b) return true

  // 父类病名不能匹配亚型：白血病 ≠ 急性白血病
  const subtypeA = a.match(DISEASE_SUBTYPE_PREFIX_RE)
  const subtypeB = b.match(DISEASE_SUBTYPE_PREFIX_RE)
  if (subtypeA && subtypeA[2] === b) return false
  if (subtypeB && subtypeB[2] === a) return false

  const compact = (value: string) => {
    const normalized = value.replace(/\s+/g, '').replace(/菌/g, '')
    const duplicatedPneumonia = normalized.match(/^肺炎(.+肺炎)$/u)
    return duplicatedPneumonia ? duplicatedPneumonia[1] : normalized
  }
  const ca = compact(a)
  const cb = compact(b)
  if (ca === cb) return true

  return false
}

/** 从节点标题拆出「主题」与「方面」，如「支气管哮喘的定义」 */
export function parseTopicAspect(
  title: string,
  chapterName: string,
): { topic: string; aspect: string } {
  const trimmed = title.trim()
  const match = trimmed.match(/^(.+?)的(.+)$/u)
  if (match) {
    return { topic: match[1].trim(), aspect: match[2].trim() }
  }

  const chapterLabel = extractChapterLabel(chapterName)
  return { topic: chapterLabel || trimmed, aspect: trimmed }
}

const GENERIC_ASPECT_LABELS = new Set([
  '治疗方案',
  '治疗措施',
  '治疗药物',
  '治疗目标',
  '使用方法',
  '给药方式',
  '联合用药',
  '作用机制',
  '分类',
])

const CROSS_DISEASE_NODE_RE = /变应性鼻炎|过敏性结膜炎|哮喘合并|结膜炎合并哮喘/u

function readParentEntity(node: KnowledgeTreeNode): string {
  const sourceSpan = node as KnowledgeTreeNode & {
    source_span?: { parent_entity?: string | null } | null
  }
  return sourceSpan.source_span?.parent_entity?.trim() ?? ''
}

/** 过滤 LLM 从治疗段扩写出的跨病种组合节点（教材原文中通常不存在） */
export function isCrossDiseaseExpansionNode(
  node: KnowledgeTreeNode,
  sectionName: string,
): boolean {
  const title = node.title.trim()
  const parentEntity = readParentEntity(node)
  const haystack = `${title}\n${parentEntity}`

  if (!CROSS_DISEASE_NODE_RE.test(haystack)) return false

  if (title.startsWith(`${sectionName}的`)) return false
  if (parentEntity === sectionName) return false

  const asthmaAliases = new Set([sectionName, '哮喘', '支气管哮喘'])
  if (asthmaAliases.has(parentEntity) && !/治疗(变应性鼻炎|过敏性结膜炎)/u.test(title)) {
    return false
  }

  return true
}

/** 同一章内多个节点共用「治疗方案」等泛化 aspect 时，改用节点标题作展示标签 */
export function resolveAspectDisplayLabel(
  node: KnowledgeTreeNode,
  chapterName: string,
  aspectUsage: Map<string, number>,
): string {
  const parsed = parseTopicAspect(node.title, chapterName)
  const structuredAspect = node.structured_sections?.[0]?.title?.trim()
  const aspect = structuredAspect || parsed.aspect
  const count = aspectUsage.get(aspect) ?? 0

  if (count > 1 && GENERIC_ASPECT_LABELS.has(aspect)) {
    return node.title.trim()
  }

  if (
    parsed.topic === extractChapterLabel(chapterName)
    && parsed.aspect === node.title.trim()
    && structuredAspect
  ) {
    return structuredAspect
  }

  return aspect
}

/** 按医学阅读顺序给「方面」排序，仅用于已有内容的相对顺序 */
export function getAspectSortWeight(label: string): number {
  const rules: Array<[RegExp, number]> = [
    [/^定义$/u, 10],
    [/^概述$/u, 15],
    [/流行病学/u, 20],
    [/病因/u, 30],
    [/发病机制/u, 40],
    [/病理/u, 50],
    [/临床表现|临床特征/u, 60],
    [/症状|体征/u, 65],
    [/检查|影像学|实验室/u, 70],
    [/诊断标准/u, 80],
    [/^诊断$/u, 82],
    [/鉴别/u, 85],
    [/治疗|用药|药物|方案/u, 90],
    [/预后/u, 95],
    [/预防/u, 100],
    [/并发症/u, 105],
  ]

  for (const [pattern, weight] of rules) {
    if (pattern.test(label)) return weight
  }
  return 200
}

function sortAspects(aspects: TopicAspect[]): TopicAspect[] {
  return [...aspects].sort((a, b) => {
    const weightDiff = getAspectSortWeight(a.label) - getAspectSortWeight(b.label)
    if (weightDiff !== 0) return weightDiff
    const orderDiff = a.order_num - b.order_num
    if (orderDiff !== 0) return orderDiff
    return a.label.localeCompare(b.label, 'zh-CN')
  })
}

function buildAspectsFromNodes(
  nodes: KnowledgeTreeNode[],
  chapterName: string,
): TopicAspect[] {
  const aspectUsage = new Map<string, number>()
  for (const node of nodes) {
    const parsed = parseTopicAspect(node.title, chapterName)
    const aspect = node.structured_sections?.[0]?.title?.trim() || parsed.aspect
    aspectUsage.set(aspect, (aspectUsage.get(aspect) ?? 0) + 1)
  }

  return sortAspects(
    nodes.map((node) => {
      const parsed = parseTopicAspect(node.title, chapterName)
      const label = resolveAspectDisplayLabel(node, chapterName, aspectUsage)
      return {
        label,
        nodeId: node.id,
        title: node.title,
        order_num: node.order_num ?? 0,
        aspect: parsed.aspect,
      }
    }).map(({ aspect: _aspect, ...aspect }) => aspect),
  )
}

function readNodeDiseaseEntity(node: KnowledgeTreeNode, chapterName: string): string {
  const parentEntity = readParentEntity(node)
  if (parentEntity) return parentEntity
  return parseTopicAspect(node.title, chapterName).topic
}

/** 判断节点是否属于某一「小节」（独立疾病） */
export function nodeMatchesSubsection(
  node: KnowledgeTreeNode,
  chapterName: string,
  subsectionEntity: string,
): boolean {
  if (isCrossDiseaseExpansionNode(node, subsectionEntity)) return false

  const chapterLabel = extractChapterLabel(chapterName)
  const parentEntity = readParentEntity(node)
  const { topic } = parseTopicAspect(node.title, chapterName)

  // 概述类小节只收录章名主体本身，避免「白血病」吞掉「急性白血病」等亚型
  if (subsectionEntity === chapterLabel) {
    return topic === chapterLabel || parentEntity === chapterLabel
  }

  if (diseaseNamesMatch(topic, subsectionEntity)) return true
  if (diseaseNamesMatch(parentEntity, subsectionEntity)) return true
  if (diseaseNamesMatch(node.title, subsectionEntity)) return true

  return false
}

/** 判断节点是否属于教材目录中的某一「节」 */
export function nodeMatchesSectionUnit(
  node: KnowledgeTreeNode,
  chapterName: string,
  unitTitle: string,
): boolean {
  const entity = extractSectionUnitEntity(unitTitle)
  const diseases = splitDiseaseGroup(entity)

  if (diseases.length > 1) {
    return diseases.some((disease) => nodeMatchesSubsection(node, chapterName, disease))
  }

  if (/概述|总论/u.test(entity)) {
    return nodeMatchesSubsection(node, chapterName, extractChapterLabel(chapterName))
  }

  return nodeMatchesSubsection(node, chapterName, entity)
}

function collectDistinctDiseaseEntities(
  nodes: KnowledgeTreeNode[],
  chapterName: string,
): string[] {
  const seen = new Set<string>()
  const entities: string[] = []

  for (const node of nodes) {
    const entity = readNodeDiseaseEntity(node, chapterName)
    if (!entity || seen.has(entity)) continue
    seen.add(entity)
    entities.push(entity)
  }

  return entities
}

function buildSubsectionsForUnit(
  matchedNodes: KnowledgeTreeNode[],
  chapterName: string,
  unitTitle: string,
  catalogSubsections: TextbookCatalogSubsection[] = [],
): KnowledgeSubsection[] {
  let entities = deriveSubsectionEntities(unitTitle, chapterName, catalogSubsections)

  if (entities.length === 1 && matchedNodes.length > 0) {
    const fromNodes = collectDistinctDiseaseEntities(matchedNodes, chapterName)
    if (fromNodes.length > 1) {
      entities = fromNodes
    }
  }

  return entities.map((entity) => {
    const nodes = matchedNodes.filter((node) => nodeMatchesSubsection(node, chapterName, entity))
    const catalogSubsection = catalogSubsections.find((item) => item.title === entity)
    return {
      name: entity,
      nodeCount: nodes.length,
      hasData: nodes.length > 0,
      target: nodes[0] ? {
        content_class: nodes[0].content_class,
        node_type: nodes[0].node_type,
        content_status: nodes[0].content_status,
        disease_id: nodes[0].disease_id,
        chapter_section_id: nodes[0].chapter_section_id,
      } : catalogSubsection?.overview_slug ? {
        node_type: catalogSubsection.node_type,
        content_status: catalogSubsection.content_status,
        overview_slug: catalogSubsection.overview_slug,
      } : undefined,
    }
  })
}

function summarizeSection(subsections: KnowledgeSubsection[]): Pick<KnowledgeSection, 'nodeCount' | 'hasData'> {
  const nodeCount = subsections.reduce((sum, subsection) => sum + subsection.nodeCount, 0)
  return {
    nodeCount,
    hasData: subsections.some((subsection) => subsection.hasData),
  }
}

export function groupNodesIntoSections(
  nodes: KnowledgeTreeNode[],
  chapterName: string,
): KnowledgeSection[] {
  const chapterLabel = extractChapterLabel(chapterName)
  const subsections = buildSubsectionsForUnit(nodes, chapterName, chapterLabel)
  const summary = summarizeSection(subsections)

  return [{
    name: chapterLabel,
    catalogTitle: chapterName,
    subsections,
    target: subsections[0]?.target,
    ...summary,
  }]
}

function buildSectionsForChapter(
  chapterNodes: KnowledgeTreeNode[],
  chapterName: string,
  catalogUnits: TextbookCatalogUnit[] = [],
): KnowledgeSection[] {
  if (catalogUnits.length > 0) {
    return catalogUnits.map((unit) => {
      const matchedNodes = sortKnowledgeNodes(
        chapterNodes.filter((node) => {
          const explicitSubsectionMatch = unit.subsections?.some((subsection) => (
            nodeMatchesSubsection(node, chapterName, subsection.title)
          ))
          return explicitSubsectionMatch
            || nodeMatchesSectionUnit(node, chapterName, unit.title)
        }),
      )
      const subsections = buildSubsectionsForUnit(
        matchedNodes,
        chapterName,
        unit.title,
        unit.subsections ?? [],
      )
      return {
        name: formatSectionUnitTitle(unit.title),
        catalogTitle: unit.title,
        subsections,
        target: subsections[0]?.target,
        ...summarizeSection(subsections),
      }
    })
  }

  return groupNodesIntoSections(chapterNodes, chapterName)
}

export function buildSubjectKnowledgeTree(
  nodes: KnowledgeTreeNode[],
  catalogParts: TextbookCatalogPart[] = [],
): KnowledgePart[] {
  const nodesByPartChapter = new Map<string, Map<string, KnowledgeTreeNode[]>>()

  for (const node of nodes) {
    const partName = node.chapter || '未分类'
    const chapterName = node.sub_chapter || '其他'
    if (!nodesByPartChapter.has(partName)) {
      nodesByPartChapter.set(partName, new Map())
    }
    const chapterMap = nodesByPartChapter.get(partName)!
    const bucket = chapterMap.get(chapterName) ?? []
    bucket.push(node)
    chapterMap.set(chapterName, bucket)
  }

  const partNames = catalogParts.length > 0
    ? catalogParts.map((part) => part.chapterTitle)
    : [...nodesByPartChapter.keys()].sort((a, b) => compareTextbookOrder(a, b, '篇'))

  return partNames.map((partName) => {
    const chapterMap = nodesByPartChapter.get(partName) ?? new Map()
    const catalogPart = catalogParts.find((part) => part.chapterTitle === partName)
    const catalogChapters = catalogPart?.sections ?? []
    const chapterNames = catalogChapters.length > 0
      ? catalogChapters.map((section) => section.title)
      : [...chapterMap.keys()].sort((a, b) => compareTextbookOrder(a, b, '章'))

    const chapters: KnowledgeChapter[] = chapterNames.map((chapterName) => {
      const chapterNodes = sortKnowledgeNodes(chapterMap.get(chapterName) ?? [])
      const catalogChapter = catalogChapters.find((section) => section.title === chapterName)
      const sections = buildSectionsForChapter(
        chapterNodes,
        chapterName,
        catalogChapter?.units ?? [],
      )
      const hasCatalogUnits = (catalogChapter?.units?.length ?? 0) > 0

      return {
        name: chapterName,
        sections,
        hasCatalogUnits,
        hasData: chapterNodes.length > 0,
        target: chapterNodes[0] ? {
          content_class: chapterNodes[0].content_class,
          node_type: chapterNodes[0].node_type,
          content_status: chapterNodes[0].content_status,
          disease_id: chapterNodes[0].disease_id,
          chapter_section_id: chapterNodes[0].chapter_section_id,
        } : undefined,
      }
    })

    return { name: partName, chapters }
  })
}

/** 单独成章：整章对应一个疾病，目录不再展开「节」 */
export function isChapterLeaf(chapter: KnowledgeChapter): boolean {
  return !chapter.hasCatalogUnits
}

/** 单独成节：该节只对应一个疾病，目录不再展开「小节」 */
export function isSectionLeaf(section: KnowledgeSection): boolean {
  return section.subsections.length === 1
}

export function getChapterEntryTarget(chapter: KnowledgeChapter): DiseaseEntryTarget {
  const section = chapter.sections[0]
  const subsection = section?.subsections[0]
  const chapterLabel = extractChapterLabel(chapter.name)

  return {
    sectionName: isChapterLeaf(chapter) ? '' : (section?.name ?? chapterLabel),
    subsectionName: subsection?.name ?? chapterLabel,
    catalogUnit: section?.catalogTitle,
  }
}

export function getSectionEntryTarget(section: KnowledgeSection): DiseaseEntryTarget {
  const subsection = section.subsections[0]

  return {
    sectionName: section.name,
    subsectionName: subsection?.name ?? extractSectionUnitEntity(section.catalogTitle),
    catalogUnit: section.catalogTitle,
  }
}

export function filterSectionNodes(
  nodes: KnowledgeTreeNode[],
  chapterName: string,
  subsectionName: string,
  catalogUnitTitle?: string,
): KnowledgeTreeNode[] {
  const scoped = nodes.filter((node) => {
    if (node.sub_chapter !== chapterName) return false
    if (catalogUnitTitle && !nodeMatchesSectionUnit(node, chapterName, catalogUnitTitle)) {
      return false
    }
    return nodeMatchesSubsection(node, chapterName, subsectionName)
  })

  const aspectUsage = new Map<string, number>()
  for (const node of scoped) {
    const parsed = parseTopicAspect(node.title, chapterName)
    const aspect = node.structured_sections?.[0]?.title?.trim() || parsed.aspect
    aspectUsage.set(aspect, (aspectUsage.get(aspect) ?? 0) + 1)
  }

  return sortKnowledgeNodes(
    scoped.map((node) => ({
      ...node,
      displayAspect: resolveAspectDisplayLabel(node, chapterName, aspectUsage),
    })),
  )
}

/** @deprecated 使用 filterSectionNodes */
export const filterTopicNodes = filterSectionNodes

/** @deprecated 使用 groupNodesIntoSections */
export const groupNodesIntoTopics = groupNodesIntoSections
