import { useEffect, useState } from 'react'
import { simulatorClient, type AudienceSegments } from '../../api/simulatorClient'
import type { AudienceFilters, AudienceSelection, WorldMetadata } from '../../domain/types'

const geoLabels: Record<string, string> = { moscow: 'Москва', other: 'Другие регионы' }
const genderLabels: Record<string, string> = { female: 'Женщины', male: 'Мужчины' }
const allFilters: AudienceFilters = { age: '', gender: '', geo: '' }

/** Each channel gets its own catalogue IDs for the same demographic intersection. */
function selectAudience(catalog: AudienceSegments, filters: AudienceFilters): AudienceSelection | undefined | null {
  if (!filters.age && !filters.gender && !filters.geo) return undefined
  const audience: AudienceSelection = {}
  for (const channel of catalog.channels) {
    const selected = channel.segments.filter(segment =>
      (!filters.age || `${segment.ageFrom}:${segment.ageToExclusive}` === filters.age) &&
      (!filters.gender || segment.gender === filters.gender) &&
      (!filters.geo || segment.geo === filters.geo))
    // Omitting a channel would silently target its entire audience in the simulator.
    if (!selected.length) return null
    if (selected.length !== channel.segments.length) audience[channel.channelId] = { segment_ids: selected.map(segment => segment.segmentId) }
  }
  return Object.keys(audience).length ? audience : undefined
}

export function AudienceFields({ metadata, value, filters = allFilters, disabled, error, onChange }: {
  metadata: WorldMetadata; value?: AudienceSelection; filters?: AudienceFilters; disabled: boolean; error?: string
  onChange: (value: AudienceSelection | undefined, filters: AudienceFilters) => void
}) {
  const [catalog, setCatalog] = useState<AudienceSegments | null>(null)
  const [failed, setFailed] = useState(false)
  const [attempt, setAttempt] = useState(0)
  useEffect(() => {
    let cancelled = false
    simulatorClient.audienceSegments().then(data => {
      if (data.worldConfigDigest !== metadata.worldConfigDigest || data.engineVersion !== metadata.engineVersion || [...data.channels.map(c => c.channelId)].sort().join('\0') !== [...metadata.channelIds].sort().join('\0')) throw new Error('audience_catalog_mismatch')
      if (!cancelled) { setCatalog(data); setFailed(false) }
    }).catch(() => { if (!cancelled) setFailed(true) })
    return () => { cancelled = true }
  }, [metadata, attempt])

  const segments = catalog?.channels.flatMap(channel => channel.segments) ?? []
  const ages = [...new Map(segments.map(segment => [`${segment.ageFrom}:${segment.ageToExclusive}`, segment])).values()].sort((a, b) => a.ageFrom - b.ageFrom || a.ageToExclusive - b.ageToExclusive)
  const fields: { key: keyof AudienceFilters; label: string; all: string; options: { value: string; label: string }[] }[] = [
    { key: 'age', label: 'Возраст', all: 'Все возрасты', options: ages.map(segment => ({ value: `${segment.ageFrom}:${segment.ageToExclusive}`, label: `${segment.ageFrom}–${segment.ageToExclusive - 1} лет` })) },
    { key: 'gender', label: 'Пол', all: 'Любой', options: [...new Set(segments.map(segment => segment.gender))].sort().map(gender => ({ value: gender, label: genderLabels[gender] ?? gender })) },
    { key: 'geo', label: 'Регион', all: 'Все регионы', options: [...new Set(segments.map(segment => segment.geo))].sort().map(geo => ({ value: geo, label: geoLabels[geo] ?? geo })) },
  ]

  function change(key: keyof AudienceFilters, next: string) {
    if (!catalog) return
    const nextFilters = { ...filters, [key]: next }
    const audience = selectAudience(catalog, nextFilters)
    if (audience !== null) onChange(audience, nextFilters)
  }

  return <section className="card stack" aria-labelledby="audience-title">
    <div><h2 id="audience-title">Целевая аудитория</h2><p className="muted">Возраст, пол и регион вместе задают единый фильтр для всех каналов.</p></div>
    {error && <p role="alert">{error}</p>}
    {failed ? <p role="alert">Не удалось загрузить каталог аудитории. <button type="button" disabled={disabled} onClick={() => setAttempt(n => n + 1)}>Повторить загрузку</button></p>
      : !catalog ? <p role="status">Загружаем сегменты аудитории…</p>
      : !segments.length ? <p>Текущий рынок не поддерживает выбор сегментов.</p>
      : <div className="form-grid">{fields.map(field => <div key={field.key} className="field">
        <label htmlFor={`audience-${field.key}`}>{field.label}</label>
        <select id={`audience-${field.key}`} value={filters[field.key]} disabled={disabled} onChange={event => change(field.key, event.target.value)}>
          <option value="">{field.all}</option>
          {field.options.map(option => <option key={option.value} value={option.value} disabled={selectAudience(catalog, { ...filters, [field.key]: option.value }) === null}>{option.label}</option>)}
        </select>
      </div>)}</div>}
    {(value || filters.age || filters.gender || filters.geo) && <>
      <button type="button" className="secondary" disabled={disabled} onClick={() => onChange(undefined, allFilters)}>Выбрать всю аудиторию</button>
      <p className="note">Выбор применяется к показам после запуска и сохраняется на весь срок кампании. Первоначальный прогноз бюджета и KPI пока рассчитан по каналам в целом; для узкой аудитории он может быть завышен. Адаптивное исполнение уточняет распределение по факту. История учитывается только для такого же выбора аудитории.</p>
    </>}
  </section>
}
