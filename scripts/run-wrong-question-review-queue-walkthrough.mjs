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
const caseId = args.get('case') || 'rq-resp-003'
const variant = args.get('variant') || 'stem_options_only'
const port = Number(args.get('port') || 8099)
const targetCase = REAL_WRONG_QUESTION_CASES.find((item) => item.id === caseId)
const storageKey = '@medlearn/wrong-question-records'

if (!targetCase) {
  throw new Error(`Unknown wrong-question fixture: ${caseId}`)
}

if (!Number.isInteger(port) || port < 1 || port > 65535) {
  throw new Error(`Invalid port: ${args.get('port')}`)
}

function stemAndOptionsOnly(input) {
  return input.split(/\n姝ｇ‘绛旀/)[0].trim()
}

function walkthroughInput(realCase) {
  if (variant === 'full_context') return realCase.input
  if (variant === 'stem_options_only') return stemAndOptionsOnly(realCase.input)
  throw new Error(`Unknown walkthrough variant: ${variant}`)
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
    command: 'npm',
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
  await page.evaluate((key) => {
    localStorage.removeItem(key)
  }, storageKey)
  await byTestId(page, 'wrong-question-input').fill(walkthroughInput(targetCase))

  const locateStartedAt = performance.now()
  await byTestId(page, 'wrong-question-locate-button').click()
  await byTestId(page, 'wrong-question-candidate').waitFor({ timeout: 30_000 })
  const candidateVisibleAt = performance.now()

  const candidateText = await byTestId(page, 'wrong-question-candidate').innerText()
  await byTestId(page, 'wrong-question-save-candidate-button').click()

  await page.goto(`${baseUrl}/wrong-questions`, { waitUntil: 'domcontentloaded', timeout: 30_000 })
  await byTestId(page, 'wrong-question-record').waitFor({ timeout: 30_000 })
  const recordText = await byTestId(page, 'wrong-question-record').innerText()
  await byTestId(page, 'wrong-question-record-reason-missed_clue').click()
  await page.waitForFunction(() => document.body.innerText.includes('漏看线索'), null, { timeout: 30_000 })
  const taggedRecordText = await byTestId(page, 'wrong-question-record').innerText()

  const openStartedAt = performance.now()
  await byTestId(page, 'wrong-question-record-open-textbook').click()
  await byTestId(page, 'wrong-question-target-card').waitFor({ timeout: 30_000 })
  const targetVisibleAt = performance.now()
  const targetCardText = await byTestId(page, 'wrong-question-target-card').innerText()
  const targetRoute = page.url().replace(baseUrl, '')

  await page.goto(`${baseUrl}/wrong-questions`, { waitUntil: 'domcontentloaded', timeout: 30_000 })
  await byTestId(page, 'wrong-question-record').waitFor({ timeout: 30_000 })
  await byTestId(page, 'wrong-question-record-toggle-reviewed').click()
  await byTestId(page, 'wrong-question-record').waitFor({ state: 'hidden', timeout: 30_000 })
  await byTestId(page, 'wrong-question-reviewed-segment').click()
  await byTestId(page, 'wrong-question-record').waitFor({ timeout: 30_000 })
  const reviewedRecordText = await byTestId(page, 'wrong-question-record').innerText()

  const screenshotDir = path.join(root, 'artifacts')
  fs.mkdirSync(screenshotDir, { recursive: true })
  const screenshotPath = path.join(
    screenshotDir,
    `wrong-question-review-queue-walkthrough-${caseId}-${variant}.png`,
  )
  await page.screenshot({ path: screenshotPath, fullPage: true })

  const result = {
    caseId,
    variant,
    route: {
      start: '/map',
      target: targetRoute,
      reviewedQueue: page.url().replace(baseUrl, ''),
    },
    matchedExpected: {
      candidateHasPage: candidateText.includes(targetCase.expected.pageLabel),
      recordHasPage: recordText.includes(targetCase.expected.pageLabel),
      recordHasMistakeReasonTag: taggedRecordText.includes('漏看线索'),
      targetHasPage: targetCardText.includes(targetCase.expected.pageLabel),
      targetHasEvidenceTerms: includesAll(targetCardText, targetCase.expected.evidenceIncludes),
      reviewedRecordStillGrounded: reviewedRecordText.includes(targetCase.expected.pageLabel),
      reviewedRecordKeepsMistakeReason: reviewedRecordText.includes('漏看线索'),
    },
    observations: {
      inputToCandidateMs: Math.round(candidateVisibleAt - locateStartedAt),
      openQueueRecordToEvidenceMs: Math.round(targetVisibleAt - openStartedAt),
      timingIsDiagnosticOnly: true,
      highestFrictionStep: 'review_queue',
      frictionReason:
        'This walkthrough verifies that a grounded candidate can be saved, reopened from the queue, and marked reviewed; it does not evaluate long-term retention.',
    },
    screenshotPath,
  }

  if (Object.values(result.matchedExpected).some((value) => !value)) {
    throw new Error(`Wrong-question review queue walkthrough failed: ${JSON.stringify(result, null, 2)}`)
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
