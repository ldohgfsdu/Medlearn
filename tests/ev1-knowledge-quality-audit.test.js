const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { spawnSync } = require('node:child_process')

test('EV1 pulmonary infection quality audit passes source lookup gates', () => {
  const scriptPath = path.join(__dirname, '..', 'scripts', 'audit-ev1-knowledge-quality.mjs')
  const result = spawnSync(
    process.execPath,
    [scriptPath],
    {
      cwd: path.join(__dirname, '..'),
      encoding: 'utf8',
    },
  )

  assert.equal(result.status, 0, result.stderr || result.stdout)

  const report = JSON.parse(result.stdout)
  assert.equal(report.sectionTitle, '第六章 肺部感染性疾病')
  assert.equal(report.catalogUnits.passed, true)
  assert.equal(report.passed, true)
  assert.equal(report.sourceQa.summary.itemCount, 241)
  assert.equal(report.sourceQa.summary.sourceEvidenceVisibleCount, 241)
  assert.equal(report.sourceQa.summary.rejectedSourceExtractionCount, 0)
  assert.equal(report.sourceQa.summary.missingSourceArtifactContextCount, 0)
  assert.equal(report.sourceQa.summary.issueTypeCounts.none, 241)
  assert.equal(report.sourceQaBook.scope, 'book')
  assert.equal(report.sourceQaBook.summary.sectionCount, 131)
  assert.equal(report.sourceQaBook.summary.itemCount, 9192)
  assert.equal(report.sourceQaBook.summary.sourceEvidenceVisibleCount, 9192)
  assert.equal(report.sourceQaBook.summary.missingFromDisplayContractCount, 0)
  assert.equal(report.sourceQaBook.summary.rejectedSourceExtractionCount, 0)
  assert.equal(report.sourceQaBook.summary.issueTypeCounts.none, 9192)
  assert.equal(
    report.warnings.some((item) => item.id === 'source-qa-missing-display-contract-evidence'),
    false,
  )
  assert.equal(
    report.groupingAlerts.some((item) => item.id === 'pulmonary-infection-overview-signs-misgrouped'),
    false,
  )
  assert.equal(
    report.blockers.some((item) => item.id === 'rq-resp-002-expected-evidence-not-matched'),
    false,
  )
  const penicillinCase = report.wrongQuestionCases.find((item) => item.id === 'rq-resp-002')
  assert.equal(penicillinCase.expectedMatched, true)
  assert.equal(penicillinCase.sourceEvidenceStatus.status, 'evidence_only_app_visible')
  assert.equal(penicillinCase.sourceEvidenceStatus.appVisible, true)
  assert.equal(penicillinCase.sourceEvidenceStatus.evidenceOnly, true)
  assert.ok(penicillinCase.sourceEvidenceStatus.synthesisMatchCount > 0)
  assert.equal(penicillinCase.topCandidate.pageLabel, 'p.83')
})

test('EV1 pulmonary infection quality audit strict mode passes source lookup gates', () => {
  const scriptPath = path.join(__dirname, '..', 'scripts', 'audit-ev1-knowledge-quality.mjs')
  const result = spawnSync(
    process.execPath,
    [scriptPath, '--strict'],
    {
      cwd: path.join(__dirname, '..'),
      encoding: 'utf8',
    },
  )

  assert.equal(result.status, 0, result.stderr || result.stdout)
})
