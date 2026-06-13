import test from 'node:test'
import assert from 'node:assert/strict'
import { ALPHA_CASE_LIBRARY } from '../shared/alpha-case-library.ts'
import { validateCaseQuality } from '../shared/case-quality.ts'

test('alpha case library contains 15 approved cases', () => {
  assert.equal(ALPHA_CASE_LIBRARY.length, 15)
  const approved = ALPHA_CASE_LIBRARY.filter(
    (record) => record.review_status === 'approved' && record.is_active === true,
  )
  assert.equal(approved.length, 15)
})

test('alpha case library passes quality validation', () => {
  for (const record of ALPHA_CASE_LIBRARY) {
    const issues = validateCaseQuality(record)
    assert.deepEqual(
      issues,
      [],
      `${record.case_code} failed validation: ${issues.map((issue) => issue.path).join(', ')}`,
    )
  }
})