import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const token = process.env.SUPABASE_ACCESS_TOKEN
const projectRef = process.env.SUPABASE_PROJECT_REF || 'xbccofxlbpazwtcfjgcr'

function projectRefFromUrl(value) {
  try {
    return new URL(value).hostname.split('.')[0]
  } catch {
    return null
  }
}

async function runQuery(query) {
  const response = await fetch(`https://api.supabase.com/v1/projects/${projectRef}/database/query`, {
    method: 'POST',
    headers: {
      Authorization: `Bearer ${token}`,
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ query }),
  })
  const text = await response.text()
  if (!response.ok) {
    throw new Error(`HTTP ${response.status}: ${text}`)
  }
  return text
}

function loadSqlFiles() {
  const migrationsDir = path.join(root, 'supabase', 'migrations')
  const migrationFiles = fs
    .readdirSync(migrationsDir)
    .filter((name) => /^\d{3}_.+\.sql$/.test(name))
    .sort()
    .map((name) => path.join(migrationsDir, name))

  return migrationFiles
}

async function main() {
  if (!token) {
    console.error('SUPABASE_ACCESS_TOKEN is required')
    process.exitCode = 2
    return
  }

  const urlRef = projectRefFromUrl(
    process.env.SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL || '',
  )
  const ref = urlRef || projectRef

  for (const file of loadSqlFiles()) {
    const sql = fs.readFileSync(file, 'utf8').trim()
    if (!sql) continue
    const label = path.basename(file)
    process.stdout.write(`Applying ${label}... `)
    try {
      await fetch(`https://api.supabase.com/v1/projects/${ref}/database/query`, {
        method: 'POST',
        headers: {
          Authorization: `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ query: sql }),
      }).then(async (response) => {
        const text = await response.text()
        if (!response.ok) throw new Error(`HTTP ${response.status}: ${text}`)
      })
      console.log('ok')
    } catch (error) {
      console.log('fail')
      console.error(error instanceof Error ? error.message : String(error))
      process.exitCode = 1
      return
    }
  }

  console.log('All SQL files applied via Management API.')
}

main().catch((error) => {
  console.error(error)
  process.exitCode = 1
})