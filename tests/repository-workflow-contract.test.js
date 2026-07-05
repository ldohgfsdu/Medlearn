const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const ROOT = path.resolve(__dirname, '..')
const read = (relativePath) => fs.readFileSync(path.join(ROOT, relativePath), 'utf8')
const packageJson = JSON.parse(read('package.json'))

test('repository pins cross-platform line endings and binary assets', () => {
  const attributes = read('.gitattributes')

  assert.match(attributes, /\* text=auto eol=lf/)
  assert.match(attributes, /\*\.bat text eol=crlf/)
  assert.match(attributes, /\*\.webp binary/)
  assert.match(attributes, /\*\.apk binary/)
})

test('repository declares its supported Node and package-manager baseline', () => {
  assert.equal(packageJson.packageManager, 'npm@11.16.0')
  assert.equal(packageJson.engines.node, '>=22 <25')
})

test('CI Python dependencies are fully pinned', () => {
  const requirements = read('scripts/requirements-ci.txt')
    .split(/\r?\n/u)
    .map((line) => line.trim())
    .filter((line) => line && !line.startsWith('#'))

  assert.ok(requirements.length > 0)
  assert.ok(requirements.every((requirement) => requirement.includes('==')))
})

test('quality workflow gates client, governance, pipeline, and Phase 1 assets', () => {
  const workflow = read('.github/workflows/quality.yml')

  assert.match(workflow, /node-version: 22/)
  assert.match(workflow, /python-version: '3\.12'/)
  assert.match(workflow, /npm run check/)
  assert.match(workflow, /validate_project_state\.py/)
  assert.match(workflow, /generate_current_state\.py --check/)
  assert.match(workflow, /unittest discover/)
  assert.match(workflow, /verify_pipeline_closure\.py/)
  assert.doesNotMatch(workflow, /verify_pipeline_closure\.py --remote/)
  assert.match(workflow, /validate_phase1_pageviewer\.py --check-export/)
  assert.match(workflow, /audit_phase1_visual_evidence_origin\.py/)
  assert.match(workflow, /git ls-files --error-unmatch/)
  assert.match(workflow, /ev1DisplayContractsChunks\/\*\.ts/)
  assert.match(workflow, /git diff --exit-code/)
})

test('release workflow validates the repository and tag version before publishing', () => {
  const workflow = read('.github/workflows/release.yml')

  assert.match(workflow, /npm run check/)
  assert.match(workflow, /package\.json/)
  assert.match(workflow, /GITHUB_REF_NAME/)
  assert.ok(workflow.indexOf('npm run check') < workflow.indexOf('softprops/action-gh-release'))
})

test('docs workflow uses the supported Node baseline and version contract', () => {
  const workflow = read('.github/workflows/deploy-docs.yml')

  assert.match(workflow, /node-version: 22/)
  assert.match(workflow, /npm run check:version/)
  assert.match(workflow, /npm run docs:build/)
})
