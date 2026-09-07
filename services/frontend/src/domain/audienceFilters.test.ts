import { describe, expect, it } from 'vitest'
import { audienceFromFilters, filterOptions, filtersFromAudience, optionLabel } from './audienceFilters'
import type { AudienceCatalog } from './audience'

const segments = ['moscow', 'other'].flatMap(geo => ['female', 'male'].flatMap(gender => [[13, 19], [19, 31], [31, 46], [46, 60], [60, 131]].map(([age_from, age_to_exclusive]) => ({ segment_id: `${geo}_${gender}_${age_from}`, geo, gender, age_from, age_to_exclusive }))))
const catalog: AudienceCatalog = { engine_version: 'sim-v2-delivery', world_config_digest: 'a'.repeat(64), channels: [{ channel_id: 'social_1', segments }, { channel_id: 'social_2', segments: segments.map(s => ({ ...s, segment_id: `second_${s.segment_id}` })) }] }

describe('independent audience dimensions', () => {
  it('combines OR within dimensions and AND between them, mapping each channel ID', () => {
    const filters = { geo: ['moscow'], gender: ['female'], age: ['13:19', '60:131'] }
    const selected = audienceFromFilters(catalog, filters)
    expect(selected).toEqual({ social_1: { segment_ids: ['moscow_female_13', 'moscow_female_60'] }, social_2: { segment_ids: ['second_moscow_female_13', 'second_moscow_female_60'] } })
    expect(filtersFromAudience(catalog, selected)).toEqual(filters)
  })
  it('includes every age with no targeting and exposes all five disjoint age ranges', () => {
    const options = filterOptions(catalog)
    expect(options.age).toEqual(['13:19', '19:31', '31:46', '46:60', '60:131'])
    expect(filtersFromAudience(catalog)).toEqual(options)
    expect(audienceFromFilters(catalog, options).social_1.segment_ids).toHaveLength(20)
    expect(optionLabel('age', '60:131').label).toBe('Пожилые · 60+')
  })
  it('keeps an empty group invalid for all channels instead of silently selecting everyone', () => {
    const result = audienceFromFilters(catalog, { ...filterOptions(catalog), gender: [] })
    expect(Object.values(result).every(channel => channel.segment_ids.length === 0)).toBe(true)
  })
  it('does not broaden targeting for channels with no matching intersection', () => {
    const sparse = { ...catalog, channels: [catalog.channels[0], { channel_id: 'social_2', segments: segments.filter(s => s.geo === 'other') }] }
    expect(audienceFromFilters(sparse, { geo: ['moscow'], gender: ['male'], age: ['19:31'] }).social_2.segment_ids).toEqual([])
  })
})
