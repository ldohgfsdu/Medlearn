const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const ts = require('typescript')

const moduleCache = new Map()

function loadTypeScriptModule(filePath) {
  const resolved = path.resolve(filePath)
  if (moduleCache.has(resolved)) return moduleCache.get(resolved)

  const source = fs.readFileSync(resolved, 'utf8')
  const output = ts.transpileModule(source, {
    compilerOptions: {
      module: ts.ModuleKind.CommonJS,
      target: ts.ScriptTarget.ES2022,
      esModuleInterop: true,
    },
  }).outputText

  const module = { exports: {} }
  const wrapper = vm.runInNewContext(`(function (require, module, exports) { ${output} })`)
  const localRequire = (id) => {
    if (id === '@/constants/phase1PageImageAssets') {
      return {
        PHASE1_PAGE_IMAGE_ASSETS: { im10_page_64: 1 },
        PHASE1_ASTHMA_PAGE_LABELS: ['64'],
      }
    }
    if (id.startsWith('@/')) {
      const base = path.join(__dirname, '..', id.slice(2))
      const withTs = `${base}.ts`
      return loadTypeScriptModule(fs.existsSync(withTs) ? withTs : base)
    }
    return require(id)
  }
  wrapper(localRequire, module, module.exports)
  moduleCache.set(resolved, module.exports)
  return module.exports
}

const {
  PHASE1_ASTHMA_SECTION_ID,
  buildPageViewerPayload,
  locatorIdsForEvidenceArtifact,
  isPhase1VisualEvidenceSection,
} = loadTypeScriptModule(path.join(__dirname, '..', 'services', 'phase1VisualEvidenceService.ts'))

test('phase1 visual evidence section is asthma only', () => {
  assert.equal(isPhase1VisualEvidenceSection(PHASE1_ASTHMA_SECTION_ID), true)
  assert.equal(
    isPhase1VisualEvidenceSection('第二篇_呼吸系统疾病__第八章_肺结核'),
    false,
  )
})

test('BDT locator on p64 resolves PageViewer payload', () => {
  const locatorId = 'loc_ev1_57068078e29b9153d70d'
  const payload = buildPageViewerPayload([locatorId], '64')
  assert.ok(payload, 'expected non-null payload for known BDT locator')
  assert.equal(payload.pageLabel, '64')
  assert.equal(typeof payload.imageSource, 'number')
  assert.ok(payload.locators.length >= 1)
  const b = payload.locators[0].bboxNorm
  assert.equal(b?.length, 4)
  for (const v of b) {
    assert.ok(v >= 0 && v <= 1, `bboxNorm out of range: ${v}`)
  }
})

test('locatorIdsForEvidenceArtifact uses explicit ids when provided', () => {
  const explicit = ['loc_ev1_57068078e29b9153d70d']
  const ids = locatorIdsForEvidenceArtifact(PHASE1_ASTHMA_SECTION_ID, 'ev1-any', explicit)
  assert.deepEqual(ids, explicit)
})