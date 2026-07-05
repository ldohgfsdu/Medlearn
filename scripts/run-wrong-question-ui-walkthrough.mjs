import { spawn, spawnSync } from 'node:child_process'
import fs from 'node:fs'
import path from 'node:path'
import { performance } from 'node:perf_hooks'
import { fileURLToPath } from 'node:url'

import { REAL_WRONG_QUESTION_CASES } from '../tests/fixtures/wrong-question-real-cases.js'

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const args = new Map(
  process.argv.slice(2).map((arg) => {
    const [key, ...rest] = arg.replace(/^--/, '').split('=')
    return [key, rest.join('=') || 'true']
  }),
)
const caseId = args.get('case') || 'rq-resp-001'
const variant = args.get('variant') || 'full_context'
const port = Number(args.get('port') || 8095)
const targetCase = REAL_WRONG_QUESTION_CASES.find((item) => item.id === caseId)

if (!targetCase) {
  throw new Error(`Unknown wrong-question fixture: ${caseId}`)
}

if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error(`Invalid port: ${args.get('port')}`)
}

function stemAndOptionsOnly(input) {
  return input.split(/\n正确答案/)[0].trim()
}

function walkthroughInput(realCase) {
  if (variant === 'full_context') return realCase.input
  if (variant === 'stem_options_only') return stemAndOptionsOnly(realCase.input)
  throw new Error(`Unknown walkthrough variant: ${variant}`)
}

function npmCommand() {
  return process.platform === 'win32' ? 'npm.cmd' : 'npm'
}

function killProcessTree(child) {
  if (!child?.pid) return
  if (process.platform === 'win32') {
    spawnSync('taskkill', ['/pid', String(child.pid), '/t', '/f'], { stdio: 'ignore' })
    return
  }
  child.kill('SIGTERM')
}

function expoWebCommand() {
  if (process.platform === 'win32') {
    return {
      command: 'cmd.exe',
      args: ['/d', '/s', '/c', `npm run web -- --port ${port}`],
    }
  }
  return {
    command: npmCommand(),
    args: ['run', 'web', '--', '--port', String(port)],
  }
}

async function sleep(ms) {
  await new Promise((resolve) => setTimeout(resolve, ms))
}

async function waitForHttp(url, timeoutMs) {
  const deadline = Date.now() + timeoutMs
  let lastError
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url)
      if (response.status < 500) return
    } catch (error) {
      lastError = error
    }
    await sleep(1000)
  }
  throw new Error(`Expo web server did not become ready at ${url}: ${lastError?.message || 'timeout'}`)
}

function byTestId(page, testId) {
  return page.locator(`[data-testid="${testId}"], [data-test-id="${testId}"]`)
}

function includesAll(value, expected) {
  return expected.every((term) => value.includes(term))
}

const serverOutput = []
const webCommand = expoWebCommand()
const server = spawn(
  webCommand.command,
  webCommand.args,
  {
    cwd: root,
    env: {
      ...process.env,
      BROWSER: 'none',
      CI: '1',
      EXPO_NO_TELEMETRY: '1',
    },
    stdio: ['ignore', 'pipe', 'pipe'],
  },
)

server.stdout.on('data', (chunk) => serverOutput.push(chunk.toString()))
server.stderr.on('data', (chunk) => serverOutput.push(chunk.toString()))

let browser

try {
  const baseUrl = `http://127.0.0.1:${port}`
  await waitForHttp(baseUrl, 90_000)

  const { chromium } = await import('playwright')
  browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } })

  await page.goto(`${baseUrl}/map`, { waitUntil: 'domcontentloaded', timeout: 90_000 })
  await byTestId(page, 'wrong-question-input').fill(walkthroughInput(targetCase))

  const locateStartedAt = performance.now()
  await byTestId(page, 'wrong-question-locate-button').click()
  await byTestId(page, 'wrong-question-candidate').waitFor({ timeout: 30_000 })
  const candidateVisibleAt = performance.now()

  const candidateText = await byTestId(page, 'wrong-question-candidate').innerText()
  const openStartedAt = performance.now()
  await byTestId(page, 'wrong-question-open-candidate-button').click()
  await byTestId(page, 'wrong-question-target-card').waitFor({ timeout: 30_000 })
  const targetVisibleAt = performance.now()

  const targetCardText = await byTestId(page, 'wrong-question-target-card').innerText()
  const screenshotDir = path.join(root, 'artifacts')
  fs.mkdirSync(screenshotDir, { recursive: true })
  const screenshotPath = path.join(screenshotDir, `wrong-question-ui-walkthrough-${caseId}-${variant}.png`)
  await page.screenshot({ path: screenshotPath, fullPage: true })

  const result = {
    caseId,
    variant,
    route: {
      start: '/map',
      target: page.url().replace(baseUrl, ''),
    },
    matchedExpected: {
      candidateHasPage: candidateText.includes(targetCase.expected.pageLabel),
      targetHasPage: targetCardText.includes(targetCase.expected.pageLabel),
      targetHasEvidenceTerms: includesAll(targetCardText, targetCase.expected.evidenceIncludes),
    },
    observations: {
      inputToCandidateMs: Math.round(candidateVisibleAt - locateStartedAt),
      openCandidateToEvidenceMs: Math.round(targetVisibleAt - openStartedAt),
      timingIsDiagnosticOnly: true,
      highestFrictionStep: 'search',
      frictionReason:
        'The UI can carry a matched candidate into the target evidence card; the remaining hard step is selecting the correct grounded candidate from free-form wrong-question text.',
    },
    screenshotPath,
  }

  if (!result.matchedExpected.candidateHasPage || !result.matchedExpected.targetHasPage || !result.matchedExpected.targetHasEvidenceTerms) {
    throw new Error(`Wrong-question UI walkthrough did not reach expected evidence: ${JSON.stringify(result, null, 2)}`)
  }

  console.log(JSON.stringify(result, null, 2))
} catch (error) {
  console.error(error instanceof Error ? error.stack || error.message : String(error))
  console.error(serverOutput.slice(-40).join(''))
  process.exitCode = 1
} finally {
  if (browser) await browser.close()
  killProcessTree(server)
}
