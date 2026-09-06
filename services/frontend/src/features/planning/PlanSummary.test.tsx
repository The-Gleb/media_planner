import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { activePlan } from '../../test/fixtures'
import { PlanSummary } from './PlanSummary'

describe('plan summary', () => {
  it('shows reserve when optimized inventory is saturated', () => {
    render(<PlanSummary plan={activePlan({ strategy: 'optimized', unallocatedBudget: '587556.800000' })} />)

    expect(screen.getByText('Резерв вне каналов')).toBeVisible()
    expect(screen.getByText('587556.800000 RUB')).toBeVisible()
    expect(screen.getByText(/benchmark не видит положительной предельной отдачи/)).toBeVisible()
  })
})
