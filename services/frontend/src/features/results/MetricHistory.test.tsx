import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { aggregateObservations } from '../../domain/aggregates'
import { result } from '../../test/fixtures'
import { MetricHistory } from './MetricHistory'

describe('MetricHistory', () => {
  it('exposes every metric and an exact inspector', async () => {
    const item = result(); item.aggregate = aggregateObservations(item.observations)
    render(<MetricHistory history={[item]} channelIds={['search_1', 'social_1']} currency="RUB" running={false} />)
    expect(screen.getAllByRole('tab')).toHaveLength(7)
    expect(screen.getByLabelText('Ряд')).toBeVisible()
    await userEvent.click(screen.getByRole('tab', { name: /Новый охват/ }))
    expect(screen.getByText('Итого (без дедупликации)', { exact: false })).toBeInTheDocument()
  })
})
