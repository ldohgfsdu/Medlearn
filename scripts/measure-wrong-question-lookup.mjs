import { performance } from 'node:perf_hooks'
import { createRequire } from 'node:module'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

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
          throw new Error('wrong-question lookup measurement must use local EV1 contracts only')
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

async function localTextbookDetails() {
  const tree = await textbookService.getTextbookTree()
  const details = await Promise.all(
    tree.sections.map((section) => textbookService.getSectionDetail(section.id)),
  )
  return details.filter(Boolean)
}

function candidateMatchesExpected(candidate, realCase) {
  if (!candidate) return false

  const scalarMatches = [
    'sectionTitle',
    'unitTitle',
    'groupTitle',
    'itemTitle',
    'pageLabel',
  ].every((field) => realCase.expected[field] === undefined || candidate[field] === realCase.expected[field])

  const evidenceMatches = realCase.expected.evidenceIncludes.every((term) =>
    candidate.evidenceExcerpt.includes(term),
  )

  return scalarMatches && evidenceMatches
}

function summarizeCandidate(candidate) {
  if (!candidate) return null
  return {
    id: candidate.id,
    sectionId: candidate.sectionId,
    sectionTitle: candidate.sectionTitle,
    unitTitle: candidate.unitTitle,
    itemId: candidate.itemId,
    groupTitle: candidate.groupTitle,
    itemTitle: candidate.itemTitle,
    pageLabel: candidate.pageLabel,
    evidenceOnly: Boolean(candidate.evidenceOnly),
    score: candidate.score,
    matchedTerms: candidate.matchedTerms,
    evidenceExcerpt: candidate.evidenceExcerpt,
  }
}

function printPretty(results) {
  for (const result of results) {
    const top = result.topCandidate
    console.log(`\n${result.caseId} - ${result.title}`)
    console.log(`variant: ${result.variant}`)
    console.log(`risk: ${result.risk}`)
    console.log(`elapsed: ${result.elapsedMs}ms`)
    console.log(`candidateCount: ${result.candidateCount}`)
    console.log(`expectedMatched: ${result.expectedMatched ? 'yes' : 'no'}`)
    if (result.safetyNote) console.log(`safety: ${result.safetyNote}`)
    if (top) {
      console.log(
        `top: ${top.sectionTitle} -> ${top.unitTitle} -> ${top.groupTitle} -> ${top.itemTitle} (${top.pageLabel})`,
      )
      console.log(`evidence: ${top.evidenceExcerpt}`)
    }
  }
}

function stemAndOptionsOnly(input) {
  return input.split(/\n正确答案/)[0].trim()
}

function measurementInputs(realCase) {
  const inputs = [{ variant: 'full_context', input: realCase.input }]
  if (realCase.id === 'rq-resp-001' || realCase.id === 'rq-resp-003') {
    inputs.push({ variant: 'stem_options_only', input: stemAndOptionsOnly(realCase.input) })
  }
  return inputs
}

function optionValue(name) {
  const prefix = `${name}=`
  const match = process.argv.find((arg) => arg.startsWith(prefix))
  return match ? match.slice(prefix.length) : undefined
}

function resultFailures(result, maxMs) {
  const failures = []
  if (!result.topCandidate) failures.push('missing_top_candidate')
  if (!result.expectedMatched) failures.push('expected_evidence_not_matched')
  if (maxMs !== undefined && result.elapsedMs > maxMs) failures.push('elapsed_time_over_limit')
  return failures
}

const pretty = process.argv.includes('--pretty')
const requireMatch = process.argv.includes('--require-match')
const maxMsOption = optionValue('--max-ms')
const maxMs = maxMsOption === undefined ? undefined : Number(maxMsOption)

if (maxMsOption !== undefined && (!Number.isFinite(maxMs) || maxMs <= 0)) {
  console.error('--max-ms must be a positive number of milliseconds')
  process.exit(2)
}

const details = await localTextbookDetails()
const results = REAL_WRONG_QUESTION_CASES.flatMap((realCase) => measurementInputs(realCase).map((inputCase) => {
  const startedAt = performance.now()
  const candidates = locateWrongQuestionCandidates(inputCase.input, details)
  const elapsedMs = Number((performance.now() - startedAt).toFixed(3))
  const topCandidate = summarizeCandidate(candidates[0])

  const result = {
    caseId: realCase.id,
    variant: inputCase.variant,
    title: realCase.title,
    risk: realCase.risk,
    safetyNote: realCase.safetyNote,
    elapsedMs,
    candidateCount: candidates.length,
    expectedMatched: candidateMatchesExpected(candidates[0], realCase),
    topCandidate,
  }

  return {
    ...result,
    failures: resultFailures(result, maxMs),
  }
}))

if (pretty) {
  printPretty(results)
} else {
  console.log(JSON.stringify({ generatedAt: new Date().toISOString(), results }, null, 2))
}

if (requireMatch && results.some((result) => result.failures.length > 0)) {
  process.exitCode = 1
}
