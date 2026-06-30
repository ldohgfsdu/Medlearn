import { chromium } from 'playwright'
import { mkdirSync, readFileSync, existsSync } from 'node:fs'
import { join } from 'node:path'

const BASE = process.env.PREVIEW_BASE_URL || 'http://localhost:8083'
const OUT = join(process.cwd(), 'artifacts', 'qa', 'screenshots', 'ui-ux-20260613')

function loadEnvValue(key) {
  if (process.env[key]) return process.env[key]
  const envPath = join(process.cwd(), '.env')
  if (!existsSync(envPath)) return undefined
  const line = readFileSync(envPath, 'utf8')
    .split(/\r?\n/)
    .find((entry) => entry.startsWith(`${key}=`))
  return line?.slice(key.length + 1).trim()
}

async function tryLogin(page) {
  const email = process.env.PREVIEW_EMAIL || loadEnvValue('PREVIEW_EMAIL')
  const password = process.env.PREVIEW_PASSWORD || loadEnvValue('PREVIEW_PASSWORD')
  if (!email || !password) return false

  await page.goto(`${BASE}/login`, { waitUntil: 'domcontentloaded', timeout: 45000 })
  await page.waitForTimeout(2000)
  await page.getByPlaceholder('邮箱地址').fill(email)
  await page.getByPlaceholder('密码').fill(password)
  await page.getByRole('button', { name: '登录' }).click()
  await page.waitForTimeout(4000)
  const url = page.url()
  return !url.includes('/login')
}

const routes = [
  { name: 'login', path: '/login', waitFor: 'text=Medlearn' },
  { name: 'search', path: '/search', waitFor: 'text=知识搜索' },
  { name: 'map', path: '/map', waitFor: 'text=知识地图' },
  { name: 'learn', path: '/learn', waitFor: 'text=知识地图' },
  { name: 'cases', path: '/cases', waitFor: 'text=病例' },
  { name: 'cases-history', path: '/cases?section=history', waitFor: 'text=病例记录' },
  { name: 'profile', path: '/profile', waitFor: 'text=个人中心' },
  { name: 'analytics', path: '/analytics', waitFor: 'text=学习报告' },
]

mkdirSync(OUT, { recursive: true })

const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({
  viewport: { width: 390, height: 844 },
  deviceScaleFactor: 2,
  locale: 'zh-CN',
})
const page = await context.newPage()
const loggedIn = await tryLogin(page)
console.log(loggedIn ? 'authenticated preview' : 'unauthenticated preview (login wall)')

for (const route of routes) {
  const url = `${BASE}${route.path}`
  try {
    await page.goto(url, { waitUntil: 'domcontentloaded', timeout: 45000 })
    await page.waitForTimeout(3000)
    try {
      await page.waitForSelector(route.waitFor, { timeout: 8000 })
    } catch {
      // Auth redirect may block some routes; still capture what rendered.
    }
    await page.screenshot({
      path: join(OUT, `${route.name}.png`),
      fullPage: true,
    })
    console.log(`saved ${route.name}`)
  } catch (error) {
    console.error(`failed ${route.name}:`, error.message)
  }
}

await browser.close()
console.log(`done -> ${OUT}`)
