import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { RunProgress } from './RunProgress'
import { session } from '../../test/fixtures'

describe('RunProgress', () => {
  it('reports server-derived completed and remaining hours', () => {
    render(<RunProgress session={{ ...session, durationHours: 10, remainingHours: 4 }} status="stopped" />)
    expect(screen.getByText(/6 выполнено, 4 осталось, 60.0%/)).toBeVisible()
    expect(screen.getByRole('progressbar')).toHaveAttribute('value', '6')
  })
})
