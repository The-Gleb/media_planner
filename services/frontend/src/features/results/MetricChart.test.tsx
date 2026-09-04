import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { MetricChart } from './MetricChart'

describe('MetricChart', () => {
  it('provides an accessible description independent of color', () => {
    render(<MetricChart rows={[{ hour: '2026-09-03T06:00:00Z', a: 1, aggregate: 1 }]} series={[{ id: 'a', label: 'a', color: '#000', dash: '', aggregate: false }, { id: 'aggregate', label: 'Итого', color: '#111', dash: '10 4', aggregate: true }]} visible={new Set(['a', 'aggregate'])} title="Запросы" unit="за час" animate={false} />)
    expect(screen.getByRole('img', { name: /Запросы.*за час/ })).toBeVisible()
  })
})
