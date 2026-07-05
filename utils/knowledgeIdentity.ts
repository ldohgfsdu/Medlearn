export type ResolutionStatus = 'confirmed' | 'review_required' | 'rejected'
export type ResolvedBy = 'pipeline' | 'script' | 'manual'
export type CatalogNodeType = 'textbook' | 'system' | 'category' | 'overview' | 'disease'
export type ContentStatus = 'available' | 'in_progress' | 'unavailable'

export type KnowledgeContentClass =
  | 'confirmed_disease'
  | 'non_disease_knowledge'
  | 'suspected_disease'
  | 'invalid'

export type DiseaseAspect =
  | 'definition'
  | 'epidemiology'
  | 'etiology'
  | 'pathogenesis'
  | 'clinical_manifestation'
  | 'diagnosis'
  | 'differential_diagnosis'
  | 'treatment'
  | 'prognosis'
  | 'prevention'
  | 'other'

export type ChainValidationStatus =
  | 'pending'
  | 'valid'
  | 'invalid_structure'
  | 'invalid_evidence'
  | 'invalid_medical_logic'
  | 'review_required'

export interface ChapterSection {
  chapter_section_id: string
  textbook_series_id: string
  source_textbook_version_ids: string[]
  catalog_path: string
  display_title: string
  parent_section_id?: string | null
  order_index: number
}

export interface DiseaseEntity {
  disease_id: string
  canonical_disease_name: string
  canonical_key: string
  aliases: string[]
  source_textbook_series_id: string
  source_chapter_section_ids: string[]
  confidence: number
  resolution_status: ResolutionStatus
  resolution_reason?: string | null
  resolved_at?: string | null
  resolved_by?: ResolvedBy | null
  resolution_version: number
  normalization_version: number
  node_type: 'disease'
  content_status: ContentStatus
}

const ASPECT_RULES: [DiseaseAspect, RegExp][] = [
  ['definition', /定义|概念|概述/u],
  ['epidemiology', /流行病学/u],
  ['etiology', /病因|危险因素/u],
  ['pathogenesis', /发病机制|病理生理|机制/u],
  ['clinical_manifestation', /临床表现|临床特征|症状|体征/u],
  ['differential_diagnosis', /鉴别诊断|诊断与鉴别/u],
  ['diagnosis', /诊断|检查|检验|影像/u],
  ['treatment', /治疗|用药|手术|处理原则/u],
  ['prognosis', /预后|并发症/u],
  ['prevention', /预防/u],
]

export function normalizeCatalogPath(value: string): string {
  return value
    .normalize('NFKC')
    .replace(/[|｜]/gu, '/')
    .replace(/\s+/gu, '')
    .replace(/\/+/gu, '/')
    .replace(/^\/|\/$/gu, '')
}

export function normalizeDiseaseName(value: string): string {
  return value
    .normalize('NFKC')
    .trim()
    .replace(/^第[一二三四五六七八九十百零〇\d]+(?:章|节)\s*/u, '')
    .replace(/\s+/gu, '')
    .replace(/[，。；：、（）()【】《》"'“”‘’]/gu, '')
    .toLowerCase()
}

export function mapDiseaseAspect(rawAspect: string | null | undefined): DiseaseAspect {
  const value = rawAspect?.trim() ?? ''
  for (const [aspect, pattern] of ASPECT_RULES) {
    if (pattern.test(value)) return aspect
  }
  return 'other'
}

export function isUserNavigableContentClass(
  value: KnowledgeContentClass | null | undefined,
): value is 'confirmed_disease' | 'non_disease_knowledge' {
  return value === 'confirmed_disease' || value === 'non_disease_knowledge'
}
