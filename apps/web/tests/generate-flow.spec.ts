import { test, expect } from '@playwright/test'

const BASE = process.env.E2E_BASE_URL || 'http://localhost:3000'

// Simple E2E for Generate page covering start -> live logs -> outputs and screenshots

test('dashboard renders and screenshot', async ({ page }) => {
  await page.goto(`${BASE}/dashboard`)
  await page.waitForLoadState('networkidle')
  await expect(page.getByText('Dashboard')).toBeVisible()
  await page.screenshot({ path: 'test-artifacts/dashboard.png', fullPage: true })
})

test('generate demo flow with screenshots', async ({ page }) => {
  test.setTimeout(240000)

  await page.goto(`${BASE}/generate`)
  await page.waitForLoadState('domcontentloaded')
  await expect(page.getByRole('heading', { name: 'Generate' })).toBeVisible()
  await page.screenshot({ path: 'test-artifacts/generate-initial.png', fullPage: true })

  // start job (demo default)
  const start = page.getByRole('button', { name: 'Start Pipeline' })
  await expect(start).toBeEnabled()
  await start.click()

  // wait for logs to appear
  await expect(page.getByText('Live Logs')).toBeVisible()
  await expect(page.getByText(/Starting|Running|pipeline/i).first()).toBeVisible({ timeout: 30000 })
  await page.screenshot({ path: 'test-artifacts/generate-running.png', fullPage: true })

  // wait for video or slides to appear
  await page.waitForFunction(() => !!document.querySelector('video, img'), { timeout: 180000 })
  await page.screenshot({ path: 'test-artifacts/generate-done.png', fullPage: true })
})

