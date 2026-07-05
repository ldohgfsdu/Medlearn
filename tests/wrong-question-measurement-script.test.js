const test = require('node:test')
const assert = require('node:assert/strict')
const path = require('node:path')
const { spawnSync } = require('node:child_process')

test('wrong-question measurement script enforces expected evidence matches', () => {
  const scriptPath = path.join(__dirname, '..', 'scripts', 'measure-wrong-question-lookup.mjs')
  const result = spawnSync(
    process.execPath,
    [scriptPath, '--require-match', '--max-ms=15000'],
    {
      cwd: path.join(__dirname, '..'),
      encoding: 'utf8',
    },
  )

  assert.equal(result.status, 0, result.stderr || result.stdout)

  const output = JSON.parse(result.stdout)
  assert.equal(output.results.length, 5)
  assert.equal(
    output.results.some((item) => item.caseId === 'rq-resp-001' && item.variant === 'stem_options_only'),
    true,
  )
  assert.equal(
    output.results.some((item) => item.caseId === 'rq-resp-003' && item.variant === 'stem_options_only'),
    true,
  )
  assert.equal(output.results.every((item) => item.expectedMatched), true)
  assert.equal(output.results.every((item) => item.failures.length === 0), true)
  assert.equal(output.results.every((item) => item.topCandidate?.itemId), true)
  assert.equal(
    output.results.some((item) =>
      item.caseId === 'rq-resp-002' &&
      item.topCandidate?.evidenceOnly === true &&
      item.topCandidate?.pageLabel === 'p.83'
    ),
    true,
  )
  assert.equal(
    output.results.some((item) => item.risk === 'high_risk_source_navigation_only' && item.safetyNote),
    true,
  )
})
