import { expect, test } from '@playwright/test'
import { clearSimulation, createCampaign } from './helpers'

test.afterEach(async ({ request }) => clearSimulation(request))

test('compares channel and aggregate results with exact values', async ({ page, request }) => {
  await clearSimulation(request)
  await createCampaign(page, 3)
  for (let i = 0; i < 3; i++) await page.getByRole('button', { name: 'Один час' }).click()
  await page.getByRole('tab', { name: /Новый охват/ }).click()
  await expect(page.getByText('Итого (без дедупликации)')).toBeVisible()
  await page.getByLabel('Час', { exact: true }).selectOption('2026-09-03T06:00:00Z')
  await expect(page.getByLabel('Час', { exact: true })).toHaveValue('2026-09-03T06:00:00Z')
  await expect(page.getByText(/сумма по каналам, без дедупликации/).first()).toBeVisible()
})
