import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const rootDir = path.resolve(__dirname, '..')

const DEFAULT_BOOK_ID = 'internal-medicine-10'
const DEFAULT_SECTION_ID = '第二篇_呼吸系统疾病__第六章_肺部感染性疾病'
const SOURCE_QA_QUEUE_VERSION = 'ev1-source-qa-queue-0.1.0'

const HIGH_RISK_TERMS = [
  '剂量',
  '用药',
  '治疗',
  '首选',
  '过敏',
  '禁忌',
  '手术',
  '处理',
  '静脉',
  '肌内',
  '注射',
  '滴注',
  'mg',
  'U/d',
  '万U',
  '小时',
]

function argValue(args, name, fallback) {
  const index = args.indexOf(name)
  if (index === -1 || index + 1 >= args.length) return fallback
  return args[index + 1]
}

function cleanText(value) {
  return String(value ?? '').replace(/\s+/g, ' ').trim()
}

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'))
}

function readJsonIfExists(filePath) {
  if (!fs.existsSync(filePath)) return null
  return readJson(filePath)
}

function ensureDir(dirPath) {
  fs.mkdirSync(dirPath, { recursive: true })
}

function itemText(item) {
  return [
    item.title,
    item.parent_entity,
    item.aspect,
    item.content,
    item.evidence,
    item.source_heading,
  ].map(cleanText).filter(Boolean).join('\n')
}

function needsSourceQa(item) {
  return item.verification_state === 'needs_review'
    || item.verification_state === 'rejected'
    || item.risk_class === 'needs_review'
}

function hasHighRiskTerm(item) {
  const text = itemText(item)
  return HIGH_RISK_TERMS.some((term) => text.includes(term))
}

function normalizedAnchorSet(normalizedPayload) {
  const anchors = new Set()
  for (const node of normalizedPayload?.nodes ?? []) {
    const sourceSpan = node.source_span ?? {}
    const artifactId = cleanText(sourceSpan.artifact_id)
    const itemIndex = sourceSpan.item_index ?? 0
    if (artifactId) anchors.add(`${artifactId}:${itemIndex}`)
  }
  return anchors
}

function sourceArtifacts(evidencePayload) {
  const artifacts = evidencePayload?.artifacts
    ?? evidencePayload?.evidence_artifacts
    ?? evidencePayload?.items
    ?? []
  return Array.isArray(artifacts) ? artifacts.filter((item) => item && typeof item === 'object') : []
}

function sourceArtifactContextIndex(evidencePayload) {
  const artifacts = sourceArtifacts(evidencePayload)
    .map((artifact, index) => ({
      id: cleanText(artifact.id),
      pageStart: artifact.page_start ?? null,
      pageEnd: artifact.page_end ?? artifact.page_start ?? null,
      sourceOrder: artifact.source_order ?? index,
      sourceHeading: cleanText(artifact.source_heading),
      rawText: cleanText(artifact.raw_text),
    }))
    .filter((artifact) => artifact.id)
    .sort((left, right) =>
      (left.pageStart ?? 0) - (right.pageStart ?? 0)
      || (left.sourceOrder ?? 0) - (right.sourceOrder ?? 0),
    )

  const byId = new Map(artifacts.map((artifact) => [artifact.id, artifact]))

  return {
    contextFor(artifactId, radius = 3) {
      const targetIndex = artifacts.findIndex((artifact) => artifact.id === artifactId)
      if (targetIndex === -1) return null
      const target = artifacts[targetIndex]
      const neighbors = artifacts
        .slice(Math.max(0, targetIndex - radius), targetIndex + radius + 1)
        .filter((artifact) => artifact.pageStart === target.pageStart)
      return {
        target,
        nearbyArtifacts: neighbors,
        reconstructedNearbyText: neighbors.map((artifact) => artifact.rawText).filter(Boolean).join(''),
      }
    },
    has(artifactId) {
      return byId.has(artifactId)
    },
  }
}

function displayEvidenceIndex(displayPayload) {
  const byArtifactAndText = new Map()
  const flattenDisplayItems = (items = []) => items.flatMap((item) => [
    ...flattenDisplayItems(Array.isArray(item.children) ? item.children : []),
    item,
  ])
  for (const node of displayPayload?.nodes ?? []) {
    const display = node.display ?? {}
    const displayItems = flattenDisplayItems(Array.isArray(display.items) ? display.items : [])
    for (const evidence of node.evidence_items ?? []) {
      const artifactId = cleanText(evidence.artifact_id)
      const evidenceText = cleanText(evidence.text)
      if (!artifactId || !evidenceText) continue
      const normalizedEvidenceText = normalizeSpanText(evidenceText)
      const displayItem = displayItems.find((item) => {
        const artifactIds = Array.isArray(item.evidence_artifact_ids) ? item.evidence_artifact_ids.map(cleanText) : []
        if (artifactIds.includes(artifactId)) return true
        const bodyText = cleanText(item.body)
        return bodyText === evidenceText || normalizeSpanText(bodyText) === normalizedEvidenceText
      })
      const publicationState = displayItem?.publication_state ?? node.publication_state ?? null
      const key = `${artifactId}:${evidenceText}`
      const indexEntry = {
        nodeId: node.id ?? null,
        renderType: node.render_type ?? null,
        publicationState,
        nodePublicationState: node.publication_state ?? null,
        itemPublicationState: displayItem?.publication_state ?? null,
        displayItemMatched: Boolean(displayItem),
        displayTitle: cleanText(display.title),
        displayItemTitle: cleanText(displayItem?.title) || null,
        pageLabel: cleanText(display.page_label),
        sourceHeading: cleanText(display.source_heading),
        groupTopic: cleanText(node.group?.topic) || null,
      }
      byArtifactAndText.set(key, indexEntry)
      if (normalizedEvidenceText) {
        byArtifactAndText.set(`${artifactId}:normalized:${normalizedEvidenceText}`, indexEntry)
      }
    }
  }
  return byArtifactAndText
}

function displayPresenceForItem(item, displayIndex) {
  const artifactId = cleanText(item.artifact_id)
  const evidence = cleanText(item.evidence)
  const normalizedEvidence = normalizeSpanText(evidence)
  const match = displayIndex.get(`${artifactId}:${evidence}`)
    ?? displayIndex.get(`${artifactId}:normalized:${normalizedEvidence}`)
  if (!match) {
    return {
      presence: 'absent',
      nodeId: null,
      renderType: null,
      publicationState: null,
      displayTitle: null,
      pageLabel: null,
      sourceHeading: null,
      groupTopic: null,
    }
  }
  const presence = match.publicationState === 'evidence_only'
    ? 'evidence_only'
    : match.displayItemMatched
      ? 'organized'
      : 'attached_evidence'
  return {
    presence,
    ...match,
  }
}

function normalizeSpanText(value) {
  return cleanText(value)
    .replace(/\p{C}/gu, '')
    .replace(/[\s.,;:!?()[\]{}"'`“”‘’，。；：！？（）【】《》、\-—]/g, '')
    .toLowerCase()
}

function hasNormalizedSpan(haystack, needle) {
  const normalizedNeedle = normalizeSpanText(needle)
  if (!normalizedNeedle) return false
  return normalizeSpanText(haystack).includes(normalizedNeedle)
}

function extractionIssueForItem({
  item,
  sourceEvidenceVisible,
  appDisplay,
  sourceArtifactContext,
}) {
  if (sourceEvidenceVisible) {
    return {
      type: 'none',
      severity: 'none',
      detail: appDisplay.presence === 'attached_evidence'
        ? 'Source evidence is attached to an organized item but is not promoted as organized display copy.'
        : 'Source evidence is visible as evidence-only material in the display contract.',
    }
  }

  if (!sourceArtifactContext) {
    return {
      type: 'source_artifact_context_missing',
      severity: 'warning',
      detail: 'Source artifact context is missing; extraction span cannot be repaired from local artifacts.',
    }
  }

  if (item.verification_state === 'rejected') {
    const targetText = sourceArtifactContext.target?.rawText ?? ''
    const sourceEvidence = cleanText(item.evidence)
    const nearbyText = sourceArtifactContext.reconstructedNearbyText ?? ''
    const targetContainsEvidence = hasNormalizedSpan(targetText, sourceEvidence)
    const evidenceContainsTarget = hasNormalizedSpan(sourceEvidence, targetText)
    const nearbyContainsEvidence = hasNormalizedSpan(nearbyText, sourceEvidence)

    if (targetContainsEvidence) {
      return {
        type: 'single_artifact_punctuation_or_partial_span_mismatch',
        severity: 'warning',
        detail:
          'Synthesized evidence matches the bound artifact after normalization; verifier punctuation/span tolerance should be repaired.',
      }
    }

    if (nearbyContainsEvidence) {
      return {
        type: 'cross_artifact_continuous_span_bound_to_partial_artifact',
        severity: 'warning',
        detail:
          'Synthesized evidence is continuous in nearby source text but was bound to only part of that source span.',
      }
    }

    if (evidenceContainsTarget && !nearbyContainsEvidence) {
      return {
        type: 'cross_artifact_compressed_span',
        severity: 'warning',
        detail:
          'Synthesized evidence contains the bound artifact text but is not a continuous span in nearby source artifacts.',
      }
    }

    return {
      type: 'rejected_source_span_mismatch',
      severity: 'warning',
      detail: 'Synthesized evidence does not match the bound source artifact.',
    }
  }

  if (appDisplay.presence === 'organized') {
    return {
      type: 'unexpected_organized_display',
      severity: 'warning',
      detail: 'Source QA material appears in the display contract as organized content instead of evidence-only material.',
    }
  }

  return {
    type: 'display_contract_missing_evidence',
    severity: 'warning',
    detail: 'Source QA material is missing from the app display contract.',
  }
}

function qaReason(item, highRisk) {
  if (item.verification_state === 'rejected') return 'source_extraction_rejected_qa'
  if (highRisk) return 'high_risk_source_extraction_qa'
  if (item.verification_state === 'needs_review') return 'verification_state_source_qa'
  return 'risk_class_source_qa'
}

function buildQueueItem(item, {
  textbookId,
  sectionId,
  normalizedAnchors,
  displayIndex,
  sourceContextIndex,
}) {
  const artifactId = cleanText(item.artifact_id)
  const itemIndex = item.item_index ?? 0
  const anchorKey = `${artifactId}:${itemIndex}`
  const highRisk = hasHighRiskTerm(item)
  const normalizedPresence = normalizedAnchors.has(anchorKey) ? 'present' : 'absent'
  const appDisplay = displayPresenceForItem(item, displayIndex)
  const sourceEvidenceVisible = (
    appDisplay.presence === 'evidence_only'
    || appDisplay.presence === 'attached_evidence'
  )
    && item.verification_state !== 'rejected'
  const sourceArtifactContext = sourceEvidenceVisible
    ? null
    : sourceContextIndex.contextFor(artifactId)
  const extractionIssue = extractionIssueForItem({
    item,
    sourceEvidenceVisible,
    appDisplay,
    sourceArtifactContext,
  })

  return {
    id: anchorKey,
    textbookId,
    sectionId,
    title: cleanText(item.title),
    parentEntity: cleanText(item.parent_entity) || null,
    aspect: cleanText(item.aspect) || null,
    riskClass: item.risk_class ?? null,
    verificationState: item.verification_state ?? null,
    qaReason: qaReason(item, highRisk),
    requiredQaRole: 'source_qa_reviewer',
    needsSourceQa: true,
    organizedConclusionVisible: false,
    sourceEvidenceVisible,
    publicationAction: sourceEvidenceVisible
      ? appDisplay.presence === 'attached_evidence'
        ? 'show_as_expandable_source_evidence_only'
        : 'show_source_evidence_only'
      : item.verification_state === 'rejected'
        ? 'fix_rejected_source_extraction_before_display'
        : 'source_evidence_missing_from_display_contract',
    displayMode: sourceEvidenceVisible
      ? appDisplay.presence === 'attached_evidence'
        ? 'evidence_attachment'
        : 'evidence_only'
      : 'missing_from_display_contract',
    organizedNormalizedPresence: normalizedPresence,
    appDisplay,
    sourceLocator: {
      artifactId,
      itemIndex,
      sourceHeading: cleanText(item.source_heading),
      pageStart: item.page_start ?? null,
      pageEnd: item.page_end ?? null,
    },
    organizedStatement: cleanText(item.content),
    sourceEvidence: cleanText(item.evidence),
    extractionIssue,
    sourceArtifactContext,
    extractionNotes: item.verification_notes ?? [],
  }
}

function countBy(items, keyFn) {
  const counts = {}
  for (const item of items) {
    const key = keyFn(item)
    counts[key] = (counts[key] ?? 0) + 1
  }
  return counts
}

function addCounts(left = {}, right = {}) {
  const merged = { ...left }
  for (const [key, value] of Object.entries(right ?? {})) {
    merged[key] = (merged[key] ?? 0) + value
  }
  return merged
}

function listSectionIds(sourceRoot) {
  if (!fs.existsSync(sourceRoot)) return []
  return fs.readdirSync(sourceRoot)
    .filter((fileName) => fileName.endsWith('.evidence.synthesis.json'))
    .map((fileName) => fileName.slice(0, -'.evidence.synthesis.json'.length))
    .sort()
}

function slugifiedSectionId(sectionId) {
  return cleanText(sectionId)
    .replace(/[^\w\u4e00-\u9fff]+/g, '_')
    .replace(/^_+|_+$/g, '')
}

function resolveSidecarPath(root, sectionId, suffix) {
  const candidates = [
    path.join(root, `${sectionId}.${suffix}.json`),
    path.join(root, `${slugifiedSectionId(sectionId)}.${suffix}.json`),
  ]
  return candidates.find((candidate) => fs.existsSync(candidate)) ?? candidates[0]
}

export function buildSourceQaQueue({
  textbookId = DEFAULT_BOOK_ID,
  sectionId = DEFAULT_SECTION_ID,
  sourceRoot = path.join(rootDir, 'generated', 'knowledge_nodes', textbookId),
  displayContractRoot = path.join(rootDir, 'generated', 'display_contracts', textbookId),
} = {}) {
  const synthesisPath = resolveSidecarPath(sourceRoot, sectionId, 'evidence.synthesis')
  const evidencePath = resolveSidecarPath(sourceRoot, sectionId, 'evidence')
  const normalizedPath = resolveSidecarPath(sourceRoot, sectionId, 'normalized')
  const displayContractPath = resolveSidecarPath(displayContractRoot, sectionId, 'display_contract')
  const synthesisPayload = readJson(synthesisPath)
  const evidencePayload = readJsonIfExists(evidencePath)
  const normalizedPayload = readJsonIfExists(normalizedPath)
  const displayPayload = readJsonIfExists(displayContractPath)
  const normalizedAnchors = normalizedAnchorSet(normalizedPayload)
  const displayIndex = displayEvidenceIndex(displayPayload)
  const sourceContextIndex = sourceArtifactContextIndex(evidencePayload)

  const items = (synthesisPayload.items ?? [])
    .filter((item) => item && typeof item === 'object' && needsSourceQa(item))
    .map((item) => buildQueueItem(item, {
      textbookId,
      sectionId,
      normalizedAnchors,
      displayIndex,
      sourceContextIndex,
    }))

  const highRiskItems = items.filter(
    (item) => item.qaReason === 'high_risk_source_extraction_qa',
  )
  const missingFromNormalized = items.filter((item) => item.organizedNormalizedPresence === 'absent')
  const missingFromDisplayContract = items.filter((item) => !item.sourceEvidenceVisible)
  const evidenceOnlyInDisplayContract = items.filter((item) => item.appDisplay.presence === 'evidence_only')
  const rejectedSourceExtraction = items.filter((item) => item.verificationState === 'rejected')
  const issueTypeCounts = countBy(items, (item) => item.extractionIssue?.type ?? 'unknown')

  return {
    version: SOURCE_QA_QUEUE_VERSION,
    textbookId,
    sectionId,
    queuePurpose:
      'Check source extraction precision, page locators, and evidence-only display. This is not a medical truth approval workflow.',
    source: {
      synthesisPath: path.relative(rootDir, synthesisPath),
      evidencePath: path.relative(rootDir, evidencePath),
      normalizedPath: path.relative(rootDir, normalizedPath),
      displayContractPath: path.relative(rootDir, displayContractPath),
    },
    summary: {
      itemCount: items.length,
      highRiskItemCount: highRiskItems.length,
      organizedConclusionHiddenCount: items.filter((item) => item.organizedConclusionVisible === false).length,
      sourceEvidenceVisibleCount: items.filter((item) => item.sourceEvidenceVisible === true).length,
      missingFromOrganizedNormalizedCount: missingFromNormalized.length,
      evidenceOnlyDisplayContractCount: evidenceOnlyInDisplayContract.length,
      missingFromDisplayContractCount: missingFromDisplayContract.length,
      rejectedSourceExtractionCount: rejectedSourceExtraction.length,
      missingSourceArtifactContextCount: missingFromDisplayContract.filter(
        (item) => !item.sourceArtifactContext,
      ).length,
      issueTypeCounts,
      requiredSourceQaCount: items.filter((item) => item.needsSourceQa).length,
    },
    items,
  }
}

export function buildSourceQaBookQueue({
  textbookId = DEFAULT_BOOK_ID,
  sourceRoot = path.join(rootDir, 'generated', 'knowledge_nodes', textbookId),
  displayContractRoot = path.join(rootDir, 'generated', 'display_contracts', textbookId),
} = {}) {
  const sectionIds = listSectionIds(sourceRoot)
  const sectionQueues = sectionIds.map((sectionId) =>
    buildSourceQaQueue({ textbookId, sectionId, sourceRoot, displayContractRoot }),
  )
  const summary = {
    sectionCount: sectionQueues.length,
    itemCount: 0,
    highRiskItemCount: 0,
    organizedConclusionHiddenCount: 0,
    sourceEvidenceVisibleCount: 0,
    missingFromOrganizedNormalizedCount: 0,
    evidenceOnlyDisplayContractCount: 0,
    missingFromDisplayContractCount: 0,
    rejectedSourceExtractionCount: 0,
    missingSourceArtifactContextCount: 0,
    issueTypeCounts: {},
    requiredSourceQaCount: 0,
  }

  for (const queue of sectionQueues) {
    for (const [key, value] of Object.entries(queue.summary)) {
      if (key === 'issueTypeCounts') continue
      if (typeof value === 'number') summary[key] += value
    }
    summary.issueTypeCounts = addCounts(summary.issueTypeCounts, queue.summary.issueTypeCounts)
  }

  return {
    version: SOURCE_QA_QUEUE_VERSION,
    textbookId,
    sectionId: null,
    scope: 'book',
    queuePurpose:
      'Check source extraction precision, page locators, and evidence-only display across all bundled EV1 sections. This is not a medical truth approval workflow.',
    source: {
      sourceRoot: path.relative(rootDir, sourceRoot),
      displayContractRoot: path.relative(rootDir, displayContractRoot),
    },
    summary,
    sections: sectionQueues.map((queue) => ({
      sectionId: queue.sectionId,
      summary: queue.summary,
      source: queue.source,
    })),
    items: sectionQueues.flatMap((queue) =>
      queue.items.map((item) => ({ ...item, sectionId: queue.sectionId })),
    ),
  }
}

function printPretty(queue, outputPath) {
  console.log(`EV1 source QA queue: ${queue.scope === 'book' ? 'all sections' : queue.sectionId}`)
  if (queue.scope === 'book') console.log(`Sections: ${queue.summary.sectionCount}`)
  console.log(`Items: ${queue.summary.itemCount}`)
  console.log(`High risk: ${queue.summary.highRiskItemCount}`)
  console.log(`Evidence-only visible: ${queue.summary.sourceEvidenceVisibleCount}`)
  console.log(`Missing from display contract: ${queue.summary.missingFromDisplayContractCount}`)
  console.log(`Missing from organized normalized: ${queue.summary.missingFromOrganizedNormalizedCount}`)
  if (outputPath) console.log(`Output: ${outputPath}`)
}

export function main() {
  const args = process.argv.slice(2)
  const textbookId = argValue(args, '--book-id', DEFAULT_BOOK_ID)
  const sectionId = argValue(args, '--section-id', DEFAULT_SECTION_ID)
  const sourceRoot = argValue(
    args,
    '--source-root',
    path.join(rootDir, 'generated', 'knowledge_nodes', textbookId),
  )
  const displayContractRoot = argValue(
    args,
    '--display-contract-root',
    path.join(rootDir, 'generated', 'display_contracts', textbookId),
  )
  const outRoot = argValue(args, '--out-root', path.join(rootDir, 'generated', 'source_qa_queue', textbookId))
  const stdoutOnly = args.includes('--stdout-only')
  const pretty = args.includes('--pretty')
  const allSections = args.includes('--all')

  const queue = allSections
    ? buildSourceQaBookQueue({ textbookId, sourceRoot, displayContractRoot })
    : buildSourceQaQueue({ textbookId, sectionId, sourceRoot, displayContractRoot })
  const outputPath = path.join(outRoot, `${allSections ? '_all' : sectionId}.source_qa.json`)

  if (!stdoutOnly) {
    ensureDir(outRoot)
    fs.writeFileSync(outputPath, `${JSON.stringify(queue, null, 2)}\n`, 'utf8')
  }

  if (pretty) {
    printPretty(queue, stdoutOnly ? null : path.relative(rootDir, outputPath))
  } else {
    console.log(JSON.stringify(queue, null, 2))
  }
}

export { buildSourceQaQueue as buildReviewQueue }

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  main()
}
