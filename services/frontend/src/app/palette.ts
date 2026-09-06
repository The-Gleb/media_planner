/** Categorical palette, fixed slot order (validated for adjacent CVD separation on a light surface). */
export const SERIES = ['#2a78d6', '#eb6834', '#1baf7a', '#eda100', '#e87ba4', '#008300', '#4a3aa7', '#e34948'] as const
export const PLAN_STROKE = '#6b6b76'
export const FACT_STROKE = '#2a78d6'
export const TOTAL_STROKE = '#18181b'

/** Color follows the channel, never its rank: slot by position in the sorted channel list. */
export function channelColor(channelId: string, channelIds: readonly string[]): string {
  const sorted = [...channelIds].sort()
  const index = sorted.indexOf(channelId)
  return SERIES[(index < 0 ? 0 : index) % SERIES.length]
}
