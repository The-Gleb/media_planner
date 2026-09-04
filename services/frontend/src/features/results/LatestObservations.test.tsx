import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { LatestObservations } from './LatestObservations'
import { observation, result } from '../../test/fixtures'

describe('LatestObservations', () => {
  it('shows exact values, currency and a missing eCPM', () => {
    render(<LatestObservations currency="RUB" result={result({ observations: [observation('search_1', { impressions: 0n, uniqueReach: 0n, clicks: 0n, conversions: 0n, spend: '0.000000', ecpm: null })] })} />)
    expect(screen.getByRole('region', { name: 'Точные наблюдения последнего часа' })).toBeVisible()
    expect(screen.getByText('—')).toBeVisible()
    expect(screen.getByText('Расход, RUB')).toBeVisible()
  })
})
