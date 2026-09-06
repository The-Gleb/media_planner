import { expect, test } from '@playwright/test'
import { clearSimulation, createCampaign } from './helpers'

test.afterEach(async ({ request }) => clearSimulation(request))

test('runs sequentially to the campaign end', async ({ page, request }) => {
  await clearSimulation(request)
  await createCampaign(page, 24)
  await page.getByRole('button', { name: 'Запустить таймлапс' }).click()
  await expect(page.getByText('Кампания завершена')).toBeVisible({ timeout: 30_000 })
  await expect(page.getByText('0 ч')).toBeVisible()
  await expect(page.getByRole('button', { name: 'Один час' })).toBeDisabled()
})

test('stops before another hour starts', async ({ page, request }) => {
  await clearSimulation(request)
  await createCampaign(page, 2160)
  await page.getByRole('button', { name: 'Запустить таймлапс' }).click()
  await page.getByRole('button', { name: 'Пауза' }).click()
  await expect(page.getByText('Таймлапс на паузе')).toBeVisible({ timeout: 10_000 })
})

test('recovers a committed response with the same pending step', async ({ page, request }) => {
  await clearSimulation(request)
  await createCampaign(page, 2)
  await page.route('**/v1/simulations/*/steps', async (route) => {
    await route.fetch()
    await route.abort('failed')
  }, { times: 1 })
  await page.getByRole('button', { name: 'Запустить таймлапс' }).click()
  await expect(page.getByText(/Операция не выполнена/)).toBeVisible()
  await page.getByRole('button', { name: 'Запустить таймлапс' }).click()
  await expect(page.getByText('Кампания завершена')).toBeVisible()
})
