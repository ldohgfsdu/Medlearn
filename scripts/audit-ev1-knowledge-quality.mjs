import { createRequire } from 'node:module'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { buildSourceQaBookQueue, buildSourceQaQueue } from './export-ev1-source-qa-queue.mjs'

const require = createRequire(import.meta.url)
const __dirname = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(__dirname, '..')

const { loadTypeScriptModule } = require(path.join(rootDir, 'tests', 'loadTsModule.js'))
const { REAL_WRONG_QUESTION_CASES } = require(path.join(
  rootDir,
  'tests',
  'fixtures',
  'wrong-question-real-cases.js',
))
const internalMedicineCatalog = require(path.join(
  rootDir,
  'constants',
  'catalog.internal-medicine.json',
))

const ev1DisplayContracts = loadTypeScriptModule(
  path.join(rootDir, 'constants', 'ev1DisplayContracts.ts'),
)

const textbookService = loadTypeScriptModule(
  path.join(rootDir, 'services', 'textbookService.ts'),
  {
    '@/constants/ev1DisplayContracts': ev1DisplayContracts,
    '@/lib/supabase': {
      supabase: {
        from() {
          throw new Error('EV1 knowledge quality audit must use local bundled display contracts')
        },
      },
    },
  },
)

const textbookStudy = loadTypeScriptModule(path.join(rootDir, 'utils', 'textbookStudy.ts'))
const { locateWrongQuestionCandidates } = loadTypeScriptModule(
  path.join(rootDir, 'utils', 'wrongQuestionIntake.ts'),
  {
    '@/utils/textbookStudy': textbookStudy,
  },
)

const TARGET_SECTION_ID = '第二篇_呼吸系统疾病__第六章_肺部感染性疾病'
const TARGET_SOURCE_ROOT = path.join(rootDir, 'generated', 'knowledge_nodes', 'internal-medicine-10')
const TARGET_SYNTHESIS_PATH = path.join(TARGET_SOURCE_ROOT, `${TARGET_SECTION_ID}.evidence.synthesis.json`)
const TARGET_NORMALIZED_PATH = path.join(TARGET_SOURCE_ROOT, `${TARGET_SECTION_ID}.normalized.json`)
const EXPECTED_PULMONARY_INFECTION_UNITS = [
  '第一节 肺炎概述',
  '第二节 细菌性肺炎',
  '第三节 病毒性肺炎',
  '第四节 肺炎支原体肺炎、衣原体肺炎与肺军团病',
  '第五节 肺真菌病',
]

function cleanText(value) {
  return String(value ?? '').replace(/\s+/g, ' ').trim()
}

function readJsonFile(filePath) {
  if (!fs.existsSync(filePath)) return null
  return JSON.parse(fs.readFileSync(filePath, 'utf8'))
}

function sourceItems(payload) {
  if (!payload) return []
  if (Array.isArray(payload)) return payload
  return payload.items ?? payload.nodes ?? []
}

function sourceItemText(item) {
  return [
    item.title,
    item.content,
    item.evidence,
    item.source_heading,
    item.source_span?.evidence,
    ...(item.structured_sections ?? []).flatMap((section) => [section.title, section.content]),
  ].map(cleanText).filter(Boolean).join('\n')
}

function sourceItemMatchesTerms(item, terms) {
  const text = sourceItemText(item)
  return terms.length > 0 && terms.every((term) => text.includes(term))
}

function summarizeSourceItem(item) {
  return {
    id: item.id ?? item.artifact_id ?? null,
    title: cleanText(item.title),
    pageLabel: item.page_start ?? item.source_span?.page_start
      ? `p.${item.page_start ?? item.source_span?.page_start}`
      : null,
    riskClass: item.risk_class ?? item.source_span?.risk_class ?? null,
    verificationState: item.verification_state ?? item.source_span?.verification_state ?? null,
    evidenceExcerpt: cleanText(item.evidence ?? item.content ?? item.source_span?.evidence).slice(0, 120),
  }
}

function findSourceMatches(payload, terms) {
  return sourceItems(payload).filter((item) => sourceItemMatchesTerms(item, terms))
}

function buildSourceEvidenceStatus(realCase, topCandidate, expectedMatched, sourcePayloads) {
  const terms = realCase.expected?.evidenceIncludes ?? []
  if (terms.length === 0) return null

  const synthesisMatches = findSourceMatches(sourcePayloads.synthesis, terms)
  const normalizedMatches = findSourceMatches(sourcePayloads.normalized, terms)

  if (expectedMatched && topCandidate) {
    return {
      status: topCandidate.evidenceOnly ? 'evidence_only_app_visible' : 'app_visible',
      expectedTerms: terms,
      appVisible: true,
      evidenceOnly: Boolean(topCandidate.evidenceOnly),
      synthesisMatchCount: synthesisMatches.length,
      normalizedMatchCount: normalizedMatches.length,
      sample: summarizeCandidate(topCandidate),
    }
  }

  const needsReviewMatches = synthesisMatches.filter((item) =>
    item.risk_class === 'needs_review' || item.verification_state === 'needs_review',
  )

  if (needsReviewMatches.length > 0) {
    return {
      status: 'extracted_needs_review',
      expectedTerms: terms,
      appVisible: false,
      synthesisMatchCount: synthesisMatches.length,
      normalizedMatchCount: normalizedMatches.length,
      skippedNeedsReview: sourcePayloads.normalized?.conversion_summary?.skipped_needs_review ?? null,
      sample: summarizeSourceItem(needsReviewMatches[0]),
    }
  }

  if (normalizedMatches.length > 0) {
    return {
      status: 'normalized_not_selected',
      expectedTerms: terms,
      appVisible: false,
      synthesisMatchCount: synthesisMatches.length,
      normalizedMatchCount: normalizedMatches.length,
      sample: summarizeSourceItem(normalizedMatches[0]),
    }
  }

  if (synthesisMatches.length > 0) {
    return {
      status: 'extracted_not_normalized',
      expectedTerms: terms,
      appVisible: false,
      synthesisMatchCount: synthesisMatches.length,
      normalizedMatchCount: normalizedMatches.length,
      sample: summarizeSourceItem(synthesisMatches[0]),
    }
  }

  return {
    status: 'not_extracted',
    expectedTerms: terms,
    appVisible: false,
    synthesisMatchCount: 0,
    normalizedMatchCount: 0,
    sample: null,
  }
}

function itemEvidence(item) {
  return [
    item.title,
    item.body,
    ...(item.evidence ?? []).map((evidence) => evidence.text),
    ...(item.children ?? []).flatMap(itemEvidence),
  ].map(cleanText).filter(Boolean).join('\n')
}

async function localTextbookDetails() {
  const tree = await textbookService.getTextbookTree()
  const details = await Promise.all(
    tree.sections.map((section) => textbookService.getSectionDetail(section.id)),
  )
  return details.filter(Boolean)
}

function summarizeCandidate(candidate) {
  if (!candidate) return null
  return {
    sectionTitle: candidate.sectionTitle,
    unitTitle: candidate.unitTitle,
    catalogTitle: candidate.catalogTitle,
    groupTitle: candidate.groupTitle,
    itemTitle: candidate.itemTitle,
    pageLabel: candidate.pageLabel,
    evidenceOnly: Boolean(candidate.evidenceOnly),
    score: candidate.score,
    evidenceExcerpt: candidate.evidenceExcerpt,
  }
}

function candidateMatchesExpected(candidate, realCase) {
  if (!candidate) return false

  const scalarMatches = [
    'sectionTitle',
    'unitTitle',
    'catalogTitle',
    'groupTitle',
    'itemTitle',
    'pageLabel',
  ].every((field) => realCase.expected[field] === undefined || candidate[field] === realCase.expected[field])

  const evidenceMatches = realCase.expected.evidenceIncludes.every((term) =>
    candidate.evidenceExcerpt.includes(term),
  )

  return scalarMatches && evidenceMatches
}

function unitTitleCoversCatalogUnit(unitTitle, catalogUnitTitle) {
  return unitTitle === catalogUnitTitle || unitTitle.startsWith(`${catalogUnitTitle} ·`)
}

function displayCatalogUnitTitle(value) {
  return cleanText(value).replace(/\s*[|｜]\s*/u, ' ')
}

function auditCatalogUnits(units) {
  const catalogChapter = internalMedicineCatalog.chapters
    .flatMap((part) => part.sections ?? [])
    .find((section) => cleanText(section.title) === '第六章 肺部感染性疾病')
  const catalogUnits = catalogChapter?.units ?? []
  const present = catalogUnits.map((unit) => displayCatalogUnitTitle(unit.title))
  const missing = EXPECTED_PULMONARY_INFECTION_UNITS.filter((unitTitle) =>
    !present.includes(unitTitle))
  const unresolved = catalogUnits.flatMap((unit) => {
    const subsections = unit.subsections ?? []
    const targets = subsections.length > 0
      ? subsections.map((subsection) => subsection.title)
      : [unit.title]
    return targets
      .filter((title) => !textbookStudy.resolveCatalogOutlineUnit(title, units))
      .map((title) => ({
        catalogUnit: displayCatalogUnitTitle(unit.title),
        subsection: title,
      }))
  })
  const extra = units
    .filter((unit) => !unit.catalogTitle)
    .map((unit) => unit.title)
  return {
    expected: EXPECTED_PULMONARY_INFECTION_UNITS,
    present,
    missing,
    unresolved,
    extra,
    passed: missing.length === 0 && unresolved.length === 0,
  }
}

function auditMisgroupedEvidence(units) {
  const alerts = []
  const allowedPneumoniaOverviewGroups = new Set(['肺炎'])

  for (const unit of units) {
    for (const group of unit.groups) {
      for (const item of group.items) {
        const evidence = itemEvidence(item)
        if (
          unitTitleCoversCatalogUnit(unit.title, '第一节 肺炎概述') &&
          item.title === '临床表现' &&
          evidence.includes('肺实变时有典型的体征') &&
          !allowedPneumoniaOverviewGroups.has(group.title)
        ) {
          alerts.push({
            id: 'pulmonary-infection-overview-signs-misgrouped',
            severity: 'blocker',
            unitTitle: unit.title,
            groupTitle: group.title,
            itemTitle: item.title,
            pageLabel: item.pageLabel,
            reason: 'General pneumonia consolidation signs are grouped under a specific disease/entity label.',
          })
        }
      }
    }
  }

  return alerts
}

function auditWrongQuestionGoldenCases(realCases, details, sourcePayloads) {
  return realCases.map((realCase) => {
    const candidates = locateWrongQuestionCandidates(realCase.input, details)
    const topCandidate = candidates[0] ?? null
    const expectedMatched = candidateMatchesExpected(topCandidate, realCase)
    const sourceEvidenceStatus = buildSourceEvidenceStatus(
      realCase,
      topCandidate,
      expectedMatched,
      sourcePayloads,
    )
    const issues = []
    if (!expectedMatched) {
      issues.push({
        id: `${realCase.id}-expected-evidence-not-matched`,
        severity: 'critical',
        reason: 'Top wrong-question candidate does not match the expected local textbook evidence.',
      })
    }
    return {
      id: realCase.id,
      title: realCase.title,
      risk: realCase.risk,
      expectedMatched,
      candidateCount: candidates.length,
      topCandidate: summarizeCandidate(topCandidate),
      sourceEvidenceStatus,
      issues,
    }
  })
}

function auditSourceQaQueue({ allSections = false } = {}) {
  const queue = allSections ? buildSourceQaBookQueue() : buildSourceQaQueue()
  const summary = queue.summary
  const issues = []
  if ((summary.missingFromDisplayContractCount ?? 0) > 0) {
    const issueTypes = Object.entries(summary.issueTypeCounts ?? {})
      .filter(([type, count]) => type !== 'none' && count > 0)
      .map(([type, count]) => `${type}=${count}`)
      .join(', ')
    issues.push({
      id: allSections
        ? 'source-qa-book-missing-display-contract-evidence'
        : 'source-qa-missing-display-contract-evidence',
      severity: allSections ? 'blocker' : 'warning',
      reason:
        `${summary.missingFromDisplayContractCount} source QA item(s) are not app-visible evidence; ` +
        `${summary.rejectedSourceExtractionCount ?? 0} are rejected source extraction items` +
        (issueTypes ? ` (${issueTypes}).` : '.'),
    })
  }
  if ((summary.missingSourceArtifactContextCount ?? 0) > 0) {
    issues.push({
      id: 'source-qa-missing-source-context',
      severity: 'warning',
      reason:
        `${summary.missingSourceArtifactContextCount} source QA item(s) lack nearby source artifact context.`,
    })
  }
  return {
    sectionId: queue.sectionId,
    scope: queue.scope ?? 'section',
    summary,
    issues,
  }
}

export async function buildAuditReport() {
  const details = await localTextbookDetails()
  const targetDetail = await textbookService.getSectionDetail(TARGET_SECTION_ID)
  if (!targetDetail) {
    return {
      sectionId: TARGET_SECTION_ID,
      passed: false,
      blockers: [{
        id: 'target-section-missing',
        severity: 'blocker',
        reason: 'Pulmonary infection section is missing from the EV1 app bundle.',
      }],
      warnings: [],
    }
  }

  const units = textbookStudy.buildChapterStudyUnits(targetDetail)
  const catalogUnits = auditCatalogUnits(units)
  const groupingAlerts = auditMisgroupedEvidence(units)
  const sourcePayloads = {
    synthesis: readJsonFile(TARGET_SYNTHESIS_PATH),
    normalized: readJsonFile(TARGET_NORMALIZED_PATH),
  }
  const wrongQuestionCases = auditWrongQuestionGoldenCases(
    REAL_WRONG_QUESTION_CASES,
    details,
    sourcePayloads,
  )
  const sourceQa = auditSourceQaQueue()
  const sourceQaBook = auditSourceQaQueue({ allSections: true })
  const wrongQuestionIssues = wrongQuestionCases.flatMap((item) => item.issues)
  const blockers = [
    ...(!catalogUnits.passed
      ? [{
          id: 'pulmonary-infection-catalog-unit-missing',
          severity: 'blocker',
          reason: [
            catalogUnits.missing.length > 0
              ? `Missing textbook catalog units: ${catalogUnits.missing.join(', ')}`
              : null,
            catalogUnits.unresolved.length > 0
              ? `Unresolved catalog subsections: ${catalogUnits.unresolved
                .map((item) => `${item.catalogUnit} > ${item.subsection}`)
                .join(', ')}`
              : null,
          ].filter(Boolean).join('; '),
        }]
      : []),
    ...groupingAlerts,
    ...wrongQuestionIssues.filter((issue) => issue.severity === 'blocker' || issue.severity === 'critical'),
    ...sourceQaBook.issues.filter((issue) => issue.severity === 'blocker' || issue.severity === 'critical'),
  ]

  return {
    sectionId: TARGET_SECTION_ID,
    sectionTitle: targetDetail.section.sectionTitle,
    textbookId: targetDetail.section.textbookId,
    unitCount: units.length,
    catalogUnits,
    groupingAlerts,
    sourceQa,
    sourceQaBook,
    wrongQuestionCases,
    blockers,
    warnings: [
      ...wrongQuestionIssues.filter((issue) => issue.severity === 'warning'),
      ...sourceQa.issues,
      ...sourceQaBook.issues.filter((issue) => issue.severity === 'warning'),
    ],
    passed: blockers.length === 0,
  }
}

function printPretty(report) {
  console.log(`EV1 knowledge quality audit: ${report.sectionTitle ?? report.sectionId}`)
  console.log(`Result: ${report.passed ? 'PASS' : 'NOT PUBLICATION READY'}`)
  console.log(`Units: ${report.unitCount ?? 0}`)
  if (report.sourceQa?.summary) {
    console.log(
      `Source QA: items=${report.sourceQa.summary.itemCount} ` +
      `evidenceOnlyVisible=${report.sourceQa.summary.sourceEvidenceVisibleCount} ` +
      `rejected=${report.sourceQa.summary.rejectedSourceExtractionCount} ` +
      `issues=${JSON.stringify(report.sourceQa.summary.issueTypeCounts ?? {})}`,
    )
  }
  if (report.sourceQaBook?.summary) {
    console.log(
      `Source QA Book: sections=${report.sourceQaBook.summary.sectionCount} ` +
      `items=${report.sourceQaBook.summary.itemCount} ` +
      `evidenceOnlyVisible=${report.sourceQaBook.summary.sourceEvidenceVisibleCount} ` +
      `missing=${report.sourceQaBook.summary.missingFromDisplayContractCount} ` +
      `issues=${JSON.stringify(report.sourceQaBook.summary.issueTypeCounts ?? {})}`,
    )
  }
  for (const blocker of report.blockers ?? []) {
    console.log(`BLOCKER ${blocker.id}: ${blocker.reason}`)
  }
  for (const warning of report.warnings ?? []) {
    console.log(`WARNING ${warning.id}: ${warning.reason}`)
  }
}

const pretty = process.argv.includes('--pretty')
const strict = process.argv.includes('--strict')
const report = await buildAuditReport()

if (pretty) {
  printPretty(report)
} else {
  console.log(JSON.stringify(report, null, 2))
}

if (strict && !report.passed) {
  process.exitCode = 1
}
