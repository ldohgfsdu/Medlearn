import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'

const root = process.cwd()

test('legacy detail route files are removed', () => {
  for (const relative of [
    'app/topic.tsx',
    'app/node/[id].tsx',
    'app/knowledge/[id].tsx',
    'app/feynman.tsx',
  ]) {
    assert.equal(fs.existsSync(path.join(root, relative)), false, relative)
  }
})

test('route builders are the only business route constructors', () => {
  const source = fs.readFileSync(path.join(root, 'utils/routeBuilders.ts'), 'utf8')
  assert.match(source, /pathname: '\/disease\/\[id\]'/)
  assert.match(source, /pathname: '\/chapter\/\[id\]'/)
  assert.match(source, /content_class === 'confirmed_disease'/)
  assert.match(source, /node\.node_type === 'disease'/)
  assert.match(source, /node\.content_status === 'available'/)
  assert.match(source, /content_class === 'non_disease_knowledge'/)
  assert.match(source, /return null/)
})

test('MVP status migration separates node type from content status', () => {
  const source = fs.readFileSync(
    path.join(root, 'supabase/migrations/20260614021344_respiratory_knowledge_mvp_status.sql'),
    'utf8',
  )
  assert.match(source, /ADD COLUMN IF NOT EXISTS node_type/)
  assert.match(source, /ADD COLUMN IF NOT EXISTS content_status/)
  assert.match(source, /'overview'/)
  assert.match(source, /'in_progress'/)
  assert.match(source, /'unavailable'/)
})

test('database migration defines identity constraints and reasoning gate', () => {
  const source = fs.readFileSync(
    path.join(root, 'supabase/migrations/022_disease_detail_convergence.sql'),
    'utf8',
  )
  assert.match(source, /chapter_section_id TEXT PRIMARY KEY/)
  assert.match(source, /UNIQUE \(textbook_series_id, catalog_path\)/)
  assert.match(source, /disease_id TEXT PRIMARY KEY/)
  assert.match(source, /UNIQUE \(source_textbook_series_id, canonical_key\)/)
  assert.match(source, /knowledge_nodes_identity_consistency_check/)
  assert.match(source, /idx_knowledge_nodes_disease_aspect/)
  assert.match(source, /invalid_medical_logic/)
  assert.match(source, /resolution_status <> 'rejected'/)
})
