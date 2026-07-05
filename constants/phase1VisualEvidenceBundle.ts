export type Phase1PageAsset = {
  id: string
  textbookId: string
  textbookVersion: string
  pageLabel: string
  pdfPageIndex: number
  pdfPageIndexBasis: string
  imageWidth: number
  imageHeight: number
  localAssetKey: string
  relativePath?: string
  bboxNormRule?: { origin: string; yFlip: boolean; note?: string }
}

export type Phase1SourceLocator = {
  id: string
  evidenceItemId: string
  locatorSource?: string
  sourceEvidenceId?: string
  sourceArtifactId?: string
  pageLabel: string
  pdfPageIndex: number
  pageAssetId: string
  bboxPdf?: number[]
  bboxNorm?: number[]
  bboxNormLines?: number[][]
  rawText: string
  confidence: number
}

export type Phase1VisualEvidenceBundle = {
  version: string
  sectionId: string
  textbookId: string
  generatedAt: string
  pageAssets: Phase1PageAsset[]
  sourceLocators: Phase1SourceLocator[]
  sourceLocatorsById: Record<string, Phase1SourceLocator>
  pageAssetsById: Record<string, Phase1PageAsset>
}

export const PHASE1_VISUAL_EVIDENCE_BUNDLE: Phase1VisualEvidenceBundle = {
  version: 'phase1-visual-evidence-bundle-v1',
  sectionId: '',
  textbookId: 'internal-medicine-10',
  generatedAt: '',
  pageAssets: [],
  sourceLocators: [],
  sourceLocatorsById: {},
  pageAssetsById: {},
}
