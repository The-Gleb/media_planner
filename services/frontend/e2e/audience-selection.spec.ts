import { expect, test } from '@playwright/test'
import { legacyPlanner } from './fixtures/legacy-planner'

test('catalogue failure blocks launch and can be retried', async ({ page }) => {
  test.skip(!process.env.AUDIENCE_E2E, 'Requires isolated segmented service')
  await page.route('**/v1/audience-segments', route => route.fulfill({ status: 503, json: {} }))
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Построить план и запустить', exact: true })).toBeDisabled()
  await expect(page.getByText('Не удалось загрузить аудитории.', { exact: false })).toBeVisible()
  await page.unroute('**/v1/audience-segments')
  await page.getByRole('button', { name: 'Повторить загрузку аудиторий' }).click()
  await expect(page.getByLabel('Все аудитории', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Построить план и запустить', exact: true })).toBeEnabled()
})

test('step retry preserves audience and a mismatched replan blocks execution', async ({ page, request }) => {
  test.skip(!process.env.AUDIENCE_E2E, 'Requires isolated segmented service')
  const id = 'audience-e2e-retry'
  const sent: unknown[] = []
  await page.route('**/steps', async route => {
    sent.push(route.request().postDataJSON())
    if (sent.length === 1) { await route.fetch(); await route.abort('failed') }
    else await route.continue()
  })
  let poisoned = false
  await page.route('**/v1/plans', async route => {
    const response = await route.fetch()
    const body = await response.json()
    if (body.state_revision === 1 && !poisoned) { body.request_id = '00000000-0000-4000-8000-000000000999'; poisoned = true }
    await route.fulfill({ response, json: body })
  })
  await page.goto('/')
  await page.getByLabel('ID симуляции', { exact: true }).fill(id)
  await page.getByLabel('Длительность, часов').fill('3')
  await page.getByLabel('Все аудитории', { exact: true }).uncheck()
  await expect(page.getByLabel('Температура social_1')).toHaveCount(0)
  try {
    await page.getByRole('button', { name: 'Построить план и запустить', exact: true }).click()
    const step = page.getByRole('button', { name: 'Один час', exact: true })
    await expect(step).toBeEnabled(); await step.click()
    await expect(page.getByRole('alert').filter({ hasText: 'Симуляция одного часа' })).toBeVisible()
    await step.click()
    await expect.poll(() => sent.length).toBe(2)
    expect(sent[1]).toEqual(sent[0])
    await expect(page.getByText(/получен устаревший или несвязанный план/)).toBeVisible()
    await expect(step).toBeDisabled()
    await page.getByRole('button', { name: /Повторить.*план/ }).click()
    await expect(step).toBeEnabled()
    expect(sent.length).toBe(2)
  } finally {
    const current = await request.get(`/api/v1/simulations/${id}/current-hour`)
    if (current.ok()) await request.delete(`/api/v1/simulations/${id}`, { headers: { 'If-Match': current.headers().etag ?? '' } })
  }
})

for (const legacy of [false, true]) for (const strategy of ['uniform', 'optimized', 'target'] as const) {
  test(`fixed audience with ${legacy ? 'legacy' : 'current'} ${strategy} planner, hours and reset`, async ({ page, request }) => {
    test.skip(!process.env.AUDIENCE_E2E, 'Requires isolated segmented service')
    const id = `audience-e2e-${strategy}`
    if (legacy) await legacyPlanner(page)
    const plans: Record<string, unknown>[] = []
    page.on('request', req => {if(req.url().endsWith('/v1/plans') && req.method()==='POST') plans.push(req.postDataJSON())})
    const selected: Record<string, unknown>[] = []
    page.on('request', req => { if (req.method() === 'POST' && req.url().endsWith('/steps')) selected.push(req.postDataJSON()) })
    await page.goto('/')
    await expect(page.getByLabel('Все аудитории', { exact: true })).toBeVisible()
    await page.getByLabel('ID симуляции', { exact: true }).fill(id)
    await page.getByLabel('Длительность, часов').fill('2')
    await page.getByLabel('Все аудитории', { exact: true }).uncheck()
    await expect(page.getByLabel('Температура social_1')).toHaveCount(0)
    if (strategy === 'target') {
      await page.getByRole('radio', { name: 'Целевой KPI' }).check()
      await page.getByLabel('Целевая метрика').selectOption('clicks')
      await page.getByLabel('Значение цели').fill('100')
    } else await page.getByLabel('Стратегия').selectOption(strategy)
    try {
      await page.getByRole('button', { name: 'Построить план и запустить', exact: true }).click()
      await expect(page.getByLabel('Все аудитории', { exact: true })).toBeDisabled()
      const step = page.getByRole('button', { name: /Один час|Один шаг|Следующий час|Шаг.*час/ })
      await expect(step).toBeEnabled()
      await step.click(); await expect(step).toBeEnabled(); await step.click()
      await expect.poll(() => selected.length).toBe(2)
      expect(selected[0].audience).toBeDefined()
      expect(selected[1].audience).toEqual(selected[0].audience)
      expect(JSON.stringify(selected[0])).not.toContain('temperature')
      for (const plan of plans) expect(plan).not.toHaveProperty('audience')
      await page.getByRole('button', { name: 'Изменить аудиторию для нового запуска' }).click()
      await page.getByLabel('Москва · Женщины · 25–34', { exact: true }).uncheck()
      await page.getByRole('button', { name: 'Перепланировать, сбросить и запустить', exact: true }).click()
      await expect(step).toBeEnabled(); await step.click()
      await expect.poll(() => selected.length).toBe(3)
      await expect(step).toBeEnabled()
      expect(selected[2].audience).not.toEqual(selected[0].audience)
      for (const plan of plans) expect(plan).not.toHaveProperty('audience')
    } finally {
      await page.unrouteAll({ behavior: 'wait' })
      const current = await request.get(`/api/v1/simulations/${id}/current-hour`)
      if (current.ok()) await request.delete(`/api/v1/simulations/${id}`, { headers: { 'If-Match': current.headers().etag ?? '' } })
    }
  })
}
