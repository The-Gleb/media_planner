import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { zeroCampaignFacts } from '../../domain/campaignFacts'
import { StrategyComparison } from './StrategyComparison'

describe('StrategyComparison', () => {
  it('shows sequential runs and all comparison KPIs', () => {
    const previousFacts = { ...zeroCampaignFacts(['social_1']), spent: '10.000000', uniqueReach: '90', clicks: '8', conversions: '2' }
    const currentFacts = { ...zeroCampaignFacts(['social_1']), spent: '9.000000', uniqueReach: '100', clicks: '10', conversions: '3' }
    render(<StrategyComparison
      previous={{ strategy: 'uniform', optimize: 'conversions', planId: 'a'.repeat(64), facts: previousFacts }}
      current={{ strategy: 'optimized', optimize: 'conversions', facts: currentFacts, finished: true }}
    />)
    expect(screen.getByRole('heading', { name: 'Сравнение стратегий' })).toBeVisible()
    expect(screen.getByText('Равномерная')).toBeVisible()
    expect(screen.getByText('Оптимизированная')).toBeVisible()
    expect(screen.getByText('Два прогона завершены')).toBeVisible()
  })
})
