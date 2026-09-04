import { describe, expect, it } from 'vitest'
import { observation, result } from '../../test/fixtures'
import { dailySpendRows, dailySpendTotal, formatSpendDay, spendDays } from './dailySpend'

describe('daily spend projection', () => {
  const history = [
    result({ observedHour: '2026-09-03T20:00:00Z', observations: [observation('social_1', { spend: '1.250000' })] }),
    result({ observedHour: '2026-09-03T21:00:00Z', observations: [observation('social_1', { spend: '2.500000' }), observation('search_1', { spend: '3.000000' })] }),
  ]

  it('groups hours by the campaign timezone and keeps channel segments', () => {
    expect(spendDays(history, 'Europe/Moscow')).toEqual(['2026-09-03', '2026-09-04'])
    const rows = dailySpendRows(history, ['search_1', 'social_1'], 'Europe/Moscow', '2026-09-04')
    expect(rows).toHaveLength(24)
    expect(rows[0]).toMatchObject({ hour: '00:00', search_1: 3, social_1: 2.5 })
    expect(dailySpendTotal(history, 'Europe/Moscow', '2026-09-04')).toBe('5.500000')
  })

  it('formats an already-local date without shifting it between timezones', () => {
    expect(formatSpendDay('2026-09-04')).toContain('4 сентября 2026')
  })
})
