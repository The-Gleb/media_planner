import { expect, test } from '@playwright/test'
import { clearSimulation, createCampaign } from './helpers'

test.afterEach(async ({ request }) => clearSimulation(request))

test('runs two strategies sequentially on the same seeded simulation and compares totals', async ({ page, request }) => {
  await clearSimulation(request)
  await createCampaign(page, 1)
  await page.getByRole('button', { name: 'Один час' }).click()
  await expect(page.getByText('Финал')).toBeVisible()

  await page.getByLabel('Стратегия').selectOption('optimized')
  await page.getByRole('button', { name: 'Перепланировать, сбросить и запустить' }).click()
  await expect(page.getByRole('heading', { name: 'Сравнение стратегий' })).toBeVisible()
  await expect(page.getByText('Второй прогон выполняется')).toBeVisible()
  await page.getByRole('button', { name: 'Один час' }).click()
  await expect(page.getByText('Два прогона завершены')).toBeVisible()
  await expect(page.getByText('Равномерная')).toBeVisible()
  await expect(page.getByRole('rowheader', { name: 'Оптимизированная' })).toBeVisible()
})
