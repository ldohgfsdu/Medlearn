import assert from 'node:assert/strict'
import fs from 'node:fs'
import path from 'node:path'
import test from 'node:test'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '..')
const configPath = path.join(repoRoot, 'site', '.vitepress', 'config.mts')

test('obsidian nav generator script exists and config is parseable', () => {
  const scriptPath = path.join(repoRoot, 'scripts', 'generate-obsidian-doc-nav.mjs')
  assert.ok(fs.existsSync(scriptPath))

  const configSource = fs.readFileSync(configPath, 'utf8')
  assert.match(configSource, /nav:\s*\[/)
  assert.match(configSource, /sidebar:\s*\{/)
  assert.match(configSource, /\/guide\/introduction/)
  assert.match(configSource, /\/dev\/architecture/)
})

test('setup-obsidian-links script defines expected junction targets', () => {
  const scriptPath = path.join(repoRoot, 'scripts', 'setup-obsidian-links.ps1')
  const source = fs.readFileSync(scriptPath, 'utf8')
  assert.match(source, /site/)
  assert.match(source, /docs/)
  assert.match(source, /MedLearn Vault/)
  assert.match(source, /\.site/)
  assert.match(source, /\.docs/)
  assert.match(source, /10 发布文档/)
})