import type { MetricKey } from '../domain/types'
import { SimulatorProblemError } from '../api/simulatorClient'
import { PlannerProblemError } from '../api/problem'

export const metricLabels: Record<MetricKey, string> = {
  requests: 'Запросы (requests)', impressions: 'Показы (impressions)',
  unique_reach: 'Новый охват (unique_reach)', clicks: 'Клики (clicks)',
  conversions: 'Конверсии (conversions)', spend: 'Расход (spend)', ecpm: 'eCPM',
  ctr: 'CTR', cr: 'CR', cpc: 'CPC', cpa: 'CPA',
}

const problemMessages: Record<string, string> = {
  active_limit: 'В Simulator уже есть другая кампания. Удалите её через API или используйте её идентификатор.',
  precondition_failed: 'Состояние кампании изменилось. Обновите данные и повторите операцию.',
  validation_error: 'Simulator отклонил значения. Проверьте отмеченные поля.',
  simulation_finished: 'Кампания уже завершена.',
  not_found: 'Кампания не найдена. Возможно, Simulator был перезапущен.',
  gone: 'Кампания была удалена.',
}

export function userError(error: unknown, operation: string): string {
  if (error instanceof PlannerProblemError) {
    const message = error.problem.code === 'unsupported_plan_type'
      ? 'планирование по целевой метрике пока недоступно.'
      : error.problem.detail ?? error.problem.title
    return `${operation}: ${message}${error.problem.trace_id ? ` Trace ID: ${error.problem.trace_id}` : ''}`
  }
  if (error instanceof SimulatorProblemError) {
    const message = problemMessages[error.problem.code] ?? error.problem.detail ?? error.problem.title
    return `${operation}: ${message}${error.problem.trace_id ? ` Trace ID: ${error.problem.trace_id}` : ''}`
  }
  if (error instanceof Error && error.message === 'stale_plan') return `${operation}: получен устаревший или несвязанный план. Повторите текущий раунд.`
  if (error instanceof Error && (error.message === 'missing_plan_hour' || error.message === 'missing_plan_allocation')) return `${operation}: в активном плане отсутствует лимит для текущего часа.`
  if (error instanceof Error && error.message.startsWith('invalid_')) return `${operation}: ответ сервиса не прошёл проверку (${error.message}).`
  if (error instanceof Error && error.message.startsWith('planner_')) return `${operation}: Planner недоступен или вернул некорректные данные.`
  return `${operation}: сервис недоступен или вернул некорректные данные.`
}
