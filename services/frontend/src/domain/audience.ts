import type { AudienceSelection } from './types'

/** Omitted channels use all their segments, as defined by the simulator API. */
export function audienceKey(audience?: AudienceSelection): string {
  return JSON.stringify(Object.entries(audience ?? {}).sort(([a], [b]) => a.localeCompare(b)).map(([channel, selection]) => [channel, [...selection.segment_ids].sort()]))
}
