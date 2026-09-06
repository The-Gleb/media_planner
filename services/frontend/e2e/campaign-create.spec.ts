import { expect, test } from '@playwright/test'
import { clearSimulation, createCampaign } from './helpers'

test.afterEach(async ({ request }) => clearSimulation(request))

test('creates plan before Simulator and preserves validation input', async ({ page, request }) => {
  await clearSimulation(request)
  await page.goto('/')
  await expect(page.getByText(/Planner: Готов/)).toBeVisible()
  await page.getByLabel('ID симуляции').fill('-invalid')
  await page.getByRole('button', { name: 'Построить план и запустить' }).click()
  await expect(page.getByText(/1–128 символов/)).toBeVisible()
  await expect(page.getByLabel('ID симуляции')).toHaveValue('-invalid')
  await createCampaign(page)
  await expect(page.getByRole('heading', { name: 'Медиаплан' })).toBeVisible()
  await expect(page.getByText(/Прогноз плана/)).toBeVisible()
})

test('successful reset clears history while failed planning preserves run', async ({ page, request }) => {
  await clearSimulation(request)
  await createCampaign(page, 3)
  await page.getByRole('button', { name: 'Один час' }).click()
  await expect(page.getByRole('heading', { name: /Последний час/ })).toBeVisible()
  await page.getByLabel('Длительность, часов').fill('2')
  await page.route('**/planner-api/v1/plans', (route) => route.abort('failed'), { times: 1 })
  await page.getByRole('button', { name: 'Перепланировать, сбросить и запустить' }).click()
  await expect(page.getByRole('heading', { name: /Последний час/ })).toBeVisible()
  await page.getByRole('button', { name: 'Перепланировать, сбросить и запустить' }).click()
  await expect(page.getByText(/час 0 из 2/)).toBeVisible()
  await expect(page.getByRole('heading', { name: /Последний час/ })).not.toBeVisible()
})
