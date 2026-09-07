import { expect, test } from '@playwright/test'
import { legacyPlanner } from './fixtures/legacy-planner'

test('independent demographic cards map to every channel and fit mobile', async ({ page }, testInfo) => {
  test.skip(!process.env.AUDIENCE_E2E, 'Requires isolated segmented service')
  await page.goto('/')
  const picker = page.getByRole('group', { name: 'Аудитория кампании', exact: true })
  await expect(picker.getByRole('group', { name: 'География', exact: true })).toBeVisible()
  await expect(picker.getByRole('group', { name: 'Пол', exact: true })).toBeVisible()
  for (const label of ['Подростки · 13–18', 'Молодёжь · 19–30', 'Зрелая аудитория · 31–45', 'Опытные потребители · 46–59', 'Пожилые · 60+']) await expect(picker.getByRole('checkbox', { name: label, exact: true })).toBeChecked()
  await picker.getByRole('checkbox', { name: 'Другие регионы', exact: true }).uncheck()
  await picker.getByRole('checkbox', { name: 'Мужчины', exact: true }).uncheck()
  await picker.getByRole('button', { name: 'Снять выбор: Возраст' }).click()
  await expect(page.getByRole('button', { name: 'Рассчитать медиаплан', exact: true })).toBeDisabled()
  await picker.getByRole('checkbox', { name: 'Подростки · 13–18', exact: true }).check()
  await picker.getByRole('checkbox', { name: 'Пожилые · 60+', exact: true }).check()
  await expect(page.getByRole('button', { name: 'Рассчитать медиаплан', exact: true })).toBeEnabled()
  await picker.screenshot({ path: testInfo.outputPath('audience-desktop.png') })
  await page.setViewportSize({ width: 390, height: 844 })
  await expect(picker.getByRole('checkbox', { name: 'Пожилые · 60+', exact: true })).toBeVisible()
  expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true)
  await picker.screenshot({ path: testInfo.outputPath('audience-mobile.png') })
  let resetBody: Record<string, unknown> | undefined
  await page.route('**/v1/simulations/*', async route => {
    if (route.request().method() !== 'PUT') return route.continue()
    resetBody = route.request().postDataJSON()
    await route.abort('failed') // Inspect mapping without creating a campaign.
  })
  await page.getByRole('button', { name: 'Рассчитать медиаплан', exact: true }).click()
  await expect.poll(() => resetBody).toBeDefined()
  const audience = resetBody!.audience as Record<string, { segment_ids: string[] }>
  expect(Object.keys(audience)).toHaveLength(8)
  for (const selection of Object.values(audience)) expect(selection.segment_ids.sort()).toEqual(['moscow_female_13_18', 'moscow_female_60_plus'])
})

for (const mode of ['frozen', 'adaptive', 'adaptive_max']) test(`new dashboard timelapse: ${mode}, default all audiences`, async ({ page, request }) => {
  test.skip(!process.env.AUDIENCE_E2E, 'Requires isolated segmented service')
  const id = `audience-e2e-mode-${mode}`
  const steps: Record<string, unknown>[] = []
  page.on('request', req => { if (req.method() === 'POST' && req.url().endsWith('/steps')) steps.push(req.postDataJSON()) })
  await page.goto('/')
  await expect(page.getByLabel('Все аудитории', { exact: true })).toBeChecked()
  await page.getByRole('radio', { name: 'Эксперт', exact: true }).click()
  await page.getByLabel('ID симуляции', { exact: true }).fill(id)
  await page.getByLabel('Срок кампании, часов').fill('3')
  await page.locator(`input[name="execution"][value="${mode}"]`).check()
  try {
    await page.getByRole('button', { name: 'Рассчитать медиаплан', exact: true }).click()
    await page.getByRole('button', { name: 'Утвердить план и перейти к запуску' }).click()
    await page.getByLabel('Скорость таймлапса').selectOption('0')
    await page.getByRole('button', { name: 'Запустить таймлапс' }).click()
    await expect(page.getByText('Кампания завершена', { exact: true })).toBeVisible()
    expect(steps).toHaveLength(3)
    for (const step of steps) expect(step).not.toHaveProperty('audience')
    const current = await request.get(`/api/v1/simulations/${id}/current-hour`)
    expect((await current.json()).remaining_hours).toBe(0)
  } finally {
    const current = await request.get(`/api/v1/simulations/${id}/current-hour`)
    if (current.ok()) await request.delete(`/api/v1/simulations/${id}`, { headers: { 'If-Match': current.headers().etag ?? '' } })
  }
})

test('catalogue failure blocks launch and can be retried', async ({ page }) => {
  test.skip(!process.env.AUDIENCE_E2E, 'Requires isolated segmented service')
  await page.route('**/v1/audience-segments', route => route.fulfill({ status: 503, json: {} }))
  await page.goto('/')
  await expect(page.getByRole('button', { name: 'Рассчитать медиаплан', exact: true })).toBeDisabled()
  await expect(page.getByText('Не удалось загрузить аудитории.', { exact: false })).toBeVisible()
  await page.unroute('**/v1/audience-segments')
  await page.getByRole('button', { name: 'Повторить загрузку аудиторий' }).click()
  await expect(page.getByLabel('Все аудитории', { exact: true })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Рассчитать медиаплан', exact: true })).toBeEnabled()
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
  await page.getByRole('radio', { name: 'Эксперт', exact: true }).click()
    await page.getByLabel('ID симуляции', { exact: true }).fill(id)
    await page.getByLabel('Учитывать опыт прошлых кампаний на этом рынке', { exact: false }).uncheck()
  await page.getByLabel('Срок кампании, часов').fill('3')
  await page.getByLabel('Все аудитории', { exact: true }).uncheck()
  await expect(page.getByLabel('Температура social_1')).toHaveCount(0)
  try {
    await page.getByRole('button', { name: 'Рассчитать медиаплан', exact: true }).click()
    await page.getByRole('button', { name: 'Утвердить план и перейти к запуску' }).click()
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
    await page.getByRole('radio', { name: 'Эксперт', exact: true }).click()
    await page.getByLabel('ID симуляции', { exact: true }).fill(id)
    await page.getByLabel('Учитывать опыт прошлых кампаний на этом рынке', { exact: false }).uncheck()
    await page.getByLabel('Срок кампании, часов').fill('2')
    await page.getByLabel('Все аудитории', { exact: true }).uncheck()
    await expect(page.getByLabel('Температура social_1')).toHaveCount(0)
    if (strategy === 'target') {
      await page.getByRole('radio', { name: /Задача B/ }).check()
      await page.getByLabel('Целевая метрика').selectOption('clicks')
      await page.getByLabel('Целевой объём').fill('100')
      await page.getByLabel('Что делать при досрочном достижении KPI?').selectOption('spend_budget')
    } else await page.getByLabel('Алгоритм распределения').selectOption(strategy)
    try {
      await page.getByRole('button', { name: 'Рассчитать медиаплан', exact: true }).click()
    await page.getByRole('button', { name: 'Утвердить план и перейти к запуску' }).click()
      const step = page.getByRole('button', { name: /Один час|Один шаг|Следующий час|Шаг.*час/ })
      await expect(step).toBeEnabled()
      await step.click(); await expect(step).toBeEnabled(); await step.click()
      await expect.poll(() => selected.length).toBe(2)
      expect(selected[0].audience).toBeDefined()
      expect(selected[1].audience).toEqual(selected[0].audience)
      expect(JSON.stringify(selected[0])).not.toContain('temperature')
      for (const plan of plans) expect(plan).not.toHaveProperty('audience')
      await page.getByRole('button', { name: 'Новая кампания или сравнение стратегий' }).click()
      await expect(page.getByLabel('Все аудитории', { exact: true })).toBeDisabled()
      await page.getByRole('button', { name: 'Изменить аудиторию для нового запуска' }).click()
      await page.getByRole('checkbox', { name: 'Молодёжь · 19–30', exact: true }).uncheck()
      await page.getByRole('button', { name: 'Пересчитать медиаплан', exact: true }).click()
      await page.getByRole('button', { name: 'Утвердить план и перейти к запуску' }).click()
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
