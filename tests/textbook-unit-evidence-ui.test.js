const test = require('node:test')
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')

const ROOT = path.join(__dirname, '..')
const UNIT_SOURCE = fs.readFileSync(
  path.join(ROOT, 'app/textbook/[sectionId]/unit/[unitId].tsx'),
  'utf8',
)

test('textbook unit screen uses explicit page kinds and compact PageViewer entry', () => {
  assert.doesNotMatch(UNIT_SOURCE, /formatTextbookPageReference\([^,]+,\s*'source'\)/)
  assert.match(UNIT_SOURCE, /formatTextbookPageReference\([^,]+,\s*'pdf'\)/)
  assert.match(UNIT_SOURCE, /compact/)
  assert.match(UNIT_SOURCE, /shouldShowStudyTitle/)
  assert.match(UNIT_SOURCE, /groupBlockWithoutHeader/)
  assert.doesNotMatch(UNIT_SOURCE, /fontStyle:\s*'italic'/)
  assert.match(UNIT_SOURCE, /viewerActionLabel \?/)
  assert.match(UNIT_SOURCE, /resolveCompactEvidenceSourceEntries/)
  assert.doesNotMatch(UNIT_SOURCE, /entriesWithPageViewer\.length === 0\) return null/)
})

test('textbook unit screen scroll offset avoids large top blank', () => {
  assert.match(UNIT_SOURCE, /scrollTo\(\{ y: Math\.max\(0, y - Spacing\.xs\)/)
  assert.doesNotMatch(UNIT_SOURCE, /paddingTop: Spacing\.base/)
})

test('textbook unit screen has CollapsibleBody with truncation awareness', () => {
  assert.match(UNIT_SOURCE, /function CollapsibleBody/)
  assert.match(UNIT_SOURCE, /BODY_PREVIEW_LIMIT/)
  assert.match(UNIT_SOURCE, /isTruncatedText/)
  assert.match(UNIT_SOURCE, /原文片段/)
  assert.match(UNIT_SOURCE, /展开全文/)
})

test('textbook unit screen auto-expands evidence for truncated body', () => {
  // Both StudyItemRow and StudyChildList should pass isTruncatedText(body)
  // into EvidenceToggle's defaultExpanded so the PageViewer button is
  // surfaced immediately for incomplete content.
  const matches = UNIT_SOURCE.match(/defaultExpanded=\{isTarget \|\| isTruncatedText\([^}]+\)\}/g)
  assert.ok(matches, 'expected at least one defaultExpanded with isTruncatedText')
  assert.ok(matches.length >= 2, 'expected both StudyItemRow and StudyChildList to use isTruncatedText in defaultExpanded')
})