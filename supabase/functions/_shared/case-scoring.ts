// Pure scoring logic shared by Edge Functions and client-side report types.
export interface DifferentialItem {
  diagnosis: string
  aliases?: string[]
  keyDiscriminator: string
  mustExclude: boolean
  supportAgainst: 'support' | 'against'
}

export interface TreatmentItem {
  action: string
  isCritical: boolean
  aliases?: string[]
}

export interface DangerousTreatment {
  action: string
  penalty: number
  aliases?: string[]
}

export interface GroundTruth {
  diagnosis: {
    primary: string
    primaryAliases: string[]
    icd10: string
  }
  differentials: DifferentialItem[]
  criticalEvidence: {
    forDiagnosis: {
      fromHistory: string[]
      fromExam: string[]
      fromTests: string[]
    }
  }
  treatment: {
    immediate: TreatmentItem[]
    definitive: TreatmentItem[]
    dangerous: DangerousTreatment[]
  }
}

export interface ScoringRubric {
  diagnosis: {
    weight: number
    exactMatch: number
    partialMatch: number
    categoryMatch: number
    hitDifferential: number
    wrong: number
  }
  differential: {
    weight: number
    threeOrMoreWithReasoning: number
    threeOrMore: number
    two: number
    one: number
    none: number
    missingCritical: number
  }
  evidence: {
    weight: number
    coverageWeight: number
    associationWeight: number
    interpretationWeight: number
  }
  treatment: {
    weight: number
    criticalCoverageWeight: number
    safetyWeight: number
    reasonablenessWeight: number
  }
}

export interface CaseSubmission {
  primaryDiagnosis: string
  differentials: Array<{ diagnosis: string; reasoning?: string }>
  evidence: string[]
  treatments: string[]
  confidence?: 1 | 2 | 3
  uncertainty?: string
}

export interface MatchDetail {
  submitted: string
  matched: string | null
  matchType: 'exact' | 'synonym' | 'partial' | 'category' | 'differential' | 'none'
  score: number
  feedback: string
}

export interface ScoreDimension {
  score: number
  maxScore: number
  analysis: string
  details: MatchDetail[]
}

export interface ScoreReport {
  totalScore: number
  grade: 'excellent' | 'good' | 'fair' | 'poor'
  diagnosis: ScoreDimension
  differential: ScoreDimension
  evidence: ScoreDimension
  treatment: ScoreDimension
  strengths: string[]
  weaknesses: string[]
  recommendations: string[]
}

const SYNONYM_GROUPS = [
  ['stemi', 'st段抬高型心肌梗死', '急性前壁心梗', 'st elevation mi', '急性st段抬高型心梗'],
  ['nstemi', '非st段抬高型心肌梗死', 'non-stemi', '非st段抬高型心梗'],
  ['ami', '急性心肌梗死', 'acute mi', 'heart attack', '心梗', '急性心梗'],
  ['pe', '肺栓塞', 'pulmonary embolism'],
  ['dka', '糖尿病酮症酸中毒', 'diabetic ketoacidosis'],
  ['copd', '慢性阻塞性肺疾病', '慢阻肺'],
  ['uti', '尿路感染', '泌尿系感染'],
  ['dvt', '深静脉血栓', '深静脉血栓形成'],
]

const NEGATION_WORDS = ['不', '没有', '无', '避免', '不要', '不用', '禁止', '忌', '非']
const MEDICAL_KEYWORDS = [
  '诊断',
  '鉴别',
  '排除',
  '支持',
  '证据',
  '检查',
  '治疗',
  '症状',
  '体征',
  '病理',
  '生理',
  '机制',
  '预后',
  '并发症',
  '禁忌',
  '适应证',
  '指南',
]
const DISEASE_CATEGORIES = [
  '心肌梗死',
  '心力衰竭',
  '心律失常',
  '心绞痛',
  '肺炎',
  '肺栓塞',
  '哮喘',
  'copd',
  '糖尿病',
  '甲亢',
  '甲减',
  '脑卒中',
  '脑梗',
  '脑出血',
  '阑尾炎',
  '胆囊炎',
  '胰腺炎',
  '肾衰竭',
  '尿路感染',
]

function normalize(text: string): string {
  return text
    .trim()
    .toLowerCase()
    .replace(/[\uff01-\uff5e]/g, (character) =>
      String.fromCharCode(character.charCodeAt(0) - 0xfee0),
    )
    .replace(
      /[\u3000-\u303f\uff00\uff0f\uff1a-\uff20\uff3b-\uff40\uff5b-\uff65\u2018-\u201f\u2026\u2014\u3001\u3002]/g,
      '',
    )
    .replace(/[\s\-_]/g, '')
}

function levenshtein(left: string, right: string): number {
  const matrix = Array.from({ length: left.length + 1 }, (_, row) =>
    Array.from({ length: right.length + 1 }, (_, column) =>
      row === 0 ? column : column === 0 ? row : 0,
    ),
  )

  for (let row = 1; row <= left.length; row += 1) {
    for (let column = 1; column <= right.length; column += 1) {
      matrix[row][column] =
        left[row - 1] === right[column - 1]
          ? matrix[row - 1][column - 1]
          : Math.min(
              matrix[row - 1][column - 1],
              matrix[row][column - 1],
              matrix[row - 1][column],
            ) + 1
    }
  }

  return matrix[left.length][right.length]
}

function similarity(left: string, right: string): number {
  const maxLength = Math.max(left.length, right.length)
  return maxLength === 0 ? 1 : 1 - levenshtein(left, right) / maxLength
}

function fuzzyMatch(left: string, right: string): boolean {
  const normalizedLeft = normalize(left)
  const normalizedRight = normalize(right)
  if (!normalizedLeft || !normalizedRight) return false
  return (
    normalizedLeft === normalizedRight ||
    normalizedLeft.includes(normalizedRight) ||
    normalizedRight.includes(normalizedLeft) ||
    similarity(normalizedLeft, normalizedRight) > 0.8
  )
}

function isSynonym(left: string, right: string): boolean {
  return SYNONYM_GROUPS.some((group) => {
    const terms = group.map(normalize)
    return terms.includes(left) && terms.includes(right)
  })
}

function matchesDiagnosis(
  submitted: string,
  diagnosis: string,
  aliases: string[] = [],
): boolean {
  const normalized = normalize(submitted)
  return [diagnosis, ...aliases].some((candidate) => {
    const normalizedCandidate = normalize(candidate)
    return normalized === normalizedCandidate || isSynonym(normalized, normalizedCandidate)
  })
}

function evaluateReasoning(reasoning = ''): number {
  if (reasoning.length < 5) return 0
  const keywordCount = MEDICAL_KEYWORDS.filter((keyword) =>
    reasoning.toLowerCase().includes(keyword),
  ).length
  if (keywordCount >= 2 || reasoning.length > 30) return 2
  if (keywordCount >= 1 || reasoning.length > 15) return 1
  return 0
}

function scoreDiagnosis(
  submitted: string,
  groundTruth: GroundTruth,
  rubric: ScoringRubric,
): ScoreDimension {
  const maxScore = rubric.diagnosis.weight
  const normalized = normalize(submitted)
  const primary = normalize(groundTruth.diagnosis.primary)
  const aliases = groundTruth.diagnosis.primaryAliases.map(normalize)

  if (normalized === primary || aliases.includes(normalized)) {
    return { score: rubric.diagnosis.exactMatch, maxScore, analysis: '诊断完全正确。', details: [] }
  }
  if (isSynonym(normalized, primary) || aliases.some((alias) => isSynonym(normalized, alias))) {
    return { score: rubric.diagnosis.exactMatch, maxScore, analysis: '诊断正确（同义词匹配）。', details: [] }
  }

  const longer = normalized.length > primary.length ? normalized : primary
  const shorter = normalized.length > primary.length ? primary : normalized
  const partialScore = longer.includes(shorter)
    ? shorter.length / Math.max(longer.length, 1)
    : similarity(normalized, primary)
  if (partialScore > 0.7) {
    return {
      score: rubric.diagnosis.partialMatch,
      maxScore,
      analysis: '诊断方向正确，但表述不够精确。',
      details: [],
    }
  }

  if (DISEASE_CATEGORIES.some((category) => normalized.includes(category) && primary.includes(category))) {
    return {
      score: rubric.diagnosis.categoryMatch,
      maxScore,
      analysis: '疾病分类接近，但具体诊断不正确。',
      details: [],
    }
  }

  const differential = groundTruth.differentials.find((item) =>
    matchesDiagnosis(submitted, item.diagnosis, item.aliases),
  )
  if (differential) {
    return {
      score: rubric.diagnosis.hitDifferential,
      maxScore,
      analysis: `“${submitted}”属于鉴别诊断，但不是主要诊断。`,
      details: [],
    }
  }

  return {
    score: rubric.diagnosis.wrong,
    maxScore,
    analysis: '诊断不正确。',
    details: [],
  }
}

function scoreDifferentials(
  submitted: CaseSubmission['differentials'],
  groundTruth: GroundTruth,
  rubric: ScoringRubric,
): ScoreDimension {
  const details: MatchDetail[] = []
  const matchedIndexes = new Set<number>()
  let score = 0

  for (const item of submitted) {
    const matchIndex = groundTruth.differentials.findIndex(
      (candidate, index) =>
        !matchedIndexes.has(index) &&
        matchesDiagnosis(item.diagnosis, candidate.diagnosis, candidate.aliases),
    )
    if (matchIndex < 0) continue

    matchedIndexes.add(matchIndex)
    const match = groundTruth.differentials[matchIndex]
    const itemScore = 4 + evaluateReasoning(item.reasoning)
    score += itemScore
    details.push({
      submitted: item.diagnosis,
      matched: match.diagnosis,
      matchType: 'exact',
      score: itemScore,
      feedback: match.keyDiscriminator,
    })
  }

  for (const critical of groundTruth.differentials.filter((item) => item.mustExclude)) {
    const covered = submitted.some((item) =>
      matchesDiagnosis(item.diagnosis, critical.diagnosis, critical.aliases),
    )
    if (!covered) {
      score += rubric.differential.missingCritical
      details.push({
        submitted: '',
        matched: critical.diagnosis,
        matchType: 'none',
        score: rubric.differential.missingCritical,
        feedback: `遗漏了重要鉴别诊断：${critical.diagnosis}`,
      })
    }
  }

  const boundedScore = Math.max(0, Math.min(score, rubric.differential.weight))
  return {
    score: boundedScore,
    maxScore: rubric.differential.weight,
    analysis: `命中 ${matchedIndexes.size} 项有效鉴别诊断。`,
    details,
  }
}

function scoreEvidence(
  submitted: string[],
  groundTruth: GroundTruth,
  rubric: ScoringRubric,
): ScoreDimension {
  const criticalEvidence = [
    ...groundTruth.criticalEvidence.forDiagnosis.fromHistory,
    ...groundTruth.criticalEvidence.forDiagnosis.fromExam,
    ...groundTruth.criticalEvidence.forDiagnosis.fromTests,
  ]
  const matchedEvidence = new Set<number>()

  for (const evidence of submitted) {
    const matchIndex = criticalEvidence.findIndex(
      (candidate, index) => !matchedEvidence.has(index) && fuzzyMatch(evidence, candidate),
    )
    if (matchIndex >= 0) matchedEvidence.add(matchIndex)
  }

  const coverage =
    criticalEvidence.length > 0 ? matchedEvidence.size / criticalEvidence.length : 0
  return {
    score: Math.round(coverage * rubric.evidence.weight),
    maxScore: rubric.evidence.weight,
    analysis: `关键证据覆盖率：${Math.round(coverage * 100)}%`,
    details: [],
  }
}

function scoreTreatment(
  submitted: string[],
  groundTruth: GroundTruth,
  rubric: ScoringRubric,
): ScoreDimension {
  const criticalTreatments = [
    ...groundTruth.treatment.immediate,
    ...groundTruth.treatment.definitive,
  ].filter((item) => item.isCritical)
  const pointsPerTreatment =
    criticalTreatments.length > 0 ? rubric.treatment.weight / criticalTreatments.length : 0
  const details: MatchDetail[] = []
  let score = 0

  for (const treatment of criticalTreatments) {
    const submittedTreatment = submitted.find(
      (item) =>
        fuzzyMatch(item, treatment.action) ||
        treatment.aliases?.some((alias) => fuzzyMatch(item, alias)),
    )
    if (submittedTreatment) {
      score += pointsPerTreatment
      details.push({
        submitted: submittedTreatment,
        matched: treatment.action,
        matchType: 'exact',
        score: Math.round(pointsPerTreatment * 10) / 10,
        feedback: `已覆盖：${treatment.action}`,
      })
    } else {
      details.push({
        submitted: '',
        matched: treatment.action,
        matchType: 'none',
        score: 0,
        feedback: `遗漏：${treatment.action}`,
      })
    }
  }

  for (const dangerous of groundTruth.treatment.dangerous) {
    for (const item of submitted) {
      const matches =
        fuzzyMatch(item, dangerous.action) ||
        dangerous.aliases?.some((alias) => fuzzyMatch(item, alias))
      if (matches && !NEGATION_WORDS.some((negation) => item.includes(negation))) {
        score -= dangerous.penalty
        details.push({
          submitted: item,
          matched: dangerous.action,
          matchType: 'none',
          score: -dangerous.penalty,
          feedback: `危险措施：${dangerous.action}`,
        })
      }
    }
  }

  return {
    score: Math.round(Math.max(0, Math.min(score, rubric.treatment.weight))),
    maxScore: rubric.treatment.weight,
    analysis: '',
    details,
  }
}

export function scoreCaseSubmission(
  submission: CaseSubmission,
  groundTruth: GroundTruth,
  rubric: ScoringRubric,
): ScoreReport {
  const dimensions = {
    diagnosis: scoreDiagnosis(submission.primaryDiagnosis, groundTruth, rubric),
    differential: scoreDifferentials(submission.differentials, groundTruth, rubric),
    evidence: scoreEvidence(submission.evidence, groundTruth, rubric),
    treatment: scoreTreatment(submission.treatments, groundTruth, rubric),
  }
  const totalScore = Object.values(dimensions).reduce(
    (total, dimension) => total + dimension.score,
    0,
  )
  const maxScore = Object.values(dimensions).reduce(
    (total, dimension) => total + dimension.maxScore,
    0,
  )
  const percentage = maxScore > 0 ? (totalScore / maxScore) * 100 : 0
  const strengths: string[] = []
  const weaknesses: string[] = []
  const recommendations: string[] = []

  if (dimensions.diagnosis.score >= dimensions.diagnosis.maxScore * 0.75) {
    strengths.push('诊断方向正确')
  } else {
    weaknesses.push('诊断需要更精确')
    recommendations.push('复习该疾病的诊断标准')
  }
  if (dimensions.differential.score >= dimensions.differential.maxScore * 0.8) {
    strengths.push('鉴别诊断较全面')
  } else {
    weaknesses.push('鉴别诊断需要补充')
    recommendations.push('补充高风险鉴别诊断及排除依据')
  }
  if (dimensions.evidence.score >= dimensions.evidence.maxScore * 0.75) {
    strengths.push('证据运用充分')
  } else {
    weaknesses.push('关键证据引用不足')
  }
  if (dimensions.treatment.score >= dimensions.treatment.maxScore * 0.75) {
    strengths.push('治疗方案较完整')
  } else {
    weaknesses.push('治疗方案需要完善')
    recommendations.push('复习关键处置步骤与安全禁忌')
  }

  return {
    totalScore,
    grade:
      percentage >= 90
        ? 'excellent'
        : percentage >= 70
          ? 'good'
          : percentage >= 50
            ? 'fair'
            : 'poor',
    ...dimensions,
    strengths,
    weaknesses,
    recommendations,
  }
}
