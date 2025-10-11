import { test, expect } from '@playwright/test'

const API = process.env.NEXT_PUBLIC_API_BASE || 'http://127.0.0.1:8001'

async function createJob(page) {
  const res = await page.request.post(`${API}/api/jobs`)
  expect(res.ok()).toBeTruthy()
  const data = await res.json()
  return data.job_id as string
}

test.describe('Video Gen UI basic flows', () => {
  test('home renders and health fetch works', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForFunction(() => getComputedStyle(document.body).display !== 'none')
    await expect(page.getByText('Video Generation UI')).toBeVisible()
  })

  test('navigate via sidebar: Dashboard -> Generate -> Results', async ({ page }) => {
    await page.goto('/')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForFunction(() => getComputedStyle(document.body).display !== 'none')

    await page.getByText('Dashboard', { exact: true }).click()

    await Promise.all([
      page.waitForURL('**/generate'),
      page.getByText('Generate', { exact: true }).click(),
    ])
    await expect(page.locator('h1', { hasText: 'Generate' })).toBeVisible()

    // interact with Select on Generate (Radix Select)
    await page.getByText('Select a model').click()
    await page.getByText('SDXL', { exact: true }).click()

    await page.getByText('Results', { exact: true }).click()
    await expect(page.locator('h1', { hasText: 'Results' })).toBeVisible()
  })

  test('results shows recent jobs and logs page streams', async ({ page }) => {
    // ensure a job exists
    const jobId = await createJob(page)

    // Results dropdown
    await page.goto('/results')
    await page.waitForLoadState('domcontentloaded')
    await page.waitForFunction(() => getComputedStyle(document.body).display !== 'none')
    await page.getByRole('button', { name: 'Recent jobs' }).click()
    await expect(page.getByRole('menu')).toBeVisible({ timeout: 15000 })
    await expect(page.getByRole('menuitem', { name: jobId })).toBeVisible({ timeout: 15000 })

    // Logs page with job id
    await page.goto(`/logs?jobId=${jobId}`)
    await page.waitForLoadState('domcontentloaded')
    await page.waitForFunction(() => getComputedStyle(document.body).display !== 'none')
    await expect(page.getByText(/Live Logs/)).toBeVisible()

    // Wait for some logs to appear
    await expect(page.getByText('Starting pipeline', { exact: false }).first()).toBeVisible({ timeout: 20000 })
  })
})

