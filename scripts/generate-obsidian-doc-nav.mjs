#!/usr/bin/env node
/**
 * Generate Obsidian navigation from site/.vitepress/config.mts.
 * Wikilinks target ASCII junctions (.site / .docs); Chinese folders hold 目录.md only.
 */

import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const repoRoot = path.resolve(__dirname, '..')
const configPath = path.join(repoRoot, 'site', '.vitepress', 'config.mts')
const vaultRoot = path.join('F:', 'MedLearn Vault', 'Medlearn')
const vaultNavDir = path.join(vaultRoot, '00 导航')

const SITE_PREFIX = 'Medlearn/.site'
const DOCS_PREFIX = 'Medlearn/.docs'
const PUBLISHED_NAV_DIR = path.join(vaultRoot, '10 发布文档')
const ENGINEERING_NAV_DIR = path.join(vaultRoot, '11 工程文档')

function siteLink(vitepressLink) {
  if (vitepressLink === '/') return `${SITE_PREFIX}/index`
  const normalized = vitepressLink.replace(/^\//, '').replace(/\/$/, '')
  return `${SITE_PREFIX}/${normalized}`
}

function docsLink(filename) {
  return `${DOCS_PREFIX}/${filename.replace(/\.md$/, '')}`
}

function parseSidebar(configSource) {
  const groups = []
  const groupPattern = /\{\s*text:\s*'([^']+)',\s*items:\s*\[([\s\S]*?)\]\s*\}/g
  let match

  while ((match = groupPattern.exec(configSource)) !== null) {
    const title = match[1]
    const itemsBlock = match[2]
    const items = []
    const itemPattern = /\{\s*text:\s*'([^']+)',\s*link:\s*'([^']+)'\s*\}/g
    let itemMatch

    while ((itemMatch = itemPattern.exec(itemsBlock)) !== null) {
      items.push({ text: itemMatch[1], link: itemMatch[2] })
    }

    if (items.length > 0) groups.push({ title, items })
  }

  return groups
}

function parseNav(configSource) {
  const nav = []
  const navBlock = configSource.match(/nav:\s*\[([\s\S]*?)\],\s*\n\s*sidebar:/)
  if (!navBlock) return nav

  const itemPattern = /\{\s*text:\s*'([^']+)',\s*link:\s*'([^']+)'\s*\}/g
  let match
  while ((match = itemPattern.exec(navBlock[1])) !== null) {
    nav.push({ text: match[1], link: match[2] })
  }
  return nav
}

function buildPublishedNavBody(nav, groups) {
  const lines = [
    '## 顶栏',
    '',
    ...nav.map((item) => `- [[${siteLink(item.link)}|${item.text}]]`),
    '',
    '## 侧栏',
    '',
  ]

  for (const group of groups) {
    lines.push(`### ${group.title}`, '')
    for (const item of group.items) {
      lines.push(`- [[${siteLink(item.link)}|${item.text}]]`)
    }
    lines.push('')
  }

  lines.push(
    '## 说明',
    '',
    '点上面链接即可编辑。真实文件在联接目录 `Medlearn/.site/`（= `F:\\ml\\site`），已隐藏以免乱码。',
    '改完后在 `F:\\ml` 执行 `git add site/` → `git commit` → `git push`。',
    '',
  )

  return lines.join('\n')
}

function buildEngineeringNavBody() {
  const docsDir = path.join(repoRoot, 'docs')
  const entries = fs.readdirSync(docsDir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.endsWith('.md'))
    .map((entry) => entry.name)
    .sort((a, b) => a.localeCompare(b, 'zh-CN'))

  const keyDocs = [
    'PROJECT_CONSTITUTION.md',
    'MVP_PRD_V2.md',
    'CURRENT_STATE.md',
    'PIPELINE_INDEX.md',
    'OBSIDIAN_VAULT.md',
    'API.md',
    'TECHNICAL_ARCHITECTURE.md',
  ]

  const lines = ['## 权威入口', '']

  for (const name of keyDocs) {
    if (entries.includes(name)) {
      const label = name.replace(/\.md$/, '')
      lines.push(`- [[${docsLink(name)}|${label}]]`)
    }
  }

  lines.push('', '## 全部 Markdown', '')
  for (const name of entries) {
    const label = name.replace(/\.md$/, '')
    lines.push(`- [[${docsLink(name)}|${label}]]`)
  }

  lines.push(
    '',
    '## 说明',
    '',
    '点链接编辑。真实文件在 `Medlearn/.docs/`（= `F:\\ml\\docs`），已隐藏以免乱码。',
    '改完后 `git add docs/` → `git commit` → `git push`。',
    '',
  )

  return lines.join('\n')
}

function wrapPage({ title, syncSource, body }) {
  const today = new Date().toISOString().slice(0, 10)
  return [
    '---',
    'area: medlearn',
    'category: 导航',
    'doc_type: index',
    'authority: generated',
    'status: active',
    `updated: ${today}`,
    `sync_source: ${syncSource}`,
    '---',
    '',
    `# ${title}`,
    '',
    `> 自动生成。运行 \`npm run docs:obsidian\` 更新。`,
    '',
    body,
  ].join('\n') + '\n'
}

function writeIfChanged(filePath, content) {
  const previous = fs.existsSync(filePath) ? fs.readFileSync(filePath, 'utf8') : null
  if (previous === content) {
    console.log(`unchanged ${filePath}`)
    return false
  }
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
  fs.writeFileSync(filePath, content, 'utf8')
  console.log(`updated ${filePath}`)
  return true
}

function main() {
  const configSource = fs.readFileSync(configPath, 'utf8')
  const nav = parseNav(configSource)
  const groups = parseSidebar(configSource)

  if (nav.length === 0 || groups.length === 0) {
    throw new Error('Failed to parse VitePress config.')
  }

  const publishedBody = buildPublishedNavBody(nav, groups)
  const engineeringBody = buildEngineeringNavBody()

  writeIfChanged(
    path.join(vaultNavDir, '发布文档站.md'),
    wrapPage({ title: '发布文档站', syncSource: 'site/.vitepress/config.mts', body: publishedBody }),
  )
  writeIfChanged(
    path.join(PUBLISHED_NAV_DIR, '目录.md'),
    wrapPage({ title: '发布文档', syncSource: 'site/.vitepress/config.mts', body: publishedBody }),
  )
  writeIfChanged(
    path.join(vaultNavDir, '工程文档索引.md'),
    wrapPage({ title: '工程文档', syncSource: 'docs/', body: engineeringBody }),
  )
  writeIfChanged(
    path.join(ENGINEERING_NAV_DIR, '目录.md'),
    wrapPage({ title: '工程文档', syncSource: 'docs/', body: engineeringBody }),
  )

  console.log('Obsidian doc nav generation complete.')
}

main()