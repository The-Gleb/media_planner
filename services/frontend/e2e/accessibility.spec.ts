import { expect, test } from '@playwright/test'
import { clearSimulation, createCampaign } from './helpers'

test.use({ viewport: { width: 768, height: 900 } })
test.afterEach(async ({ request }) => clearSimulation(request))

test('supports the primary keyboard path without page overflow', async ({ page, request }) => {
  await clearSimulation(request)
  await createCampaign(page, 1)
  await page.getByRole('button', { name: 'Один час' }).focus()
  await page.keyboard.press('Enter')
  await expect(page.getByRole('region', { name: 'Точные наблюдения последнего часа' })).toBeVisible()
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth)
  expect(overflow).toBe(false)
})
