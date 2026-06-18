import { EV1_DISPLAY_CONTRACT_SECTIONS } from '@/constants/ev1DisplayContracts'
import { supabase } from '@/lib/supabase'

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
}

export interface Ev1DisplayItem {
  title: string
  body: string
  page_label: string
  publication_state: Ev1PublicationState
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
}

export interface TextbookKnowledgeNode {
  id: string
  title: string
  content: string
  renderType: Ev1RenderType
  publicationState: Ev1PublicationState
  qualityBadges: string[]
  listItems: TextbookListItem[]
  evidenceExcerpt: string
  evidenceFull: string
  pageLabel: string
  sourceHeading: string
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

interface KnowledgeSourceSpan {
  artifact_id?: string | null
  source_heading?: string | null
  normalized_aspect?: string | null
  evidence?: string | null
  evidence_items?: string[] | null
  page_start?: number | null
  page_end?: number | null
  provenance?: {
    page_start?: number | null
    page_end?: number | null
    [key: string]: unknown
  } | null
  [key: string]: unknown
}

interface KnowledgeNodeRow {
  id: string
  title: string | null
  content: string | null
  key_points?: string[] | null
  structured_sections?: { title?: string | null; content?: string | null }[] | null
  sub_chapter: string | null
  order_num: number | null
  source_span?: KnowledgeSourceSpan | null
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
  return {
    id: node.id,
    title: cleanText(node.display.title) || '未命名知识点',
    content: cleanText(node.display.body),
    renderType: node.render_type,
    publicationState: node.publication_state,
    qualityBadges: node.quality_badges ?? [],
    listItems: (node.display.items ?? []).map((item) => ({
      title: cleanText(item.title),
      body: cleanText(item.body),
      pageLabel: cleanText(item.page_label),
      publicationState: item.publication_state,
    })),
    evidenceExcerpt: excerpt(evidenceFull, 260),
    evidenceFull,
    pageLabel: cleanText(node.display.page_label),
    sourceHeading: cleanText(node.display.source_heading),
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
  if (EV1_DISPLAY_CONTRACT_SECTIONS.length > 0) {
    return {
      textbookId: TEXTBOOK_ID,
      textbookTitle: TEXTBOOK_TITLE,
      systemTitle: 'EV1 Display Contract',
      partTitle: '已通过 release gate 的本地教材视图契约',
      sections: EV1_DISPLAY_CONTRACT_SECTIONS.map(toSectionSummary),
    }
  }

  const { data, error } = await supabase
    .from('knowledge_nodes')
    .select('id, sub_chapter, chapter')
    .eq('book_id', TEXTBOOK_ID)
    .limit(1000)

  if (error) throw error

  const sections = new Map<string, TextbookSectionSummary>()
  for (const row of data ?? []) {
    const sectionTitle = String(row.sub_chapter ?? '').trim()
    if (!sectionTitle) continue
    const existing = sections.get(sectionTitle)
    sections.set(sectionTitle, {
      id: sectionTitle,
      sectionTitle,
      nodeCount: (existing?.nodeCount ?? 0) + 1,
      organizedCount: existing?.organizedCount ?? 0,
      evidenceOnlyCount: existing?.evidenceOnlyCount ?? 0,
      mergedCount: existing?.mergedCount ?? 0,
      groupedCount: existing?.groupedCount ?? 0,
      pageRange: existing?.pageRange ?? '?',
      pageStart: existing?.pageStart ?? 0,
      pageEnd: existing?.pageEnd ?? 0,
      partTitle: String(row.chapter ?? ''),
      systemTitle: String(row.chapter ?? ''),
    })
  }

  return {
    textbookId: TEXTBOOK_ID,
    textbookTitle: TEXTBOOK_TITLE,
    systemTitle: '远端知识库',
    partTitle: 'knowledge_nodes',
    sections: Array.from(sections.values()),
  }
}

function contentFromNode(row: KnowledgeNodeRow): string {
  const structured = row.structured_sections?.filter((item) => cleanText(item.content)) ?? []
  if (structured.length > 0) {
    return structured
      .map((item) => {
        const title = cleanText(item.title)
        const content = cleanText(item.content)
        return title ? `${title}: ${content}` : content
      })
      .join('\n')
  }

  if (cleanText(row.content)) return cleanText(row.content)
  return row.key_points?.map(cleanText).filter(Boolean).join('；') ?? ''
}

function evidenceFromNode(row: KnowledgeNodeRow): string {
  const items = row.source_span?.evidence_items?.map(cleanText).filter(Boolean) ?? []
  if (items.length > 0) return items.join(' ')
  return cleanText(row.source_span?.evidence)
}

function pageLabelFromSource(source: KnowledgeSourceSpan | null | undefined): string {
  const pageStart = source?.page_start ?? source?.provenance?.page_start
  const pageEnd = source?.page_end ?? source?.provenance?.page_end ?? pageStart
  if (typeof pageStart !== 'number') return 'p.?'
  return pageStart === pageEnd ? `p.${pageStart}` : `pp.${pageStart}-${pageEnd}`
}

function toLegacyKnowledgeNode(row: KnowledgeNodeRow): TextbookKnowledgeNode {
  const evidence = evidenceFromNode(row)
  return {
    id: row.id,
    title: cleanText(row.title) || '未命名知识点',
    content: excerpt(contentFromNode(row), 320),
    renderType: 'normal',
    publicationState: 'organized',
    qualityBadges: ['textbook_grounded', 'page_bound'],
    listItems: [],
    evidenceExcerpt: excerpt(evidence, 260),
    evidenceFull: evidence,
    pageLabel: pageLabelFromSource(row.source_span),
    sourceHeading: cleanText(row.source_span?.source_heading) || cleanText(row.source_span?.normalized_aspect),
    artifactIds: row.source_span?.artifact_id ? [row.source_span.artifact_id] : [],
    sourceNodeIds: [row.id],
  }
}

export async function getSectionDetail(sectionId: string): Promise<TextbookSectionDetail | null> {
  const displaySection = displaySectionById(sectionId)
  if (displaySection) {
    const summary = toSectionSummary(displaySection)
    return {
      section: summary,
      textbookTitle: displaySection.textbookTitle,
      systemTitle: displaySection.systemTitle,
      partTitle: displaySection.partTitle,
      nodes: displaySection.nodes.map(toDisplayKnowledgeNode),
    }
  }

  const { data, error } = await supabase
    .from('knowledge_nodes')
    .select('id, title, content, key_points, structured_sections, sub_chapter, order_num, source_span')
    .eq('book_id', TEXTBOOK_ID)
    .eq('sub_chapter', sectionId)
    .order('order_num', { ascending: true })
    .limit(500)

  if (error) throw error
  if (!data || data.length === 0) return null

  const rows = data as KnowledgeNodeRow[]
  const summary: TextbookSectionSummary = {
    id: sectionId,
    sectionTitle: sectionId,
    nodeCount: rows.length,
    organizedCount: rows.length,
    evidenceOnlyCount: 0,
    mergedCount: 0,
    groupedCount: 0,
    pageRange: '?',
    pageStart: 0,
    pageEnd: 0,
    partTitle: '',
    systemTitle: '',
  }

  return {
    section: summary,
    textbookTitle: TEXTBOOK_TITLE,
    systemTitle: '',
    partTitle: '',
    nodes: rows.map(toLegacyKnowledgeNode),
  }
}
