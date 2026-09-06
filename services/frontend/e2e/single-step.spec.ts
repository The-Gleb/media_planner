import { expect, test } from '@playwright/test'
import { clearSimulation, createCampaign } from './helpers'

test.afterEach(async ({ request }) => clearSimulation(request))

test('advances one planned hour and exposes all metrics', async ({ page, request }) => {
  await clearSimulation(request)
  await createCampaign(page, 2)
  await page.getByRole('button', { name: 'Один час' }).click()
  await expect(page.getByRole('heading', { name: /Последний час/ })).toContainText('06:00:00Z')
  await expect(page.getByRole('tab')).toHaveCount(11)
  await expect(page.getByText('1 ч', { exact: true })).toBeVisible()
})
