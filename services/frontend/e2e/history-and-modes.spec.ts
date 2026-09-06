import { expect, test } from '@playwright/test'
import { clearSimulation, createCampaign } from './helpers'

test.afterEach(async ({ request }) => clearSimulation(request))

test('archives a finished campaign, plans the next one from it and tracks plan versus fact', async ({ page, request }) => {
  await clearSimulation(request)
  await page.addInitScript(() => window.localStorage.clear())
  await createCampaign(page, 4)

  await expect(page.getByRole('heading', { name: 'План против факта' })).toBeVisible()
  await expect(page.getByText('публичный каталог')).toBeVisible()
  await expect(page.getByText(/Прошлых кампаний для этого world seed пока нет/)).toBeVisible()

  await page.getByRole('button', { name: 'Запустить таймлапс' }).click()
  await expect(page.getByText(/час 4 из 4/).first()).toBeVisible({ timeout: 60_000 })
  await expect(page.getByText('4 из 4', { exact: true }).first()).toBeVisible()
  await expect(page.getByText(/Доступно кампаний: 1/)).toBeVisible()

  await page.getByLabel('Стратегия').selectOption('optimized')
  await page.getByLabel('Исполнение').selectOption('frozen')
  await page.getByRole('button', { name: 'Перепланировать, сбросить и запустить' }).click()
  await expect(page.getByText('каталог + 1 прошл. камп.')).toBeVisible()
  await expect(page.locator('dd', { hasText: 'Замороженный план' })).toBeVisible()

  const replans: string[] = []
  page.on('request', (item) => { if (item.url().includes('/planner-api/v1/plans')) replans.push(item.url()) })
  await page.getByRole('button', { name: 'Один час' }).click()
  await expect(page.getByText(/час 1 из 4/)).toBeVisible()
  expect(replans).toHaveLength(0)

  await expect(page.getByRole('heading', { name: 'Сравнение стратегий' })).toBeVisible()
  await expect(page.getByRole('cell', { name: 'максимизация KPI' })).toBeVisible()
  await expect(page.getByRole('cell', { name: 'заморожен' })).toBeVisible()
  if (process.env.E2E_SCREENSHOT) await page.screenshot({ path: process.env.E2E_SCREENSHOT, fullPage: true })
})
