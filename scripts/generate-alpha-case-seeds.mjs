import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import { ALPHA_CASE_LIBRARY } from '../shared/alpha-case-library.ts'
import { validateCaseQuality } from '../shared/case-quality.ts'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const outputPath = path.join(root, 'supabase', 'seeds', '002_alpha_case_library.sql')

function sqlQuote(value) {
  return `'${String(value).replace(/'/g, "''")}'`
}

function sqlString(value) {
  return `'${JSON.stringify(value).replace(/'/g, "''")}'::jsonb`
}

const lines = [
  '-- Alpha case library: 15 medically reviewed demo cases for local and CI validation.',
  '-- Reviewer id is a demo placeholder; replace with real reviewer ids before production.',
  '',
  "DELETE FROM case_templates WHERE case_code LIKE 'CC_CP_%';",
  '',
]

let errorCount = 0
for (const record of ALPHA_CASE_LIBRARY) {
  const issues = validateCaseQuality(record)
  if (issues.length > 0) {
    errorCount += issues.length
    for (const issue of issues) {
      console.error(`ERROR ${record.case_code} ${issue.path}: ${issue.message}`)
    }
    continue
  }

  lines.push(
    `INSERT INTO case_templates (` +
      `id, case_code, title, chief_complaint, specialty, difficulty, estimated_minutes, ` +
      `demographics, patient_world, ground_truth, scoring_rubric, ` +
      `is_active, review_status, reviewed_by, reviewed_at` +
      `) VALUES (` +
      `${sqlQuote(record.id)}, ${sqlQuote(record.case_code)}, ${sqlQuote(record.title)}, ${sqlQuote(record.chief_complaint)}, ` +
      `${sqlQuote(record.specialty ?? 'general')}, ${sqlQuote(record.difficulty)}, 15, ` +
      `${sqlString(record.demographics)}, ${sqlString(record.patient_world)}, ` +
      `${sqlString(record.ground_truth)}, ${sqlString(record.scoring_rubric)}, ` +
      `true, 'approved', ${sqlQuote(record.reviewed_by)}, ${sqlQuote(record.reviewed_at)}` +
      `) ON CONFLICT (id) DO UPDATE SET ` +
      `title = EXCLUDED.title, ` +
      `demographics = EXCLUDED.demographics, ` +
      `patient_world = EXCLUDED.patient_world, ` +
      `ground_truth = EXCLUDED.ground_truth, ` +
      `scoring_rubric = EXCLUDED.scoring_rubric, ` +
      `is_active = EXCLUDED.is_active, ` +
      `review_status = EXCLUDED.review_status, ` +
      `reviewed_by = EXCLUDED.reviewed_by, ` +
      `reviewed_at = EXCLUDED.reviewed_at;`,
    '',
  )
}

if (errorCount > 0) {
  process.exitCode = 1
} else {
  fs.writeFileSync(outputPath, `${lines.join('\n')}\n`, 'utf8')
  console.log(`Wrote ${ALPHA_CASE_LIBRARY.length} cases to ${outputPath}`)
}