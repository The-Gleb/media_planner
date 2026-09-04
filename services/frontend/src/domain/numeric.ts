const MONEY = /^(0|[1-9][0-9]*)(?:\.([0-9]{1,6}))?$/
export const MONEY_SCALE = 1_000_000n
export const MAX_INT64 = 9_223_372_036_854_775_807n

export function parseMoney(value: string): bigint {
  const match = MONEY.exec(value)
  if (!match) throw new Error('invalid_money')
  const micros = BigInt(match[1]) * MONEY_SCALE + BigInt((match[2] ?? '').padEnd(6, '0') || '0')
  if (micros > MAX_INT64) throw new Error('money_overflow')
  return micros
}

export function formatMoney(micros: bigint): string {
  if (micros < 0n) throw new Error('negative_money')
  const whole = micros / MONEY_SCALE
  const fraction = (micros % MONEY_SCALE).toString().padStart(6, '0')
  return `${whole}.${fraction}`
}

export function normalizeMoney(value: string): string {
  return formatMoney(parseMoney(value))
}

export function addMoney(left: string, right: string): string {
  return formatMoney(parseMoney(left) + parseMoney(right))
}

export function ceilDiv(numerator: bigint, denominator: bigint): bigint {
  if (numerator < 0n || denominator <= 0n) throw new Error('invalid_division')
  const quotient = numerator / denominator
  return numerator % denominator === 0n ? quotient : quotient + 1n
}

export function aggregateECPMMicros(spendMicros: bigint, impressions: bigint): bigint | null {
  return impressions === 0n ? null : ceilDiv(spendMicros * 1000n, impressions)
}

export function decodeSafeCount(value: unknown, field = 'count'): bigint {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 0) {
    throw new Error(`invalid_${field}`)
  }
  return BigInt(value)
}

export function toChartNumber(value: bigint | string | null): number | null {
  if (value === null) return null
  const result = typeof value === 'bigint' ? Number(value) : Number(value)
  return Number.isFinite(result) ? result : null
}
