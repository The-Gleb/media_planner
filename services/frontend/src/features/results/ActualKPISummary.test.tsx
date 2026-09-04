import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { facts } from '../../test/fixtures'
import { ActualKPISummary } from './ActualKPISummary'

describe('actual KPI summary', () => {
  it('shows all campaign aggregates and non-deduplicated reach', () => {
    const actual = {
      ...facts,
      spent: '25.500000' as const,
      uniqueReach: '100',
      clicks: '10',
      conversions: '2',
      channels: {
        ...facts.channels,
        search_1: { ...facts.channels.search_1, impressions: '40' },
        social_1: { ...facts.channels.social_1, impressions: '60' },
      },
    }
    render(<ActualKPISummary facts={actual} currency="RUB" finished={false} />)
    expect(screen.getByRole('heading', { name: 'Фактические результаты' })).toBeVisible()
    expect(screen.getByText(/сумма по каналам, без дедупликации/)).toBeVisible()
    expect(screen.getByText('25.500000')).toBeVisible()
    expect(screen.getAllByText('100')).toHaveLength(2)
    expect(screen.getByText('10')).toBeVisible()
    expect(screen.getByText('2')).toBeVisible()
  })

  it('labels every final aggregate', () => {
    render(<ActualKPISummary facts={facts} currency="RUB" finished />)
    expect(screen.getByRole('heading', { name: 'Итоговые результаты' })).toBeVisible()
    expect(screen.getAllByText(/^Итогов/, { selector: 'small' })).toHaveLength(5)
  })
})
