import { describe, expect, it } from 'vitest'
import { buildApprovedPayload, buildPastCampaignPayload, buildRecentHours } from './history'
import { activePlan, metadata, observation, result } from '../test/fixtures'

const hours = Array.from({ length: 30 }, (_, index) => {
  const observedHour = new Date(Date.UTC(2026, 8, 3, 6 + index)).toISOString().replace('.000Z', 'Z')
  return result({
    observedHour, stepId: `00000000-0000-4000-8000-${String(index).padStart(12, '0')}`,
    observations: [observation('search_1', { hour: observedHour, impressions: 100n, uniqueReach: 10n, clicks: 4n, spend: '2.000000' }), observation('social_1', { hour: observedHour })],
  })
})

describe('campaign history payloads', () => {
  it('bins committed hours by local hour of day and keeps daily saturation state', () => {
    const payload = buildPastCampaignPayload(hours, metadata.channelIds, 'Europe/Moscow', 30)
    const search = payload.channels.search_1
    expect(payload.horizon_hours).toBe(30)
    expect(search.bins).toHaveLength(24)
    expect(search.bins.reduce((sum, bin) => sum + bin.hours, 0)).toBe(30)
    expect(search.bins.map((bin) => bin.hour)).toEqual(Array.from({ length: 24 }, (_, hour) => hour))
    // 06:00 UTC is 09:00 in Moscow; hours 9..14 of the day appear twice within 30 campaign hours.
    expect(search.bins[9].hours).toBe(2)
    expect(search.bins[9].impressions).toBe('200')
    expect(search.bins[9].spent).toBe('4.000000')
    expect(search.daily).toHaveLength(2)
    expect(search.daily[0]).toMatchObject({ day: 0, hours: 24, impressions: '2400', clicks: '96', reach_before: '0', impressions_before: '0' })
    expect(search.daily[1]).toMatchObject({ day: 1, hours: 6, reach_before: '240', impressions_before: '2400' })
  })
  it('sends only the latest 72 hours with campaign hour indexes', () => {
    const recent = buildRecentHours(hours, metadata.channelIds)
    expect(recent).toHaveLength(30)
    expect(recent[0].hour).toBe(0)
    expect(recent.at(-1)?.hour).toBe(29)
    expect(recent[3].channels.search_1).toEqual({ spent: '2.000000', requests: '100', impressions: '100', unique_reach: '10', clicks: '4', conversions: '1' })
    const long = Array.from({ length: 100 }, (_, index) => hours[index % hours.length])
    expect(buildRecentHours(long, metadata.channelIds).map((row) => row.hour)).toEqual(Array.from({ length: 72 }, (_, index) => 28 + index))
  })
  it('turns the approved plan into a tracking target with channel budgets', () => {
    expect(buildApprovedPayload(activePlan())).toBeNull()
    const plan = activePlan({ optimize: 'clicks', expected: { spend: '12.000000', impressions: '1000', uniqueReach: '100', clicks: '10', conversions: '1' } })
    expect(buildApprovedPayload(plan)).toEqual({ kpi_target: '10', channel_budgets: { search_1: '6.000000', social_1: '6.000000' } })
  })
})
