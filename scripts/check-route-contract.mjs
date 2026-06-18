import fs from 'node:fs'
import path from 'node:path'
import process from 'node:process'

const root = process.cwd()
const sourceRoots = ['app', 'components', 'hooks', 'services', 'utils']
const allowedRawDetailPaths = new Set([
  path.normalize('app/disease/[id].tsx'),
  path.normalize('app/chapter/[id].tsx'),
  path.normalize('utils/routeBuilders.ts'),
])
const legacyPatterns = [
  /['"`]\/topic(?:['"`?])/,
  /['"`]\/node(?:\/|\[|['"`?])/,
  /['"`]\/knowledge(?:\/|\[|['"`?])/,
  /['"`]\/feynman(?:['"`?])/,
]
const rawDetailPatterns = [
  /['"`]\/disease\//,
  /['"`]\/chapter\//,
]

function walk(directory) {
  if (!fs.existsSync(directory)) return []
  return fs.readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const fullPath = path.join(directory, entry.name)
    return entry.isDirectory() ? walk(fullPath) : [fullPath]
  })
}

const violations = []
for (const sourceRoot of sourceRoots) {
  for (const filePath of walk(path.join(root, sourceRoot))) {
    if (!/\.[jt]sx?$/.test(filePath)) continue
    const relative = path.normalize(path.relative(root, filePath))
    const source = fs.readFileSync(filePath, 'utf8')

    for (const pattern of legacyPatterns) {
      if (pattern.test(source)) violations.push(`${relative}: legacy detail route`)
    }
    if (!allowedRawDetailPaths.has(relative)) {
      for (const pattern of rawDetailPatterns) {
        if (pattern.test(source)) violations.push(`${relative}: raw detail route`)
      }
    }
  }
}

if (violations.length) {
  console.error(violations.join('\n'))
  process.exit(1)
}

console.log('Route contract passed.')
