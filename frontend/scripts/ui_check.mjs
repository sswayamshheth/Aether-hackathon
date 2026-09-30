// Interaction checks in Google Chrome: draw a zone, keyboard triage, add-camera form state.
//   node frontend/scripts/ui_check.mjs [baseUrl]
import { chromium } from 'playwright-core'

const base = process.argv[2] ?? 'http://localhost:8000'
const browser = await chromium.launch({ channel: 'chrome', headless: true })
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage()
const results = []
const check = (name, ok, detail = '') => console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${detail ? '  (' + detail + ')' : ''}`)
const api = async (path, init) => (await page.request.fetch(base + path, init)).json()

// 1. zone editor: three clicks on the frame, save, see it listed, delete it
await page.goto(base + '/zones', { waitUntil: 'domcontentloaded' })
await page.waitForSelector('svg.cursor-crosshair', { timeout: 15000 })
const box = await page.locator('svg.cursor-crosshair').boundingBox()
for (const [fx, fy] of [[0.2, 0.2], [0.5, 0.25], [0.35, 0.6]]) {
  await page.mouse.click(box.x + box.width * fx, box.y + box.height * fy)
}
await page.getByPlaceholder('Platform edge').fill('UI check zone')
await page.getByRole('button', { name: /Save zone/ }).click()
await page.waitForTimeout(800)
const zones = await api('/api/zones')
const made = zones.find((z) => z.name === 'UI check zone')
check('zone drawn with the mouse is saved', !!made, made ? `${made.points.length} points, kind ${made.kind}` : 'not found')
check('saved zone is listed in the editor', (await page.getByText('UI check zone').count()) > 0)
if (made) {
  await page.getByRole('button', { name: 'Delete UI check zone' }).click()
  await page.waitForTimeout(600)
  check('zone deleted from the editor', !(await api('/api/zones')).some((z) => z.id === made.id))
}

// 2. command view: J selects the top incident, Enter opens it, Esc goes back
await page.goto(base + '/', { waitUntil: 'domcontentloaded' })
await page.waitForTimeout(1500)
const open = (await api('/api/incidents')).filter((i) => i.status === 'new')
if (open.length) {
  await page.keyboard.press('j')
  await page.waitForTimeout(300)
  check('J selects an incident', (await page.getByRole('button', { name: /Confirm/ }).count()) > 0)
  await page.keyboard.press('Enter')
  await page.waitForTimeout(800)
  check('Enter opens the incident page', /\/incidents\/\d+$/.test(page.url()), page.url())
  check('incident page shows reasons', (await page.getByText('How the score was built').count()) > 0)
  await page.keyboard.press('Escape')
  await page.waitForTimeout(500)
  check('Esc returns to the command view', new URL(page.url()).pathname === '/')
} else {
  check('keyboard triage', false, 'no open incidents to test with')
}

// 3. camera wall: click to focus, Esc to return
const tiles = page.locator('section canvas')
if (await tiles.count()) {
  await tiles.first().click()
  await page.waitForTimeout(400)
  check('click focuses one camera', (await page.getByRole('button', { name: /Wall/ }).count()) > 0)
  await page.keyboard.press('Escape')
}

// 4. cameras page: the connect button stays disabled until the URL is a stream URL
await page.goto(base + '/cameras', { waitUntil: 'domcontentloaded' })
const connect = page.getByRole('button', { name: /Connect stream/ })
check('connect is disabled with no URL', await connect.isDisabled())
await page.getByPlaceholder('rtsp://localhost:8554/cam1').fill('not a url')
check('connect stays disabled for a bad URL', await connect.isDisabled())
await page.getByPlaceholder('rtsp://localhost:8554/cam1').fill('rtsp://localhost:8554/cam1')
check('connect enables for an rtsp URL', await connect.isEnabled())

await browser.close()
console.log(results.join('\n'))
process.exit(0)
