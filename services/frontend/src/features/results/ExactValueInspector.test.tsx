import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import { aggregateObservations } from '../../domain/aggregates'
import { result } from '../../test/fixtures'
import { ExactValueInspector } from './ExactValueInspector'

describe('ExactValueInspector', () => {
  it('lets keyboard users select a channel and read the exact value', async () => {
    const item = result(); item.aggregate = aggregateObservations(item.observations)
    render(<ExactValueInspector history={[item]} channelIds={['search_1', 'social_1']} metric="spend" currency="RUB" />)
    await userEvent.selectOptions(screen.getByLabelText('Ряд'), 'search_1')
    expect(screen.getByText(/10.000000 RUB/)).toBeVisible()
  })
})
