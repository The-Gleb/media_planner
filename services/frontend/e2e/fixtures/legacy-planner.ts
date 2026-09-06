import type { Page } from '@playwright/test'

// Contract emulator: strict pre-segmentation inputs and a response without echo.
// Calculations are delegated unchanged to the existing Planner behind the proxy.
export async function legacyPlanner(page: Page) {
  const allowed = new Set(['request_id', 'type', 'strategy', 'horizon', 'channels', 'simulation', 'market', 'current', 'budget', 'optimize', 'target'])
  await page.route('**/v1/plans', async route => {
    const input = route.request().postDataJSON() as Record<string, unknown>
    if (Object.keys(input).some(key => !allowed.has(key))) {
      await route.fulfill({ status: 422, json: { detail: 'unknown legacy Planner field' } })
      return
    }
    const response = await route.fetch()
    const body = await response.json()
    delete body.audience
    await route.fulfill({ response, json: body })
  })
}
