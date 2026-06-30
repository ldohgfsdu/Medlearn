const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const os = require('node:os')
const path = require('node:path')
const { spawnSync } = require('node:child_process')

function runQueueExport(args = []) {
  const scriptPath = path.join(__dirname, '..', 'scripts', 'export-ev1-source-qa-queue.mjs')
  const result = spawnSync(
    process.execPath,
    [scriptPath, '--stdout-only', ...args],
    {
      cwd: path.join(__dirname, '..'),
      encoding: 'utf8',
      maxBuffer: 20 * 1024 * 1024,
    },
  )
  assert.equal(result.status, 0, result.stderr || result.stdout)
  return JSON.parse(result.stdout)
}

function runLegacyQueueExport(args = []) {
  const scriptPath = path.join(__dirname, '..', 'scripts', 'export-ev1-review-queue.mjs')
  const result = spawnSync(
    process.execPath,
    [scriptPath, '--stdout-only', ...args],
    {
      cwd: path.join(__dirname, '..'),
      encoding: 'utf8',
    },
  )
  assert.equal(result.status, 0, result.stderr || result.stdout)
  return JSON.parse(result.stdout)
}

function writeJson(filePath, payload) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
  fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8')
}

test('EV1 source QA queue exports candidates as evidence-only source material', () => {
  const queue = runQueueExport()

  assert.equal(queue.version, 'ev1-source-qa-queue-0.1.0')
  assert.equal(queue.textbookId, 'internal-medicine-10')
  assert.equal(queue.sectionId, '第二篇_呼吸系统疾病__第六章_肺部感染性疾病')
  assert.ok(queue.summary.itemCount > 0)
  assert.match(queue.queuePurpose, /not a medical truth approval workflow/)
  assert.ok(queue.summary.highRiskItemCount > 0)
  assert.equal(queue.summary.sourceEvidenceVisibleCount, queue.summary.evidenceOnlyDisplayContractCount)
  assert.equal(queue.summary.itemCount, queue.summary.missingFromOrganizedNormalizedCount)
  assert.equal(queue.summary.missingFromDisplayContractCount, queue.summary.rejectedSourceExtractionCount)
  assert.equal(queue.summary.rejectedSourceExtractionCount, 0)
  assert.equal(queue.summary.missingSourceArtifactContextCount, 0)
  assert.equal(queue.summary.sourceEvidenceVisibleCount, 241)
  assert.equal(queue.summary.issueTypeCounts.none, 241)
  assert.match(queue.source.evidencePath, /evidence\.json$/)
  assert.match(queue.source.displayContractPath, /display_contract\.json$/)
})

test('EV1 source QA queue can audit all bundled sections', () => {
  const queue = runQueueExport(['--all'])

  assert.equal(queue.version, 'ev1-source-qa-queue-0.1.0')
  assert.equal(queue.scope, 'book')
  assert.equal(queue.textbookId, 'internal-medicine-10')
  assert.equal(queue.summary.sectionCount, 131)
  assert.equal(queue.summary.itemCount, 9192)
  assert.equal(queue.summary.sourceEvidenceVisibleCount, 9192)
  assert.equal(queue.summary.missingFromDisplayContractCount, 0)
  assert.equal(queue.summary.rejectedSourceExtractionCount, 0)
  assert.equal(queue.summary.issueTypeCounts.none, 9192)
  assert.equal(queue.items.length, 9192)
})

test('EV1 source QA all-sections mode aggregates fixture sections', () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'medlearn-source-qa-all-'))
  const sourceRoot = path.join(tmp, 'knowledge_nodes', 'internal-medicine-10')
  const displayRoot = path.join(tmp, 'display_contracts', 'internal-medicine-10')

  const sectionPairs = [
    ['fixture-a', 'fixture-a'],
    ['fixture-b__CAR-T, demo', 'fixture_b__CAR_T_demo'],
  ]
  for (const [sourceSectionId, displaySectionId] of sectionPairs) {
    writeJson(path.join(sourceRoot, `${sourceSectionId}.evidence.synthesis.json`), {
      items: [{
        artifact_id: `${sourceSectionId}-artifact`,
        item_index: 0,
        title: 'Needs review source',
        content: 'source sentence',
        evidence: 'source sentence',
        risk_class: 'needs_review',
        source_heading: 'Fixture heading',
        page_start: 1,
        page_end: 1,
        verification_state: 'needs_review',
        verification_notes: [],
      }],
    })
    writeJson(path.join(sourceRoot, `${sourceSectionId}.evidence.json`), {
      artifacts: [{
        id: `${sourceSectionId}-artifact`,
        page_start: 1,
        page_end: 1,
        source_order: 1,
        source_heading: 'Fixture heading',
        raw_text: 'source sentence',
      }],
    })
    writeJson(path.join(sourceRoot, `${displaySectionId}.normalized.json`), { nodes: [] })
    writeJson(path.join(displayRoot, `${displaySectionId}.display_contract.json`), {
      nodes: [{
        id: `view-${displaySectionId}`,
        render_type: 'evidence_only',
        publication_state: 'evidence_only',
        display: {
          title: '原文证据',
          page_label: 'p.1',
        },
        evidence_items: [{
          artifact_id: `${sourceSectionId}-artifact`,
          text: 'source sentence',
          page_start: 1,
          page_end: 1,
        }],
      }],
    })
  }

  const queue = runQueueExport([
    '--all',
    '--source-root',
    sourceRoot,
    '--display-contract-root',
    displayRoot,
  ])

  assert.equal(queue.scope, 'book')
  assert.equal(queue.summary.sectionCount, 2)
  assert.equal(queue.summary.itemCount, 2)
  assert.equal(queue.summary.sourceEvidenceVisibleCount, 2)
  assert.equal(queue.summary.missingFromDisplayContractCount, 0)
  assert.deepEqual(queue.sections.map((section) => section.sectionId), ['fixture-a', 'fixture-b__CAR-T, demo'])
})

test('EV1 source QA queue matches display evidence after control-character cleanup', () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'medlearn-source-qa-control-'))
  const sourceRoot = path.join(tmp, 'knowledge_nodes', 'internal-medicine-10')
  const displayRoot = path.join(tmp, 'display_contracts', 'internal-medicine-10')
  const sectionId = 'fixture-control'
  const rawEvidence = 'source \x07 sentence'
  const cleanedEvidence = 'source sentence'

  writeJson(path.join(sourceRoot, `${sectionId}.evidence.synthesis.json`), {
    items: [{
      artifact_id: 'artifact-control',
      item_index: 0,
      title: 'Control cleanup source',
      content: rawEvidence,
      evidence: rawEvidence,
      risk_class: 'needs_review',
      source_heading: 'Fixture heading',
      page_start: 1,
      page_end: 1,
      verification_state: 'needs_review',
      verification_notes: [],
    }],
  })
  writeJson(path.join(sourceRoot, `${sectionId}.evidence.json`), {
    artifacts: [{
      id: 'artifact-control',
      page_start: 1,
      page_end: 1,
      source_order: 1,
      source_heading: 'Fixture heading',
      raw_text: rawEvidence,
    }],
  })
  writeJson(path.join(sourceRoot, `${sectionId}.normalized.json`), { nodes: [] })
  writeJson(path.join(displayRoot, `${sectionId}.display_contract.json`), {
    nodes: [{
      id: 'view-control',
      render_type: 'evidence_only',
      publication_state: 'evidence_only',
      display: {
        title: '原文证据',
        page_label: 'p.1',
        items: [{
          title: '原文证据',
          body: cleanedEvidence,
          publication_state: 'evidence_only',
        }],
      },
      evidence_items: [{
        artifact_id: 'artifact-control',
        text: cleanedEvidence,
        page_start: 1,
        page_end: 1,
      }],
    }],
  })

  const queue = runQueueExport([
    '--section-id',
    sectionId,
    '--source-root',
    sourceRoot,
    '--display-contract-root',
    displayRoot,
  ])

  assert.equal(queue.summary.itemCount, 1)
  assert.equal(queue.summary.sourceEvidenceVisibleCount, 1)
  assert.equal(queue.summary.missingFromDisplayContractCount, 0)
  assert.equal(queue.summary.issueTypeCounts.none, 1)
  assert.equal(queue.items[0].sourceEvidenceVisible, true)
  assert.equal(queue.items[0].appDisplay.presence, 'evidence_only')
})

test('EV1 source QA queue includes rejected standard-risk source extraction', () => {
  const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'medlearn-source-qa-'))
  const sourceRoot = path.join(tmp, 'knowledge_nodes', 'internal-medicine-10')
  const displayRoot = path.join(tmp, 'display_contracts', 'internal-medicine-10')
  const sectionId = 'fixture-section'

  writeJson(path.join(sourceRoot, `${sectionId}.evidence.synthesis.json`), {
    items: [{
      artifact_id: 'artifact-standard-rejected',
      item_index: 0,
      title: 'Rejected standard item',
      content: 'A synthesized sentence that is not continuous.',
      evidence: 'A synthesized sentence that is not continuous.',
      risk_class: 'standard',
      source_heading: 'Fixture heading',
      page_start: 1,
      page_end: 1,
      verification_state: 'rejected',
      verification_notes: ['evidence_substring'],
    }],
  })
  writeJson(path.join(sourceRoot, `${sectionId}.evidence.json`), {
    artifacts: [{
      id: 'artifact-standard-rejected',
      page_start: 1,
      page_end: 1,
      source_order: 1,
      source_heading: 'Fixture heading',
      raw_text: 'Original textbook source span.',
    }],
  })
  writeJson(path.join(sourceRoot, `${sectionId}.normalized.json`), { nodes: [] })
  writeJson(path.join(displayRoot, `${sectionId}.display_contract.json`), { nodes: [] })

  const queue = runQueueExport([
    '--section-id',
    sectionId,
    '--source-root',
    sourceRoot,
    '--display-contract-root',
    displayRoot,
  ])

  assert.equal(queue.summary.itemCount, 1)
  assert.equal(queue.summary.rejectedSourceExtractionCount, 1)
  assert.equal(queue.items[0].riskClass, 'standard')
  assert.equal(queue.items[0].verificationState, 'rejected')
  assert.equal(queue.items[0].qaReason, 'source_extraction_rejected_qa')
  assert.equal(queue.items[0].publicationAction, 'fix_rejected_source_extraction_before_display')
})

test('legacy EV1 review queue command remains a source QA compatibility wrapper', () => {
  const queue = runLegacyQueueExport()

  assert.equal(queue.version, 'ev1-source-qa-queue-0.1.0')
  assert.match(queue.queuePurpose, /not a medical truth approval workflow/)
})

test('EV1 source QA queue keeps pneumococcal penicillin dosage as evidence-only', () => {
  const queue = runQueueExport()
  const item = queue.items.find((entry) =>
    entry.sourceEvidence.includes('青霉素G') &&
    entry.sourceEvidence.includes('用药途径及剂量'),
  )

  assert.ok(item, 'expected pneumococcal penicillin dosage evidence in source QA queue')
  assert.equal(item.riskClass, 'needs_review')
  assert.equal(item.verificationState, 'needs_review')
  assert.equal(item.qaReason, 'high_risk_source_extraction_qa')
  assert.equal(item.requiredQaRole, 'source_qa_reviewer')
  assert.equal(item.needsSourceQa, true)
  assert.equal(item.organizedConclusionVisible, false)
  assert.equal(item.sourceEvidenceVisible, true)
  assert.equal(item.publicationAction, 'show_source_evidence_only')
  assert.equal(item.displayMode, 'evidence_only')
  assert.equal(item.organizedNormalizedPresence, 'absent')
  assert.equal(item.appDisplay.presence, 'evidence_only')
  assert.equal(item.appDisplay.publicationState, 'evidence_only')
  assert.equal(item.appDisplay.renderType, 'grouped')
  assert.equal(item.appDisplay.groupTopic, 'treatment')
  assert.equal(item.appDisplay.displayTitle, '抗菌药物治疗')
  assert.equal(item.sourceLocator.pageStart, 83)
})

test('EV1 source QA queue keeps repaired antibacterial-selection evidence app visible', () => {
  const queue = runQueueExport()
  const item = queue.items.find((entry) =>
    entry.sourceEvidence.includes('选择抗菌药物和给药途径'),
  )

  assert.ok(item, 'expected repaired antibacterial-selection source item in source QA queue')
  assert.equal(item.verificationState, 'needs_review')
  assert.equal(item.qaReason, 'verification_state_source_qa')
  assert.equal(item.sourceEvidenceVisible, true)
  assert.equal(item.publicationAction, 'show_source_evidence_only')
  assert.equal(item.displayMode, 'evidence_only')
  assert.equal(item.appDisplay.presence, 'evidence_only')
  assert.equal(item.extractionIssue.type, 'none')
  assert.equal(item.extractionIssue.severity, 'none')
  assert.match(item.sourceEvidence, /选择抗菌药物和给药途径/)
})
