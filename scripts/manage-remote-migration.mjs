import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const token = process.env.SUPABASE_ACCESS_TOKEN
const projectUrl = process.env.SUPABASE_URL || process.env.EXPO_PUBLIC_SUPABASE_URL

function projectRefFromUrl(value) {
  return new URL(value).hostname.split('.')[0]
}

async function runQuery(projectRef, query) {
  const response = await fetch(
    `https://api.supabase.com/v1/projects/${projectRef}/database/query`,
    {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ query }),
    },
  )
  const text = await response.text()
  if (!response.ok) throw new Error(`HTTP ${response.status}: ${text}`)
  return text ? JSON.parse(text) : []
}

async function readStatus(projectRef) {
  let migrations = []
  let historyAvailable = true
  try {
    migrations = await runQuery(
      projectRef,
      'select version, name from supabase_migrations.schema_migrations order by version',
    )
  } catch (error) {
    if (!String(error).includes('schema_migrations')) throw error
    historyAvailable = false
  }
  const historyColumns = historyAvailable
    ? await runQuery(
        projectRef,
        `select column_name, data_type
         from information_schema.columns
         where table_schema = 'supabase_migrations'
           and table_name = 'schema_migrations'
         order by ordinal_position`,
      )
    : []
  const convergenceColumns = await runQuery(
    projectRef,
    `select column_name
     from information_schema.columns
     where table_schema = 'public'
       and table_name = 'knowledge_nodes'
       and column_name in (
         'disease_id',
         'chapter_section_id',
         'aspect',
         'raw_aspect',
         'display_title',
         'content_class'
       )
     order by column_name`,
  )
  return { historyAvailable, migrations, historyColumns, convergenceColumns }
}

function parseMigration(fileName) {
  const match = /^(\d{3})_(.+)\.sql$/.exec(fileName)
  if (!match) throw new Error('Migration must match NNN_name.sql')
  const filePath = path.join(root, 'supabase', 'migrations', fileName)
  if (!fs.existsSync(filePath)) throw new Error(`Migration not found: ${filePath}`)
  return {
    version: match[1],
    name: match[2],
    sql: fs.readFileSync(filePath, 'utf8').trim(),
  }
}

function sqlLiteral(value) {
  return `'${String(value).replaceAll("'", "''")}'`
}

async function applyMigration(projectRef, fileName) {
  const migration = parseMigration(fileName)
  const status = await readStatus(projectRef)
  if (status.historyAvailable) {
    const historyColumnNames = new Set(status.historyColumns.map((column) => column.column_name))
    for (const required of ['version', 'name', 'statements']) {
      if (!historyColumnNames.has(required)) {
        throw new Error(`Migration history is missing required column: ${required}`)
      }
    }
    if (status.migrations.some((row) => row.version === migration.version)) {
      console.log(`Migration ${migration.version} already recorded; no changes made.`)
      return
    }
  }

  const delimiter = '$medlearn_migration$'
  if (migration.sql.includes(delimiter)) {
    throw new Error(`Migration contains reserved delimiter ${delimiter}`)
  }
  const historyInsert = status.historyAvailable
    ? `insert into supabase_migrations.schema_migrations(version, statements, name)
values (
  ${sqlLiteral(migration.version)},
  array[${delimiter}${migration.sql}${delimiter}],
  ${sqlLiteral(migration.name)}
);`
    : ''
  const transaction = `
begin;
${migration.sql}
${historyInsert}
commit;
`
  await runQuery(projectRef, transaction)
  const after = await readStatus(projectRef)
  const requiredColumns = new Set([
    'disease_id',
    'chapter_section_id',
    'aspect',
    'raw_aspect',
    'display_title',
    'content_class',
  ])
  const actualColumns = new Set(after.convergenceColumns.map((column) => column.column_name))
  if ([...requiredColumns].some((column) => !actualColumns.has(column))) {
    throw new Error(`Migration ${migration.version} did not create all convergence columns`)
  }
  if (
    after.historyAvailable
    && !after.migrations.some((row) => row.version === migration.version)
  ) {
    throw new Error(`Migration ${migration.version} executed but was not recorded`)
  }
  console.log(
    after.historyAvailable
      ? `Applied and recorded ${fileName}.`
      : `Applied ${fileName}; remote migration history table is unavailable.`,
  )
}

async function main() {
  if (!token || !projectUrl) {
    throw new Error('SUPABASE_ACCESS_TOKEN and SUPABASE_URL are required')
  }
  const [command = 'status', fileName] = process.argv.slice(2)
  const projectRef = projectRefFromUrl(projectUrl)
  if (command === 'status') {
    console.log(JSON.stringify(await readStatus(projectRef), null, 2))
    return
  }
  if (command === 'apply' && fileName) {
    await applyMigration(projectRef, fileName)
    return
  }
  throw new Error('Usage: manage-remote-migration.mjs status | apply NNN_name.sql')
}

main().catch((error) => {
  console.error(error instanceof Error ? error.message : String(error))
  process.exitCode = 1
})
