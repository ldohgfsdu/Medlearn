import {
  PHASE1_VISUAL_EVIDENCE_BUNDLE,
  type Phase1SourceLocator,
} from '@/constants/phase1VisualEvidenceBundle'
import { PHASE1_PAGE_IMAGE_ASSETS } from '@/constants/phase1PageImageAssets'
import { TEXTBOOK_TITLE } from '@/services/textbookService'

export const PHASE1_ASTHMA_SECTION_ID = PHASE1_VISUAL_EVIDENCE_BUNDLE.sectionId

export function isPhase1VisualEvidenceSection(sectionId: string): boolean {
  return sectionId === PHASE1_ASTHMA_SECTION_ID
}

export function resolveSourceLocators(locatorIds: string[]): Phase1SourceLocator[] {
  const byId = PHASE1_VISUAL_EVIDENCE_BUNDLE.sourceLocatorsById
  return locatorIds
    .map((id) => byId[id])
    .filter((loc): loc is Phase1SourceLocator => Boolean(loc))
}

export function resolvePageImageSource(localAssetKey: string): number | null {
  return PHASE1_PAGE_IMAGE_ASSETS[localAssetKey] ?? null
}

export interface PageViewerPayload {
  textbookTitle: string
  pageLabel: string
  pageAssetId: string
  imageSource: number
  imageWidth: number
  imageHeight: number
  locators: Phase1SourceLocator[]
}

export function buildPageViewerPayload(
  locatorIds: string[],
  fallbackPageLabel?: string,
): PageViewerPayload | null {
  const locators = resolveSourceLocators(locatorIds)
  if (locators.length === 0) return null

  const pageLabel = locators[0].pageLabel || fallbackPageLabel || '?'
  const pageAsset =
    PHASE1_VISUAL_EVIDENCE_BUNDLE.pageAssetsById[locators[0].pageAssetId]
  if (!pageAsset) return null

  const imageSource = resolvePageImageSource(pageAsset.localAssetKey)
  if (imageSource == null) return null

  const samePage = locators.every((loc) => loc.pageLabel === pageLabel)
  const highlights = samePage
    ? locators
    : locators.filter((loc) => loc.pageLabel === pageLabel)

  return {
    textbookTitle: TEXTBOOK_TITLE,
    pageLabel,
    pageAssetId: pageAsset.id,
    imageSource,
    imageWidth: pageAsset.imageWidth,
    imageHeight: pageAsset.imageHeight,
    locators: highlights.filter((loc) => (loc.bboxNorm?.length ?? 0) === 4),
  }
}

export function locatorIdsForEvidenceArtifact(
  sectionId: string,
  artifactId: string,
  explicitIds?: string[],
): string[] {
  if (!isPhase1VisualEvidenceSection(sectionId)) return []
  if (explicitIds && explicitIds.length > 0) return explicitIds
  const loc = PHASE1_VISUAL_EVIDENCE_BUNDLE.sourceLocators.find(
    (item) => item.evidenceItemId === artifactId,
  )
  return loc ? [loc.id] : []
}