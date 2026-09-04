import { describe, expect, it, vi } from 'vitest'
import { SimulatorClient } from './simulatorClient'

describe('SimulatorClient', () => {
  it('uses proxy path and captures ETag on create', async () => {
    const fetcher = vi.fn(async () => new Response(JSON.stringify({ simulation_id: 'demo', status: 'active', current_hour: '2026-09-03T06:00:00Z', end_hour_exclusive: '2026-09-03T07:00:00Z', duration_hours: 1, remaining_hours: 1, time_zone: 'Europe/Moscow', currency: 'RUB', engine_version: 'sim-v0', world_config_digest: 'a'.repeat(64), channel_ids: ['a'] }), { status: 201, headers: { ETag: '"1-aaaaaaaaaaaaaaaa"', 'Content-Type': 'application/json' } }))
    const client = new SimulatorClient(fetcher as typeof fetch)
    const response = await client.putSimulation('demo', { world_seed: '1', campaign_seed: '2', start_hour: '2026-09-03T06:00:00Z', duration_hours: 1, time_zone: 'Europe/Moscow' }, null)
    expect(fetcher).toHaveBeenCalledWith('/api/v1/simulations/demo', expect.objectContaining({ method: 'PUT', headers: expect.objectContaining({ 'If-None-Match': '*' }) }))
    expect(response.etag).toBe('"1-aaaaaaaaaaaaaaaa"')
  })
})
