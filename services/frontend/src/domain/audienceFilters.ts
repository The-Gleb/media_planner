import type { Audience, AudienceCatalog, AudienceSegment } from './audience'

export type Dimension = 'geo' | 'gender' | 'age'
export type AudienceFilters = Record<Dimension, string[]>
const ageKey = (segment: AudienceSegment) => `${segment.age_from}:${segment.age_to_exclusive}`

export function filterOptions(catalog: AudienceCatalog): AudienceFilters {
  const segments = catalog.channels.flatMap(channel => channel.segments)
  return {
    geo: [...new Set(segments.map(s => s.geo))].sort(),
    gender: [...new Set(segments.map(s => s.gender))].sort(),
    age: [...new Set(segments.map(ageKey))].sort((a, b) => Number(a.split(':')[0]) - Number(b.split(':')[0])),
  }
}

export function filtersFromAudience(catalog: AudienceCatalog, audience?: Audience): AudienceFilters {
  if (audience === undefined) return filterOptions(catalog)
  const selected = catalog.channels.flatMap(channel => channel.segments.filter(segment =>
    audience[channel.channel_id] === undefined || audience[channel.channel_id].segment_ids.includes(segment.segment_id)))
  return { geo: [...new Set(selected.map(s => s.geo))], gender: [...new Set(selected.map(s => s.gender))], age: [...new Set(selected.map(ageKey))] }
}

export function audienceFromFilters(catalog: AudienceCatalog, filters: AudienceFilters): Audience {
  return Object.fromEntries(catalog.channels.filter(channel => channel.segments.length > 0).map(channel => [channel.channel_id, {
    segment_ids: channel.segments.filter(s => filters.geo.includes(s.geo) && filters.gender.includes(s.gender) && filters.age.includes(ageKey(s))).map(s => s.segment_id),
  }]))
}

const ageLabels: Record<string, [string, string]> = {
  '13:19': ['Подростки', 'Соцсети, тренды и мнение сверстников'],
  '19:31': ['Молодёжь', 'Онлайн-покупки, эксперименты и новые бренды'],
  '31:46': ['Зрелая аудитория', 'Качество, удобство и потребности семьи'],
  '46:60': ['Опытные потребители', 'Проверенные каналы и рекомендации'],
  '60:131': ['Пожилые', 'Аудитория от 60 лет'],
}
export function optionLabel(dimension: Dimension, key: string): { label: string; hint?: string } {
  if (dimension === 'geo') return { label: ({ moscow: 'Москва', other: 'Другие регионы' } as Record<string, string>)[key] ?? key }
  if (dimension === 'gender') return { label: ({ female: 'Женщины', male: 'Мужчины' } as Record<string, string>)[key] ?? key }
  const [from, to] = key.split(':').map(Number)
  const range = to === 131 ? `${from}+` : `${from}–${to - 1}`
  const named = ageLabels[key]
  return { label: named ? `${named[0]} · ${range}` : range, hint: named?.[1] }
}
