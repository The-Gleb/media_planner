import { expect, test } from '@playwright/test'
import { clearSimulation, createCampaign } from './helpers'

test.afterEach(async ({ request }) => clearSimulation(request))

test('shows an exact plan-first summary and paged allocation matrix', async ({ page, request }) => {
  await clearSimulation(request)
  const calls: string[] = []
  page.on('request', (outgoing) => {
    if ((outgoing.method() === 'POST' && outgoing.url().includes('/planner-api/v1/plans'))
      || (outgoing.method() === 'PUT' && outgoing.url().includes('/api/v1/simulations/'))) calls.push(outgoing.url())
  })
  await createCampaign(page, 25)
  expect(calls[0]).toContain('/planner-api/v1/plans')
  expect(calls[1]).toContain('/api/v1/simulations/')
  await expect(page.getByText('Страница 1 из 2')).toBeVisible()
  await page.getByRole('button', { name: 'Далее' }).click()
  await expect(page.getByText('Страница 2 из 2')).toBeVisible()
  await expect(page.getByRole('region', { name: 'Точное распределение бюджета по часам и каналам' })).toBeVisible()
})
