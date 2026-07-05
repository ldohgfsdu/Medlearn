import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const rootDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')

function readJson(relativePath) {
  return JSON.parse(fs.readFileSync(path.join(rootDir, relativePath), 'utf8'))
}

const packageJson = readJson('package.json')
const packageLock = readJson('package-lock.json')
const appJson = readJson('app.json')
const easJson = readJson('eas.json')

const authoritativeVersion = packageJson.version
const errors = []

if (!/^\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?$/u.test(authoritativeVersion)) {
  errors.push(`package.json version is not valid SemVer: ${authoritativeVersion}`)
}
if (packageLock.version !== authoritativeVersion) {
  errors.push(`package-lock.json version ${packageLock.version} != ${authoritativeVersion}`)
}
if (packageLock.packages?.['']?.version !== authoritativeVersion) {
  errors.push(
    `package-lock.json root package version ${packageLock.packages?.['']?.version} != ${authoritativeVersion}`,
  )
}
if (appJson.expo?.version !== authoritativeVersion) {
  errors.push(`app.json expo.version ${appJson.expo?.version} != ${authoritativeVersion}`)
}
if (easJson.cli?.appVersionSource !== 'local') {
  errors.push('eas.json must keep cli.appVersionSource="local"')
}
if (!Number.isInteger(appJson.expo?.android?.versionCode) || appJson.expo.android.versionCode <= 0) {
  errors.push('app.json android.versionCode must be a positive integer')
}
if (!/^\d+$/u.test(String(appJson.expo?.ios?.buildNumber ?? ''))) {
  errors.push('app.json ios.buildNumber must be a numeric string')
}

if (errors.length > 0) {
  console.error('Project version contract failed:')
  for (const error of errors) console.error(`- ${error}`)
  process.exit(1)
}

console.log(
  `Project version contract passed: ${authoritativeVersion} `
  + `(android ${appJson.expo.android.versionCode}, ios ${appJson.expo.ios.buildNumber})`,
)
