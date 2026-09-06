import type { LaunchDraft, WorldMetadata } from '../../domain/types'
import { MAX_INT64, parseMoney } from '../../domain/numeric'
import { normalizeAudience } from '../../domain/audience'

export type FieldErrors = Record<string, string>
const MIN_INT64 = -MAX_INT64 - 1n

function validInt64(value: string): boolean {
  if (!/^-?(0|[1-9][0-9]*)$/.test(value)) return false
  try {
    const parsed = BigInt(value)
    return parsed >= MIN_INT64 && parsed <= MAX_INT64
  } catch { return false }
}

export function validateDraft(draft: LaunchDraft, metadata: WorldMetadata): FieldErrors {
  const errors: FieldErrors = {}
  const { simulation, campaign } = draft
  if (campaign.audience !== undefined) {
    try { const audience = normalizeAudience(campaign.audience); if (Object.keys(audience).some(id => !metadata.channelIds.includes(id))) throw new Error('unknown_channel') }
    catch { errors['campaign.audience'] = 'Выберите непустую аудиторию для существующих каналов.' }
  }
  if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$/.test(simulation.simulationId)) errors['simulation.simulationId'] = '1–128 символов: латиница, цифры, точка, _ или -.'
  if (!validInt64(simulation.worldSeed)) errors['simulation.worldSeed'] = 'Введите целое число int64.'
  if (!validInt64(simulation.campaignSeed)) errors['simulation.campaignSeed'] = 'Введите целое число int64.'
  const start = new Date(simulation.startHour)
  if (!simulation.startHour || Number.isNaN(start.valueOf()) || start.getUTCMinutes() !== 0 || start.getUTCSeconds() !== 0 || start.getUTCMilliseconds() !== 0) {
    errors['simulation.startHour'] = 'Введите RFC 3339 время, выровненное на начало часа.'
  }
  const duration = Number(campaign.durationHours)
  if (!Number.isInteger(duration) || duration < 1 || duration > 2160) errors['campaign.durationHours'] = 'Введите целое число от 1 до 2160.'
  try { new Intl.DateTimeFormat('ru-RU', { timeZone: simulation.timeZone }).format(start) } catch { errors['simulation.timeZone'] = 'Введите существующий часовой пояс IANA.' }
  if (simulation.scenario.enabled) {
    const event = simulation.scenario
    const startIndex = Number(event.startIndex)
    const eventDuration = Number(event.durationHours)
    const multiplier = Number(event.multiplier)
    if (!metadata.channelIds.includes(event.channelId)) errors['simulation.scenario.channelId'] = 'Выберите существующий канал.'
    if (!Number.isInteger(startIndex) || startIndex < 0 || startIndex >= duration) errors['simulation.scenario.startIndex'] = 'Начальный индекс должен попадать в горизонт.'
    if (!Number.isInteger(eventDuration) || eventDuration < 1 || startIndex + eventDuration > duration) errors['simulation.scenario.durationHours'] = 'Длительность события должна попадать в горизонт.'
    if (!Number.isFinite(multiplier) || multiplier < 0) errors['simulation.scenario.multiplier'] = 'Введите неотрицательный множитель.'
  }
  if (!['uniform', 'optimized'].includes(campaign.strategy)) errors['campaign.strategy'] = 'Выберите доступную стратегию.'
  if (!['unique_reach', 'clicks', 'conversions'].includes(campaign.optimize)) errors['campaign.optimize'] = 'Выберите поддерживаемую KPI.'
  if (campaign.planType === 'fixed_budget') {
    try { parseMoney(campaign.totalBudget) } catch { errors['campaign.totalBudget'] = 'Введите неотрицательную сумму, максимум 6 знаков после точки.' }
  } else if (!/^[1-9][0-9]*$/.test(campaign.targetValue)) {
    errors['campaign.targetValue'] = 'Введите положительное целое значение цели.'
  }
  return errors
}

export function initialDraft(metadata: WorldMetadata): LaunchDraft {
  const now = new Date()
  now.setUTCMinutes(0, 0, 0)
  return {
    simulation: {
      simulationId: 'simulation-demo_1', worldSeed: '42001', campaignSeed: '77001',
      startHour: now.toISOString().replace('.000Z', 'Z'), timeZone: 'Europe/Moscow', disableRandomEvents: false,
      scenario: { enabled: false, channelId: metadata.channelIds[0] ?? '', metric: 'ctr', startIndex: '84', durationHours: '24', multiplier: '0.6' },
    },
    campaign: {
      durationHours: '168',
      planType: 'fixed_budget', totalBudget: '100000', optimize: 'unique_reach', strategy: 'uniform',
      targetMetric: 'unique_reach', targetValue: '10000',
    },
  }
}
