import { test, expect } from '@playwright/test'

const BASE = process.env.E2E_BASE_URL || 'http://localhost:3000'

// Full pipeline test per spec: start demo, wait for success, then verify slides and video pages

test('pipeline: generate -> slides -> video', async ({ page, context }) => {
  test.setTimeout(300_000)

  // Generate
  await page.goto(`${BASE}/generate`)
  await expect(page.getByRole('heading', { name: 'Generate' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Start Pipeline' })).toBeEnabled()
  await page.getByRole('button', { name: 'Start Pipeline' }).click()

  // Websocket/logs appearing
  await expect(page.getByText('Live Logs')).toBeVisible()
  await expect(page.getByText(/step 1\/5|Starting pipeline/i).first()).toBeVisible({ timeout: 15000 })

  // Wait for success text in status panel
  await expect(page.getByText(/State:\s*succeeded/i)).toBeVisible({ timeout: 180000 })

  // Slides Preview
  await page.goto(`${BASE}/slides`)
  await expect(page.getByRole('heading', { name: 'Slides Preview' })).toBeVisible()
  // At least one thumbnail should be visible
  const thumbnails = page.locator('img').first()
  await expect(thumbnails).toBeVisible({ timeout: 20000 })
  await page.screenshot({ path: 'test-artifacts/slides-preview-final.png', fullPage: true })
  // Try clicking download (if present)
  const [dl1] = await Promise.all([
    page.waitForEvent('download').catch(() => null),
    page.getByRole('button', { name: /Download All Images/i }).click().catch(() => null),
  ])
  if (dl1) { const path = await dl1.path(); console.log('Slides zip downloaded', path) }

  // Video Output
  await page.goto(`${BASE}/video`)
  await expect(page.getByRole('heading', { name: 'Video Output' })).toBeVisible()
  // Video element should exist
  await expect(page.locator('video')).toBeVisible({ timeout: 30000 })
  await page.screenshot({ path: 'test-artifacts/video-output-final.png', fullPage: true })
  // Attempt play
  await page.locator('video').evaluate((v: HTMLVideoElement) => v.play().catch(() => {}))
  // Try clicking download buttons if present
  const [dlv] = await Promise.all([
    page.waitForEvent('download').catch(() => null),
    page.getByRole('link', { name: /Download Video/i }).click().catch(() => null),
  ])
  if (dlv) { const path = await dlv.path(); console.log('Video downloaded', path) }
  const [dls] = await Promise.all([
    page.waitForEvent('download').catch(() => null),
    page.getByRole('link', { name: /Download Subtitles/i }).click().catch(() => null),
  ])
  if (dls) { const path = await dls.path(); console.log('Subtitles downloaded', path) }
})

