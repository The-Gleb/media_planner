import { describe, expect, it } from 'vitest'
import { aggregateECPMMicros, decodeSafeCount, formatMoney, normalizeMoney, parseMoney } from './numeric'

describe('exact numeric primitives', () => {
  it('round trips six-decimal money without floating point', () => {
    expect(parseMoney('0.000001')).toBe(1n)
    expect(normalizeMoney('12.3')).toBe('12.300000')
    expect(formatMoney(parseMoney('900719925.474099'))).toBe('900719925.474099')
  })
  it('rejects invalid or overflowing money', () => {
    expect(() => parseMoney('-1')).toThrow()
    expect(() => parseMoney('1.0000001')).toThrow()
    expect(() => parseMoney('9223372036854.775808')).toThrow()
  })
  it('uses upward micro-unit rounding for eCPM', () => {
    expect(aggregateECPMMicros(1n, 3n)).toBe(334n)
    expect(aggregateECPMMicros(0n, 0n)).toBeNull()
  })
  it('rejects unsafe transport counts', () => {
    expect(decodeSafeCount(42)).toBe(42n)
    expect(() => decodeSafeCount(Number.MAX_SAFE_INTEGER + 1)).toThrow()
  })
})
