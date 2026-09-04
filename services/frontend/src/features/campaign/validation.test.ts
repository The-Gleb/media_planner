import { describe, expect, it } from 'vitest'
import { metadata } from '../../test/fixtures'
import { initialDraft, validateDraft } from './validation'

describe('campaign validation', () => {
  it('accepts a valid fixed-budget draft', () => {
    const draft = initialDraft(metadata)
    draft.simulation.startHour = '2026-09-03T06:00:00Z'
    expect(validateDraft(draft, metadata)).toEqual({})
  })

  it('validates fixed budget and positive unavailable target', () => {
    const draft = initialDraft(metadata)
    draft.simulation.simulationId = '-bad'
    draft.simulation.startHour = '2026-09-03T06:30:00Z'
    draft.campaign.durationHours = '0'
    draft.campaign.totalBudget = '1e3'
    expect(validateDraft(draft, metadata)).toEqual(
      expect.objectContaining({
        'simulation.simulationId': expect.any(String),
        'simulation.startHour': expect.any(String),
        'campaign.durationHours': expect.any(String),
        'campaign.totalBudget': expect.any(String),
      }),
    )
    draft.campaign.planType = 'target_kpi'
    draft.campaign.targetValue = '0'
    expect(validateDraft(draft, metadata)).toHaveProperty('campaign.targetValue')
  })

  it('requires a controlled scenario to fit the campaign horizon', () => {
    const draft = initialDraft(metadata)
    draft.simulation.startHour = '2026-09-03T06:00:00Z'
    draft.campaign.durationHours = '8'
    draft.simulation.scenario = {
      enabled: true,
      channelId: metadata.channelIds[0],
      metric: 'cpm',
      startIndex: '7',
      durationHours: '2',
      multiplier: '-1',
    }

    expect(validateDraft(draft, metadata)).toEqual(
      expect.objectContaining({
        'simulation.scenario.durationHours': expect.any(String),
        'simulation.scenario.multiplier': expect.any(String),
      }),
    )
  })
})
