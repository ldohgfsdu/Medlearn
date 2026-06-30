import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'

const BASE = process.env.PREVIEW_BASE_URL || 'http://localhost:8083'
const OUT = join(process.cwd(), 'artifacts', 'qa', 'screenshots', 'ai-settings-preview')
const EMAIL = process.env.PREVIEW_EMAIL || 'e2e-remote@medlearn.local'
const PASSWORD = process.env.PREVIEW_PASSWORD || 'MedlearnE2E2026!'

mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({
  viewport: { width: 390, height: 844 },
  deviceScaleFactor: 2,
  locale: 'zh-CN',
})
const page = await context.newPage()

async function shot(name) {
  await page.screenshot({ path: join(OUT, `${name}.png`), fullPage: true })
  console.log(`saved ${name}`)
}

try {
  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 60000 })
  await page.waitForTimeout(2500)
  await page.locator('input[placeholder="邮箱地址"], textarea[placeholder="邮箱地址"]').first().fill(EMAIL)
  await page.locator('input[placeholder="密码"], textarea[placeholder="密码"]').first().fill(PASSWORD)
  await page.getByText('登录', { exact: true }).click()
  await page.waitForTimeout(6000)

  await page.goto(`${BASE}/profile`, { waitUntil: 'domcontentloaded', timeout: 60000 })
  await page.waitForTimeout(3000)
  await shot('01-profile-menu')

  await page.getByText('AI 设置', { exact: true }).click()
  await page.waitForTimeout(3000)
  await shot('02-ai-settings-top')

  await page.getByText('DeepSeek', { exact: true }).click()
  await page.waitForTimeout(1000)
  await shot('03-ai-settings-deepseek')

  await page.evaluate(() => window.scrollTo(0, document.body.scrollHeight))
  await page.waitForTimeout(1000)
  await shot('04-ai-settings-bottom')
} catch (error) {
  console.error('capture failed:', error.message)
  await shot('error-state')
}

await browser.close()
console.log(`done -> ${OUT}`)
