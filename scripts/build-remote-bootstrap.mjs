import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const migrationsDir = path.join(root, 'supabase', 'migrations')
const outputPath = path.join(root, 'scripts', 'remote-bootstrap.sql')

const migrationFiles = fs
  .readdirSync(migrationsDir)
  .filter((name) => /^\d{3}_.+\.sql$/.test(name))
  .sort()

const seedPath = path.join(root, 'supabase', 'seeds', '002_alpha_case_library.sql')
const parts = [
  '-- MedLearn remote bootstrap',
  '-- Apply in Supabase Dashboard -> SQL Editor when CLI access is unavailable.',
  '-- Includes migrations 001-019 and alpha case seeds.',
  '',
]

for (const file of migrationFiles) {
  parts.push(`-- >>> migration: ${file}`)
  parts.push(fs.readFileSync(path.join(migrationsDir, file), 'utf8').trim())
  parts.push('')
}

if (fs.existsSync(seedPath)) {
  parts.push('-- >>> seed: 002_alpha_case_library.sql')
  parts.push(fs.readFileSync(seedPath, 'utf8').trim())
  parts.push('')
}

fs.writeFileSync(outputPath, `${parts.join('\n')}\n`, 'utf8')
console.log(`Wrote ${outputPath} (${migrationFiles.length} migrations)`)