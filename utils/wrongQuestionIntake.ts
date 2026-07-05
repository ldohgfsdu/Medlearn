import type { TextbookSectionDetail } from '@/services/textbookService'
import { buildChapterStudyUnits, type StudyGroupItem } from '@/utils/textbookStudy'

export interface WrongQuestionCandidate {
  id: string
  sectionId: string
  sectionTitle: string
  partTitle: string
  unitId: string
  unitTitle: string
  catalogTitle?: string
  itemId: string
  groupTitle: string
  itemTitle: string
  pageLabel: string
  evidenceExcerpt: string
  evidenceOnly: boolean
  matchedTerms: string[]
  score: number
}

const CLINICAL_CUE_TERMS = [
  'COPD',
  'PTE',
  'ARDS',
  'CAP',
  'HAP',
  'VAP',
  'pneumonia',
  'asthma',
  '病毒性肺炎',
  '病毒',
  'viral pneumonia',
  '衣原体肺炎',
  '真菌性肺炎',
  '细菌性肺炎',
  '大叶性肺炎',
  '肺炎球菌肺炎',
  '肺炎链球菌肺炎',
  '肺炎球菌',
  '肺炎链球菌',
  '肺实变',
  '支气管呼吸音',
  '肺炎',
  '肺真菌病',
  '肺结核',
  '肺气肿',
  '肺癌',
  '过敏性肺炎',
  '肺炎支原体肺炎',
  '肺炎支原体',
  '心包积液',
  '肺脓肿',
  '哮喘',
  '慢阻肺',
  '肺栓塞',
  '气胸',
  '胸腔积液',
  '呼吸衰竭',
  '咳嗽',
  '咳痰',
  '咯血',
  '胸痛',
  '发热',
  '呼吸困难',
  '全身酸痛',
  '倦怠',
  '白细胞',
  'WBC',
  'IgM',
  '特异性IgM',
  '血清',
  '血清学',
  '抗体',
  '叩诊',
  '浊音',
  '实音',
  '鼓音',
  '过清音',
  '诊断',
  '鉴别诊断',
  '治疗',
  '检查',
  '临床表现',
  '病因',
  '发病机制',
  '分类',
  '并发症',
  '预后',
  '青霉素',
  '用药',
  '剂量',
  '肌注',
  '肌肉注射',
  '静脉注射',
  '静脉滴注',
  '静滴',
  '输液',
  '过敏',
]

const GENERAL_ASPECT_TERMS = new Set([
  '诊断',
  '鉴别诊断',
  '治疗',
  '检查',
  '临床表现',
  '病因',
  '发病机制',
  '分类',
  '并发症',
  '预后',
  '用药',
  '剂量',
  '肌注',
  '肌肉注射',
  '静脉注射',
  '静脉滴注',
  '静滴',
  '输液',
  '过敏',
])

const OPTION_LINE_PATTERN = /^\s*[A-EＡ-Ｅ][.．、]\s*/i
const OPTION_EXPLANATION_PATTERN = /[A-EＡ-Ｅ]\s*错/
const DISEASE_ANCHOR_TERMS = new Set([
  'pneumonia',
  'asthma',
  '病毒性肺炎',
  '病毒',
  'viral pneumonia',
  '衣原体肺炎',
  '真菌性肺炎',
  '细菌性肺炎',
  '大叶性肺炎',
  '肺炎球菌肺炎',
  '肺炎链球菌肺炎',
  '肺炎球菌',
  '肺炎链球菌',
  '肺炎',
  '肺真菌病',
  '肺结核',
  '肺气肿',
  '肺癌',
  '过敏性肺炎',
  '肺炎支原体肺炎',
  '肺炎支原体',
  '心包积液',
  '肺脓肿',
  '哮喘',
  '慢阻肺',
  '肺栓塞',
  '气胸',
  '胸腔积液',
  '呼吸衰竭',
])
const TREATMENT_ANCHOR_TERMS = new Set([
  '治疗',
  '青霉素',
  '用药',
  '剂量',
  '肌注',
  '肌肉注射',
  '静脉注射',
  '静脉滴注',
  '静滴',
  '输液',
])
const PHYSICAL_SIGN_ANCHOR_TERMS = new Set([
  '支气管呼吸音',
  '叩诊',
  '浊音',
  '实音',
  '鼓音',
  '过清音',
])
const RESPIRATORY_SIGNAL_TERMS = new Set([
  '咳嗽',
  '咳痰',
  '咯血',
  '胸痛',
  '呼吸困难',
  '支气管呼吸音',
])
const RESPIRATORY_CONTEXT_TERMS = new Set([
  '肺',
  '肺炎',
  '支气管',
  '呼吸',
  '胸膜',
  '气胸',
])
const SPECIFIC_REQUIRED_TERMS = new Set([
  '青霉素',
])
const STRONG_TREATMENT_SOURCE_PHRASES = new Set([
  '首选青霉素',
  '用药途径及剂量',
  '青霉素G',
])
const GENERIC_DISEASE_ANCHOR_TERMS = new Set([
  'pneumonia',
  '病毒',
  '肺炎',
])
const SPECIFIC_PATHOGEN_TERMS = [
  'SARS',
  '新冠',
  'H5N1',
  'H1N1',
  '禽流感',
]

function cleanText(value: string | null | undefined): string {
  return (value ?? '').replace(/\s+/g, ' ').trim()
}

function normalizeText(value: string): string {
  return cleanText(value)
    .toLowerCase()
    .replace(/[，。；：、！？,.!?;:()[\]{}"'`“”‘’<>《》]/g, ' ')
    .replace(/\s+/g, ' ')
    .trim()
}

function unique<T>(items: T[]): T[] {
  return Array.from(new Set(items))
}

export function extractWrongQuestionTerms(input: string): string[] {
  const normalized = normalizeText(signalText(input))
  if (normalized.length < 2) return []

  const terms: string[] = []
  for (const cue of CLINICAL_CUE_TERMS) {
    if (normalized.includes(cue.toLowerCase())) terms.push(cue)
  }

  const tokenTerms = normalized
    .split(/\s+/)
    .map((token) => token.trim())
    .filter((token) => (
      token.length >= 2 &&
      token.length <= 24 &&
      !/\d/.test(token)
    ))

  return unique([...terms, ...tokenTerms])
}

function extractOptionDiseaseAnchorTerms(input: string): string[] {
  const optionText = input
    .split(/\r?\n/)
    .filter((line) => OPTION_LINE_PATTERN.test(line))
    .map(normalizeText)
    .join('\n')
  if (!optionText) return []

  return Array.from(DISEASE_ANCHOR_TERMS).filter((term) => (
    term.length >= 3 &&
    optionText.includes(term.toLowerCase())
  ))
}

function signalText(input: string): string {
  const withoutOptionLines = input
    .split(/\r?\n/)
    .filter((line) => !OPTION_LINE_PATTERN.test(line))
    .join('\n')
  const withoutOptionExplanations = withoutOptionLines
    .split(/(?<=[。！？!?;；])/)
    .filter((sentence) => !OPTION_EXPLANATION_PATTERN.test(sentence))
    .join('')
  return cleanText(withoutOptionExplanations || withoutOptionLines || input)
}

function itemText(item: StudyGroupItem, includeChildren = true): string {
  const children = item.children ?? []
  return [
    item.title,
    item.body,
    item.pageLabel,
    ...item.evidence.map((evidence) => evidence.text),
    ...(includeChildren ? children.map((child) => itemText(child, true)) : []),
  ].join('\n')
}

function flattenStudyItems(item: StudyGroupItem): StudyGroupItem[] {
  return [item, ...(item.children ?? []).flatMap(flattenStudyItems)]
}

function excerpt(value: string, maxLength = 160): string {
  const text = cleanText(value)
  if (text.length <= maxLength) return text
  return `${text.slice(0, maxLength - 1)}…`
}

function scoreMatch(query: string, terms: string[], target: string): { score: number; matchedTerms: string[] } {
  const normalizedQuery = normalizeText(query)
  const normalizedTarget = normalizeText(target)
  const matchedTerms = terms.filter((term) => normalizedTarget.includes(term.toLowerCase()))
  let score = 0

  if (normalizedTarget.includes(normalizedQuery)) score += 80
  for (const term of matchedTerms) {
    const normalizedTerm = term.toLowerCase()
    if (normalizedTarget.startsWith(normalizedTerm)) score += 12
    score += normalizedTerm.length >= 4 ? 8 : 5
  }

  return { score, matchedTerms }
}

function firstPageNumber(pageLabel: string): number {
  const match = pageLabel.match(/\d+/)
  return match ? Number(match[0]) : Number.POSITIVE_INFINITY
}

function hasConflictingClinicalCue(target: string, matchedTerms: string[]): boolean {
  const normalizedTarget = normalizeText(target)
  const normalizedMatched = new Set(matchedTerms.map((term) => term.toLowerCase()))
  const matchedDiseaseTerms = matchedTerms.filter((term) => DISEASE_ANCHOR_TERMS.has(term))
  if (matchedDiseaseTerms.length === 0) return false

  return Array.from(DISEASE_ANCHOR_TERMS).some((term) => {
    const normalizedTerm = term.toLowerCase()
    const relatedMatchedTerm = Array.from(normalizedMatched).some((matchedTerm) => (
      matchedTerm.length >= 2 &&
      (
        normalizedTerm.includes(matchedTerm) ||
        matchedTerm.includes(normalizedTerm)
      )
    ))
    return (
      !normalizedMatched.has(normalizedTerm) &&
      !relatedMatchedTerm &&
      normalizedTarget.includes(normalizedTerm)
    )
  })
}

function hasAnyTerm(terms: string[], anchors: Set<string>): boolean {
  return terms.some((term) => anchors.has(term))
}

function targetHasAnyTerm(target: string, anchors: Set<string>): boolean {
  const normalizedTarget = normalizeText(target)
  return Array.from(anchors).some((term) => normalizedTarget.includes(term.toLowerCase()))
}

function missingSpecificRequiredTerm(terms: string[], targetText: string): boolean {
  const normalizedTarget = normalizeText(targetText)
  return terms
    .filter((term) => SPECIFIC_REQUIRED_TERMS.has(term))
    .some((term) => !normalizedTarget.includes(term.toLowerCase()))
}

function missingSpecificTreatmentDiseaseAnchor(terms: string[], candidateContext: string): boolean {
  if (!hasAnyTerm(terms, TREATMENT_ANCHOR_TERMS)) return false
  if (
    terms.some((term) => STRONG_TREATMENT_SOURCE_PHRASES.has(term)) &&
    targetHasAnyTerm(candidateContext, STRONG_TREATMENT_SOURCE_PHRASES)
  ) {
    return false
  }

  const specificTerms = terms.filter((term) => (
    DISEASE_ANCHOR_TERMS.has(term) &&
    !GENERIC_DISEASE_ANCHOR_TERMS.has(term) &&
    term.length >= 2
  ))
  return specificTerms.length > 0 && !targetHasRelatedSpecificDiseaseTerm(candidateContext, specificTerms)
}

function hasUnmentionedSpecificPathogen(query: string, candidateContext: string): boolean {
  const normalizedQuery = normalizeText(query)
  const normalizedContext = normalizeText(candidateContext)
  return SPECIFIC_PATHOGEN_TERMS.some((term) => {
    const normalizedTerm = term.toLowerCase()
    return normalizedContext.includes(normalizedTerm) && !normalizedQuery.includes(normalizedTerm)
  })
}

function diagnosticIntentScore(query: string, targetText: string): number {
  const normalizedQuery = normalizeText(query)
  const normalizedTarget = normalizeText(targetText)
  const hasDiagnosticIntent = (
    normalizedQuery.includes('可能是') ||
    normalizedQuery.includes('诊断') ||
    normalizedQuery.includes('符合')
  )
  if (!hasDiagnosticIntent) return 0

  return (
    normalizedTarget.includes('诊断') ||
    normalizedTarget.includes('鉴别诊断') ||
    normalizedTarget.includes('早期诊断')
  ) ? 24 : 0
}

function targetHasRelatedDiseaseTerm(target: string, terms: string[]): boolean {
  const normalizedTarget = normalizeText(target)
  return terms
    .filter((term) => DISEASE_ANCHOR_TERMS.has(term))
    .some((term) => {
      const normalizedTerm = term.toLowerCase()
      return normalizedTarget.includes(normalizedTerm) || (
        normalizedTerm.length >= 4 &&
        Array.from(DISEASE_ANCHOR_TERMS).some((anchor) => {
          const normalizedAnchor = anchor.toLowerCase()
          return (
            normalizedTarget.includes(normalizedAnchor) &&
            (normalizedAnchor.includes(normalizedTerm) || normalizedTerm.includes(normalizedAnchor))
          )
        })
      )
    })
}

function targetHasRelatedSpecificDiseaseTerm(target: string, terms: string[]): boolean {
  const normalizedTarget = normalizeText(target)
  return terms.some((term) => {
    const normalizedTerm = term.toLowerCase()
    return (
      normalizedTarget.includes(normalizedTerm) ||
      (
        (normalizedTerm.includes('肺炎球菌') || normalizedTerm.includes('肺炎链球菌')) &&
        (normalizedTarget.includes('肺炎球菌') || normalizedTarget.includes('肺炎链球菌'))
      )
    )
  })
}

function missesRequiredAnchor(terms: string[], targetText: string, candidateContext: string): boolean {
  return (
    (hasAnyTerm(terms, DISEASE_ANCHOR_TERMS) && !targetHasRelatedDiseaseTerm(candidateContext, terms)) ||
    (hasAnyTerm(terms, RESPIRATORY_SIGNAL_TERMS) && !targetHasAnyTerm(candidateContext, RESPIRATORY_CONTEXT_TERMS)) ||
    (hasAnyTerm(terms, TREATMENT_ANCHOR_TERMS) && !targetHasAnyTerm(targetText, TREATMENT_ANCHOR_TERMS)) ||
    (hasAnyTerm(terms, PHYSICAL_SIGN_ANCHOR_TERMS) && !targetHasAnyTerm(targetText, PHYSICAL_SIGN_ANCHOR_TERMS))
  )
}

function anchorScore(terms: string[], targetText: string, candidateContext: string): number {
  const normalizedTarget = normalizeText(targetText)
  const normalizedContext = normalizeText(candidateContext)
  let score = 0
  for (const term of terms) {
    const normalizedTerm = term.toLowerCase()
    if (TREATMENT_ANCHOR_TERMS.has(term) && normalizedTarget.includes(normalizedTerm)) score += 14
    if (PHYSICAL_SIGN_ANCHOR_TERMS.has(term) && normalizedTarget.includes(normalizedTerm)) score += 14
    if (DISEASE_ANCHOR_TERMS.has(term) && normalizedContext.includes(normalizedTerm)) score += normalizedTerm.length >= 4 ? 10 : 4
  }
  return score
}

export function locateWrongQuestionCandidates(
  question: string,
  details: TextbookSectionDetail[],
  limit = 5,
): WrongQuestionCandidate[] {
  const querySignal = signalText(question)
  const terms = unique([
    ...extractWrongQuestionTerms(querySignal),
    ...extractOptionDiseaseAnchorTerms(question),
  ])
  if (terms.length === 0) return []

  const candidates: WrongQuestionCandidate[] = []
  for (const detail of details) {
    const sectionScored = scoreMatch(querySignal, terms, [
      detail.section.sectionTitle,
      detail.partTitle,
      detail.systemTitle,
    ].join('\n'))
    const units = buildChapterStudyUnits(detail)

    for (const unit of units) {
      const unitScored = scoreMatch(querySignal, terms, unit.title)
      for (const group of unit.groups) {
        const groupScored = scoreMatch(querySignal, terms, group.title)
        for (const item of group.items) {
          for (const matchedItem of flattenStudyItems(item)) {
            const targetText = itemText(matchedItem, false)
            const scored = scoreMatch(querySignal, terms, targetText)
            const evidenceText = matchedItem.evidence.map((evidence) => evidence.text).find(Boolean) ?? matchedItem.body
            const matchedTerms = unique([
              ...sectionScored.matchedTerms,
              ...unitScored.matchedTerms,
              ...groupScored.matchedTerms,
              ...scored.matchedTerms,
            ])
            const candidateContext = [
              detail.section.sectionTitle,
              detail.partTitle,
              detail.systemTitle,
              unit.title,
              group.title,
              targetText,
            ].join('\n')
            const score = (
              scored.score +
              unitScored.score +
              groupScored.score +
              Math.round(sectionScored.score / 2) +
              anchorScore(terms, targetText, candidateContext) +
              diagnosticIntentScore(querySignal, targetText)
            )
            if (
              scored.score <= 0 ||
              matchedTerms.length < Math.min(2, terms.length) ||
              missesRequiredAnchor(terms, targetText, candidateContext) ||
              missingSpecificRequiredTerm(terms, targetText) ||
              missingSpecificTreatmentDiseaseAnchor(terms, candidateContext) ||
              hasUnmentionedSpecificPathogen(querySignal, candidateContext) ||
              hasConflictingClinicalCue(candidateContext, matchedTerms) ||
              !evidenceText ||
              !matchedItem.pageLabel
            ) {
              continue
            }

            candidates.push({
              id: `${detail.section.id}:${unit.id}:${matchedItem.id}`,
              sectionId: detail.section.id,
              sectionTitle: detail.section.sectionTitle,
              partTitle: detail.partTitle,
              unitId: unit.id,
              unitTitle: unit.title,
              catalogTitle: unit.catalogTitle,
              itemId: matchedItem.id,
              groupTitle: group.title,
              itemTitle: matchedItem.title,
              pageLabel: matchedItem.pageLabel,
              evidenceExcerpt: excerpt(evidenceText),
              evidenceOnly: matchedItem.evidenceOnly,
              matchedTerms,
              score,
            })
          }
        }
      }
    }
  }

  return candidates
    .sort((a, b) =>
      b.score - a.score ||
      firstPageNumber(a.pageLabel) - firstPageNumber(b.pageLabel) ||
      a.sectionTitle.localeCompare(b.sectionTitle, 'zh-CN') ||
      a.unitTitle.localeCompare(b.unitTitle, 'zh-CN')
    )
    .slice(0, limit)
}
