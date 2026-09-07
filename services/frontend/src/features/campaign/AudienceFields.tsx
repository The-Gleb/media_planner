import { useEffect, useState } from 'react'
import { simulatorClient } from '../../api/simulatorClient'
import type { Audience, AudienceCatalog } from '../../domain/audience'
import { audienceFromFilters, filterOptions, filtersFromAudience, optionLabel, type AudienceFilters, type Dimension } from '../../domain/audienceFilters'

const dimensions: { key: Dimension; label: string }[] = [{ key: 'geo', label: 'География' }, { key: 'gender', label: 'Пол' }, { key: 'age', label: 'Возраст' }]

export function AudienceFields({ value, onChange, disabled, digest, onReady }: { value?: Audience; onChange: (value: Audience | undefined) => void; disabled: boolean; digest: string; onReady: (ready: boolean) => void }) {
  const [catalog, setCatalog] = useState<AudienceCatalog | null>(null)
  const [error, setError] = useState(false)
  const [legacy, setLegacy] = useState(false)
  const [retry, setRetry] = useState(0)
  // Preserve other dimension choices while an empty intersection is being edited.
  const [editing, setEditing] = useState<{ audience: Audience | undefined; filters: AudienceFilters; digest: string } | null>(null)
  useEffect(() => {
    let active = true
    onReady(false)
    simulatorClient.audienceCatalog().then(result => {
      if (!active) return
      if (result && result.world_config_digest !== digest) throw new Error('stale_catalog')
      setCatalog(result); setLegacy(result === null); setError(false); onReady(true)
    }).catch(() => { if (active) { setError(true); onReady(false) } })
    return () => { active = false }
  }, [digest, retry, onReady])

  const currentCatalog = catalog?.world_config_digest === digest ? catalog : null
  const options = currentCatalog ? filterOptions(currentCatalog) : null
  const filters = currentCatalog ? editing && editing.audience === value && editing.digest === digest ? editing.filters : filtersFromAudience(currentCatalog, value) : null
  const invalid = value !== undefined && Object.values(value).some(selection => selection.segment_ids.length === 0)
  function updateFilters(next: AudienceFilters) {
    if (!currentCatalog) return
    const audience = audienceFromFilters(currentCatalog, next)
    setEditing({ audience, filters: next, digest }); onChange(audience)
  }
  function toggleAll(checked: boolean) {
    if (!options) return
    if (checked) { setEditing(null); onChange(undefined) } else updateFilters(options)
  }

  return <fieldset disabled={disabled} className="audience-picker">
    <legend>Аудитория кампании</legend>
    <p className="muted">Выберите географию, пол и возраст отдельно. Внутри группы можно отметить несколько вариантов; между группами применяется пересечение. Выбор общий для всех каналов и фиксируется при запуске.</p>
    {error ? <div role="alert">Не удалось загрузить аудитории. <button type="button" onClick={() => setRetry(v => v + 1)}>Повторить загрузку аудиторий</button></div> : legacy ? <p>Этот Simulator не поддерживает выбор аудитории.</p> : !currentCatalog || !options || !filters ? <p>Загрузка аудиторий…</p> : <>
      <div className="audience-toolbar"><label className="check"><input type="checkbox" checked={value === undefined} onChange={e => toggleAll(e.target.checked)} /> Все аудитории</label><span className="muted">{value === undefined ? 'Без ограничений' : 'Выбраны ограничения аудитории'}</span></div>
      <div className="audience-dimensions">{dimensions.map(({ key, label }) => <fieldset key={key} className={'audience-dimension audience-dimension-' + key}>
        <legend>{label}</legend>
        <div className="audience-group-actions"><span className="muted">{filters[key].length} из {options[key].length}</span><button type="button" className="link-button" onClick={() => updateFilters({ ...filters, [key]: [...options[key]] })} aria-label={'Выбрать все: ' + label}>Все</button><button type="button" className="link-button" onClick={() => updateFilters({ ...filters, [key]: [] })} aria-label={'Снять выбор: ' + label}>Снять выбор</button></div>
        <div className="audience-options">{options[key].map(option => {
          const { label: name, hint } = optionLabel(key, option)
          const selected = filters[key].includes(option)
          return <label key={option} className="audience-option" data-selected={selected}>
            <input type="checkbox" aria-label={name} checked={selected} onChange={event => updateFilters({ ...filters, [key]: event.target.checked ? [...filters[key], option] : filters[key].filter(item => item !== option) })} />
            <span><strong>{name}</strong>{hint && <small>{hint}</small>}</span>
          </label>
        })}</div>
      </fieldset>)}</div>
      {invalid && <p role="alert" className="field-error">Выберите хотя бы один вариант в каждой группе. Пересечение должно быть доступно во всех каналах с сегментами.</p>}
    </>}
  </fieldset>
}
