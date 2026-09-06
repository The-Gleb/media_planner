import type { KPI, Strategy } from '../domain/planning'
import type { ExecutionMode, MetricKey } from '../domain/types'

const CURRENCY_SIGN: Record<string, string> = { RUB: '₽', USD: '$', EUR: '€' }

export function currencySign(currency: string): string { return CURRENCY_SIGN[currency] ?? currency }

/** Money text with six decimals ("1200000.000000") as a human amount: "1 200 000 ₽". */
export function money(text: string | number | null | undefined, currency: string, digits = 0): string {
  if (text === null || text === undefined || text === '') return '—'
  const value = Number(text)
  if (!Number.isFinite(value)) return '—'
  return `${value.toLocaleString('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits })} ${currencySign(currency)}`
}

/** Plain number or numeric text with thousands separators. */
export function count(value: number | string | bigint | null | undefined, digits = 0): string {
  if (value === null || value === undefined || value === '') return '—'
  const number = typeof value === 'bigint' ? Number(value) : Number(value)
  if (!Number.isFinite(number)) return '—'
  return number.toLocaleString('ru-RU', { maximumFractionDigits: digits })
}

/** Ratio (0.0123) as a percentage string "1,23 %". */
export function percent(ratio: number | null | undefined, digits = 2): string {
  if (ratio === null || ratio === undefined || !Number.isFinite(ratio)) return '—'
  return `${(ratio * 100).toLocaleString('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits })} %`
}

/** Signed deviation "+4,2 %" or "−1,8 %". */
export function signedPercent(ratio: number | null | undefined, digits = 1): string {
  if (ratio === null || ratio === undefined || !Number.isFinite(ratio)) return '—'
  const sign = ratio > 0 ? '+' : ratio < 0 ? '−' : ''
  return `${sign}${(Math.abs(ratio) * 100).toLocaleString('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits })} %`
}

export function hoursAsDays(hours: number): string {
  const days = hours / 24
  const whole = Number.isInteger(days) ? `${days}` : days.toLocaleString('ru-RU', { maximumFractionDigits: 1 })
  return `${whole} ${plural(Math.round(days), 'день', 'дня', 'дней')}`
}

export function plural(n: number, one: string, few: string, many: string): string {
  const mod10 = n % 10, mod100 = n % 100
  if (mod10 === 1 && mod100 !== 11) return one
  if (mod10 >= 2 && mod10 <= 4 && (mod100 < 12 || mod100 > 14)) return few
  return many
}

const CHANNEL_KIND: Record<string, string> = { social: 'Соцсеть', programmatic: 'Programmatic', marketplace: 'Маркетплейс', sms: 'SMS' }

/** Abstract inventory name for a channel id: social_1 → "Соцсеть 1". */
export function channelLabel(channelId: string): string {
  const match = /^([a-z]+)(?:_([a-z0-9]+))?$/i.exec(channelId)
  if (!match) return channelId
  const kind = CHANNEL_KIND[match[1].toLowerCase()]
  if (!kind) return channelId
  return match[2] ? `${kind} ${match[2].toUpperCase()}` : kind
}

export function channelKind(channelId: string): string {
  const prefix = channelId.split('_')[0]?.toLowerCase() ?? ''
  return CHANNEL_KIND[prefix] ?? 'Канал'
}

export const KPI_LABEL: Record<KPI, string> = { unique_reach: 'Охват', clicks: 'Клики', conversions: 'Конверсии' }
export const KPI_LABEL_GENITIVE: Record<KPI, string> = { unique_reach: 'охвата', clicks: 'кликов', conversions: 'конверсий' }
export const KPI_UNIT_COST: Record<KPI, string> = { unique_reach: 'CPM охвата', clicks: 'CPC', conversions: 'CPA' }
export const STRATEGY_LABEL: Record<Strategy, string> = { uniform: 'Равномерное распределение', optimized: 'Оптимизация по каталогу' }
export const EXECUTION_LABEL: Record<ExecutionMode, string> = { adaptive_max: 'Максимизация KPI', adaptive: 'Удержание плана', frozen: 'Замороженный план' }
export const EXECUTION_HINT: Record<ExecutionMode, string> = {
  adaptive_max: 'Каждый час бюджет перекладывается в каналы с наибольшей отдачей по факту.',
  adaptive: 'Бюджет перекладывается только когда прогноз отклоняется от утверждённого плана.',
  frozen: 'Утверждённые лимиты исполняются без изменений. Базовая линия для сравнения.',
}
export const METRIC_SHORT: Record<MetricKey, string> = {
  requests: 'Запросы', impressions: 'Показы', unique_reach: 'Новый охват', clicks: 'Клики', conversions: 'Конверсии',
  spend: 'Расход', ecpm: 'eCPM', ctr: 'CTR', cr: 'CR', cpc: 'CPC', cpa: 'CPA',
}

export function kpiOfFacts(facts: { uniqueReach: string; clicks: string; conversions: string }, kpi: KPI): string {
  return kpi === 'unique_reach' ? facts.uniqueReach : facts[kpi]
}

export function shortHash(value: string, length = 10): string { return value.length > length ? `${value.slice(0, length)}…` : value }

export function formatHour(iso: string, timeZone: string): string {
  try {
    return new Intl.DateTimeFormat('ru-RU', { timeZone, day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(iso))
  } catch { return iso }
}
