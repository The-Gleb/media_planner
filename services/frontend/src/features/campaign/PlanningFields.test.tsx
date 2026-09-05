import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { metadata } from '../../test/fixtures'
import { PlanningFields } from './PlanningFields'
import { initialDraft } from './validation'

describe('PlanningFields', () => {
  it('exposes accessible total budget, KPI and both strategies', () => {
    render(<PlanningFields value={initialDraft(metadata).campaign} currency="RUB" errors={{}} disabled={false} onChange={() => {}} />)
    expect(screen.getByLabelText('Общий бюджет, RUB')).toBeVisible()
    expect(screen.getByLabelText('Оптимизируемая метрика')).toBeVisible()
    expect(screen.getByLabelText('Стратегия')).toBeEnabled()
  })

  it('enables target mode, validates the target and fixes optimized strategy', async () => {
    const change = vi.fn()
    const campaign = { ...initialDraft(metadata).campaign, planType: 'target_kpi' as const, targetValue: '0', strategy: 'optimized' as const }
    render(<PlanningFields value={campaign} currency="RUB" errors={{ 'campaign.targetValue': 'Введите положительное значение' }} disabled={false} onChange={change} />)
    const mode = screen.getByRole('radio', { name: 'Целевой KPI' })
    mode.focus()
    expect(mode).toHaveFocus()
    expect(screen.getByRole('textbox', { name: /Значение цели/ })).toHaveAccessibleDescription('Введите положительное значение')
    expect(screen.getByRole('status')).toHaveTextContent(/бюджет фиксируется/)
    expect(screen.getByLabelText('Стратегия')).toBeDisabled()
    await userEvent.click(screen.getByRole('radio', { name: 'Фиксированный бюджет' }))
    expect(change).toHaveBeenCalled()
  })
})
