import { EV1_DISPLAY_CONTRACT_SECTIONS } from '@/constants/ev1DisplayContracts'

export const TEXTBOOK_ID = 'internal-medicine-10'
export const TEXTBOOK_TITLE = '内科学（第10版）'

export type Ev1RenderType = 'normal' | 'merged' | 'grouped' | 'evidence_only'
export type Ev1PublicationState = 'organized' | 'evidence_only'

export interface Ev1EvidenceItem {
  artifact_id: string
  text: string
  page_start: number | null
  page_end: number | null
  source_order: number | null
  sourceLocatorIds?: string[]
  pageLabel?: string
}

export interface Ev1DisplayItem {
  title: string
  body: string
  page_label: string
  publication_state: Ev1PublicationState
  evidence_artifact_ids?: string[]
  children?: Ev1DisplayItem[]
}

export interface Ev1DisplayNode {
  id: string
  render_type: Ev1RenderType
  publication_state: Ev1PublicationState
  quality_badges: string[]
  display: {
    title: string
    body: string
    page_label: string
    source_heading: string
    items?: Ev1DisplayItem[]
  }
  source_node_ids: string[]
  evidence_items: Ev1EvidenceItem[]
  merge?: {
    strategy: string
    child_node_ids: string[]
    child_artifact_ids: string[]
  }
  group?: {
    strategy: string
    topic: string
    child_view_ids: string[]
    child_node_ids: string[]
    child_artifact_ids: string[]
  }
}

export interface Ev1DisplayContractSection {
  id: string
  textbookId: string
  textbookTitle: string
  systemTitle: string
  partTitle: string
  sectionTitle: string
  nodeCount: number
  pageStart: number
  pageEnd: number
  summary: {
    organized?: number
    evidence_only?: number
    merged?: number
    grouped?: number
  }
  nodes: Ev1DisplayNode[]
}

export interface TextbookSectionSummary {
  id: string
  sectionTitle: string
  nodeCount: number
  organizedCount: number
  evidenceOnlyCount: number
  mergedCount: number
  groupedCount: number
  pageRange: string
  pageStart: number
  pageEnd: number
  partTitle: string
  systemTitle: string
  previewOnly?: boolean
}

export interface TextbookTree {
  textbookId: string
  textbookTitle: string
  systemTitle: string
  partTitle: string
  sections: TextbookSectionSummary[]
}

export interface TextbookListItem {
  title: string
  body: string
  pageLabel: string
  publicationState: Ev1PublicationState
  evidenceArtifactIds?: string[]
  children?: TextbookListItem[]
}

export interface TextbookEvidenceItem {
  artifactId: string
  text: string
  pageStart: number | null
  pageEnd: number | null
  sourceOrder: number | null
  pageLabel: string
  sourceLocatorIds?: string[]
  printedPageLabel?: string
  pageReferenceKind: TextbookPageReferenceKind
}

export type TextbookPageReferenceKind = 'pdf' | 'printed' | 'source'

export interface TextbookKnowledgeNode {
  id: string
  title: string
  content: string
  renderType: Ev1RenderType
  publicationState: Ev1PublicationState
  qualityBadges: string[]
  listItems: TextbookListItem[]
  evidenceItems: TextbookEvidenceItem[]
  evidenceExcerpt: string
  evidenceFull: string
  pageLabel: string
  sourceHeading: string
  groupTopic?: string
  artifactIds: string[]
  sourceNodeIds: string[]
}

export interface TextbookSectionDetail {
  section: TextbookSectionSummary
  textbookTitle: string
  systemTitle: string
  partTitle: string
  nodes: TextbookKnowledgeNode[]
}

function cleanText(value: string | null | undefined): string {
  return (value ?? '').replace(/\s+/g, ' ').trim()
}

function excerpt(value: string, maxLength: number): string {
  const text = cleanText(value)
  if (text.length <= maxLength) return text
  return `${text.slice(0, maxLength - 1)}…`
}

function pageRange(pageStart: number, pageEnd: number): string {
  if (!pageStart && !pageEnd) return '?'
  return pageStart === pageEnd ? String(pageStart) : `${pageStart}-${pageEnd}`
}

export function evidencePageLabel(item: Ev1EvidenceItem): string {
  if (typeof item.page_start !== 'number') return 'p.?'
  const end = typeof item.page_end === 'number' ? item.page_end : item.page_start
  return item.page_start === end ? `p.${item.page_start}` : `p.${item.page_start}-${end}`
}

export function formatTextbookPageReference(
  value: string | null | undefined,
  kind: TextbookPageReferenceKind,
): string {
  const label = cleanText(value).replace(/^p\.?/iu, '')
  if (!label || label === '?') return '页码待确认'
  if (kind === 'printed') return `教材页 ${label}`
  if (kind === 'pdf') return `PDF 页 ${label}`
  return `来源页 ${label}`
}

function toSectionSummary(section: Ev1DisplayContractSection): TextbookSectionSummary {
  return {
    id: section.id,
    sectionTitle: section.sectionTitle,
    nodeCount: section.nodeCount,
    organizedCount: section.summary.organized ?? 0,
    evidenceOnlyCount: section.summary.evidence_only ?? 0,
    mergedCount: section.summary.merged ?? 0,
    groupedCount: section.summary.grouped ?? 0,
    pageRange: pageRange(section.pageStart, section.pageEnd),
    pageStart: section.pageStart,
    pageEnd: section.pageEnd,
    partTitle: section.partTitle,
    systemTitle: section.systemTitle,
    previewOnly: true,
  }
}

function toDisplayKnowledgeNode(node: Ev1DisplayNode): TextbookKnowledgeNode {
  const evidenceItems = node.evidence_items ?? []
  const evidenceFull = evidenceItems.map((item) => cleanText(item.text)).filter(Boolean).join('\n\n')
  const toListItem = (item: Ev1DisplayItem): TextbookListItem => ({
    title: cleanText(item.title),
    body: cleanText(item.body),
    pageLabel: cleanText(item.page_label),
    publicationState: item.publication_state,
    evidenceArtifactIds: (item.evidence_artifact_ids ?? []).map(cleanText).filter(Boolean),
    children: (item.children ?? []).map(toListItem),
  })
  return {
    id: node.id,
    title: cleanText(node.display.title) || '未命名知识点',
    content: cleanText(node.display.body),
    renderType: node.render_type,
    publicationState: node.publication_state,
    qualityBadges: node.quality_badges ?? [],
    listItems: (node.display.items ?? []).map(toListItem),
    evidenceItems: evidenceItems.map((item) => ({
      artifactId: item.artifact_id,
      text: cleanText(item.text),
      pageStart: item.page_start,
      pageEnd: item.page_end,
      sourceOrder: item.source_order,
      pageLabel: cleanText(item.pageLabel) || evidencePageLabel(item),
      printedPageLabel: cleanText(item.pageLabel) || undefined,
      pageReferenceKind: cleanText(item.pageLabel) ? 'printed' : 'pdf',
      sourceLocatorIds: item.sourceLocatorIds ?? [],
    })),
    evidenceExcerpt: excerpt(evidenceFull, 260),
    evidenceFull,
    pageLabel: cleanText(node.display.page_label),
    sourceHeading: cleanText(node.display.source_heading),
    groupTopic: cleanText(node.group?.topic),
    artifactIds: evidenceItems.map((item) => item.artifact_id).filter(Boolean),
    sourceNodeIds: node.source_node_ids ?? [],
  }
}

function displaySectionById(sectionId: string): Ev1DisplayContractSection | null {
  return EV1_DISPLAY_CONTRACT_SECTIONS.find((section) => section.id === sectionId) ?? null
}

export function getRespiratorySectionTitle(sectionId: string): string | null {
  return displaySectionById(sectionId)?.sectionTitle ?? null
}

export async function getTextbookTree(): Promise<TextbookTree> {
  return {
    textbookId: TEXTBOOK_ID,
    textbookTitle: TEXTBOOK_TITLE,
    systemTitle: 'EV1 Display Contract',
    partTitle: '已通过 release gate 的本地教材视图契约',
    sections: EV1_DISPLAY_CONTRACT_SECTIONS.map(toSectionSummary),
  }
}

export async function getSectionDetail(sectionId: string): Promise<TextbookSectionDetail | null> {
  const displaySection = displaySectionById(sectionId)
  if (!displaySection) return null

  return {
    section: toSectionSummary(displaySection),
    textbookTitle: displaySection.textbookTitle,
    systemTitle: displaySection.systemTitle,
    partTitle: displaySection.partTitle,
    nodes: displaySection.nodes.map(toDisplayKnowledgeNode),
  }
}
