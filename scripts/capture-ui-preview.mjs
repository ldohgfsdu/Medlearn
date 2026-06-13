import { chromium } from 'playwright'
import { mkdirSync } from 'node:fs'
import { join } from 'node:path'

const BASE = process.env.PREVIEW_BASE_URL || 'http://localhost:8082'
const OUT = join(process.cwd(), 'dogfood-output', 'screenshots', 'ui-ux-20260613')

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