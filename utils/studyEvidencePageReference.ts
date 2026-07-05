import {
  formatTextbookPageReference,
  type TextbookPageReferenceKind,
} from '@/services/textbookService'
import {
  buildPageViewerPayload,
  isPhase1VisualEvidenceSection,
  locatorIdsForEvidenceArtifact,
} from '@/services/phase1VisualEvidenceService'

export interface StudyEvidencePageReferenceInput {
  id: string
  pageLabel: string
  sourceLocatorIds?: string[]
  pageReferenceKind: TextbookPageReferenceKind
}

export interface StudyEvidenceCompactInput extends StudyEvidencePageReferenceInput {
  text: string
}

function normalizePrintedPageLabel(value: string): string {
  return value.replace(/^p\.?/iu, '').trim()
}

/** Shared with EvidenceEntry in app/textbook/[sectionId]/unit/[unitId].tsx */
export function resolveStudyEvidencePageReference(
  sectionId: string,
  item: StudyEvidencePageReferenceInput,
  fallbackPageLabel = '',
) {
  const locatorIds = locatorIdsForEvidenceArtifact(
    sectionId,
    item.id,
    item.sourceLocatorIds,
  )
  const fallbackLabel = normalizePrintedPageLabel(fallbackPageLabel)
  const itemLabel = normalizePrintedPageLabel(item.pageLabel)
  const viewerPayload = isPhase1VisualEvidenceSection(sectionId) && locatorIds.length > 0
    ? buildPageViewerPayload(locatorIds, itemLabel || fallbackLabel)
    : null
  const resolvedPrintedLabel = normalizePrintedPageLabel(viewerPayload?.pageLabel ?? '')
  const showPageViewer = Boolean(
    viewerPayload
    && resolvedPrintedLabel
    && resolvedPrintedLabel !== '?',
  )
  const label = showPageViewer
    ? resolvedPrintedLabel
    : itemLabel || fallbackLabel
  const pageReferenceKind: TextbookPageReferenceKind = showPageViewer
    ? 'printed'
    : item.pageReferenceKind
  const viewerActionLabel = showPageViewer
    ? formatPageViewerActionLabel(resolvedPrintedLabel)
    : null
  return {
    locatorIds,
    showPageViewer,
    pageReferenceKind,
    pageReference: formatTextbookPageReference(label, pageReferenceKind),
    viewerPageLabel: showPageViewer ? resolvedPrintedLabel : label,
    viewerActionLabel,
  }
}

/** Phase 1 PageViewer CTA copy per PHASE1_VISUAL_EVIDENCE_SOURCE_LOOP.md (Step 5). */
export function formatPageViewerActionLabel(pageLabel: string): string | null {
  const normalized = normalizePrintedPageLabel(pageLabel)
  if (!normalized || normalized === '?') return null
  return `教材原文 P${normalized}`
}

export type CompactEvidenceSourceKind = 'page_viewer' | 'page_reference'

export interface CompactEvidenceSourceEntry {
  kind: CompactEvidenceSourceKind
  locatorIds: string[]
  pageReference: string
  showPageViewer: boolean
  viewerActionLabel: string | null
  viewerPageLabel: string
}

export function compactStudyText(value: string): string {
  return value.replace(/\s+/g, ' ').trim()
}

export function bodyMatchesStudyEvidence(
  body: string,
  evidence: StudyEvidenceCompactInput[],
): boolean {
  const availableEvidence = evidence.filter((item) => compactStudyText(item.text))
  if (availableEvidence.length === 0) return false
  const evidenceText = availableEvidence.map((item) => item.text).join('\n\n')
  return compactStudyText(body) === compactStudyText(evidenceText)
}

/** Compact source entry when body already equals evidence text (no duplicate body). */
export function resolveCompactEvidenceSourceEntry(
  sectionId: string,
  item: StudyEvidenceCompactInput,
  fallbackPageLabel = '',
): CompactEvidenceSourceEntry | null {
  const resolved = resolveStudyEvidencePageReference(sectionId, item, fallbackPageLabel)
  if (resolved.showPageViewer && resolved.viewerActionLabel) {
    return {
      kind: 'page_viewer',
      locatorIds: resolved.locatorIds,
      pageReference: resolved.pageReference,
      showPageViewer: true,
      viewerActionLabel: resolved.viewerActionLabel,
      viewerPageLabel: resolved.viewerPageLabel,
    }
  }
  if (resolved.pageReference !== '页码待确认') {
    return {
      kind: 'page_reference',
      locatorIds: resolved.locatorIds,
      pageReference: resolved.pageReference,
      showPageViewer: false,
      viewerActionLabel: null,
      viewerPageLabel: resolved.viewerPageLabel,
    }
  }
  return null
}

export function resolveCompactEvidenceSourceEntries(
  sectionId: string,
  evidence: StudyEvidenceCompactInput[],
  fallbackPageLabel = '',
): CompactEvidenceSourceEntry[] {
  return evidence
    .filter((item) => compactStudyText(item.text))
    .map((item) => resolveCompactEvidenceSourceEntry(sectionId, item, fallbackPageLabel))
    .filter((entry): entry is CompactEvidenceSourceEntry => Boolean(entry))
}

/**
 * Deduplicate compact evidence source entries by viewerPageLabel.
 *
 * When multiple evidence items resolve to the same printed page (e.g., three
 * evidence items all on P31), merge their locatorIds into a single entry so
 * only one "教材原文 P31" button is shown. Page-viewer entries take precedence
 * over page-reference entries for the same page label.
 */
export function dedupeCompactEvidenceSourceEntries(
  entries: CompactEvidenceSourceEntry[],
): CompactEvidenceSourceEntry[] {
  const byPageLabel = new Map<string, CompactEvidenceSourceEntry>()
  for (const entry of entries) {
    const key = entry.viewerPageLabel
    const existing = byPageLabel.get(key)
    if (!existing) {
      byPageLabel.set(key, { ...entry, locatorIds: [...entry.locatorIds] })
      continue
    }
    // Merge locatorIds (deduplicated, preserving order)
    const seen = new Set(existing.locatorIds)
    for (const id of entry.locatorIds) {
      if (!seen.has(id)) {
        existing.locatorIds.push(id)
        seen.add(id)
      }
    }
    // page_viewer takes precedence over page_reference for the same page
    if (existing.kind === 'page_reference' && entry.kind === 'page_viewer') {
      existing.kind = 'page_viewer'
      existing.showPageViewer = true
      existing.viewerActionLabel = entry.viewerActionLabel
      existing.pageReference = entry.pageReference
    }
  }
  return Array.from(byPageLabel.values())
}