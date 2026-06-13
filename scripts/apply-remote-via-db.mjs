import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'
import pg from 'pg'

const { Client } = pg
const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const bootstrapPath = path.join(root, 'scripts', 'remote-bootstrap.sql')

async function main() {
  const databaseUrl = process.env.DATABASE_URL || process.env.SUPABASE_DB_URL
  if (!databaseUrl) {
    console.error('DATABASE_URL or SUPABASE_DB_URL is required for direct SQL apply.')
    process.exitCode = 2
    return
  }

  if (!fs.existsSync(bootstrapPath)) {
    console.error('Missing scripts/remote-bootstrap.sql. Run: npm run build:remote-bootstrap')
    process.exitCode = 2
    return
  }

  const sql = fs.readFileSync(bootstrapPath, 'utf8')
  const client = new Client({
    connectionString: databaseUrl,
    ssl: { rejectUnauthorized: false },
  })

  console.log('Applying remote bootstrap SQL via direct database connection...')
  await client.connect()
  try {
    await client.query(sql)
    console.log('Bootstrap SQL applied successfully.')
  } finally {
    await client.end()
  }
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error))
  process.exitCode = 1
})