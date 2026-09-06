import { expect, test } from '@playwright/test'

test('target KPI mode estimates a budget and starts an executable campaign', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByText(/Simulator: Готов/)).toBeVisible()
  await page.getByRole('radio', { name: 'Целевой KPI' }).click()
  await page.getByLabel('Целевая метрика').selectOption('clicks')
  await page.getByLabel('Значение цели').fill('1000')
  await page.getByRole('button', { name: 'Построить план и запустить' }).click()
  await expect(page.getByText('Целевой KPI', { exact: true })).toBeVisible()
  await expect(page.getByText('Расчётный бюджет')).toBeVisible()
  await expect(page.getByText(/Прогноз плана/)).toBeVisible()
})
