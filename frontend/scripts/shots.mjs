// Screenshots of every screen at 1440 and 1920 wide, in Google Chrome (never Edge).
//   node frontend/scripts/shots.mjs [baseUrl] [outDir]
import { mkdirSync } from 'node:fs'
import path from 'node:path'
import { chromium } from 'playwright-core'

const base = process.argv[2] ?? 'http://localhost:8000'
const out = process.argv[3] ?? path.resolve(import.meta.dirname, '../../docs/screenshots')
mkdirSync(out, { recursive: true })

const browser = await chromium.launch({ channel: 'chrome', headless: true })
const errors = []
for (const width of [1440, 1920]) {
  const ctx = await browser.newContext({ viewport: { width, height: width === 1440 ? 900 : 1080 } })
  const page = await ctx.newPage()
  page.on('console', (m) => m.type() === 'error' && errors.push(`${width} ${page.url()} ${m.text()}`))
  page.on('pageerror', (e) => errors.push(`${width} ${page.url()} ${e.message}`))

  const shot = async (name, url, prep) => {
    await page.goto(base + url, { waitUntil: 'domcontentloaded' })
    await page.waitForTimeout(1800)
    if (prep) await prep()
    await page.screenshot({ path: path.join(out, `${name}-${width}.png`) })
  }

  await shot('01-command', '/', async () => {
    const row = page.locator('aside .row-in').first()
    if (await row.count()) { await row.click(); await page.waitForTimeout(400) }
  })
  const incidents = await (await page.request.get(base + '/api/incidents')).json()
  if (incidents.length) {
    const top = incidents.slice().sort((a, b) => b.score - a.score)[0]
    await shot('02-incident', `/incidents/${top.id}`)
  }
  await shot('03-cameras', '/cameras')
  await shot('04-zones', '/zones')
  await shot('05-analytics', '/analytics')
  await shot('06-models', '/models')
  await ctx.close()
}
await browser.close()
console.log(errors.length ? `console errors:\n${errors.join('\n')}` : 'no console errors')
process.exit(0)
