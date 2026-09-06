import { useEffect, useState } from 'react'
import { simulatorClient } from '../../api/simulatorClient'
import type { Audience, AudienceCatalog, AudienceSegment } from '../../domain/audience'

function segmentKey(segment: AudienceSegment): string {
  return JSON.stringify([segment.geo, segment.gender, segment.age_from, segment.age_to_exclusive])
}

export function AudienceFields({ value, onChange, disabled, digest, onReady }: { value?: Audience; onChange: (value: Audience | undefined) => void; disabled: boolean; digest: string; onReady: (ready: boolean) => void }) {
  const [catalog, setCatalog] = useState<AudienceCatalog | null>(null)
  const [error, setError] = useState(false)
  const [legacy, setLegacy] = useState(false)
  const [retry, setRetry] = useState(0)
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
  const channels = catalog?.channels.filter(channel => channel.segments.length > 0) ?? []
  const segments = channels[0]?.segments.filter(segment => channels.every(channel =>
    channel.segments.some(candidate => segmentKey(candidate) === segmentKey(segment)))) ?? []
  const allAudiences = channels.every(channel => value?.[channel.channel_id] === undefined)
  const selectedKeys = segments.filter(segment => channels.every(channel => {
    const selection = value?.[channel.channel_id]
    return !selection || channel.segments.some(candidate => segmentKey(candidate) === segmentKey(segment) && selection.segment_ids.includes(candidate.segment_id))
  })).map(segmentKey)
  function selectSegments(keys: string[]) {
    onChange(Object.fromEntries(channels.map(channel => [channel.channel_id, {
      segment_ids: channel.segments.filter(segment => keys.includes(segmentKey(segment))).map(segment => segment.segment_id),
    }])))
  }
  return <fieldset disabled={disabled}>
    <legend><strong>Аудитория кампании</strong></legend>
    <p>Единый выбор для всех каналов фиксируется на весь прогон. Изменение применяется только при новом запуске после сброса.</p>
    {error ? <div role="alert">Не удалось загрузить аудитории. <button type="button" onClick={() => setRetry(v => v + 1)}>Повторить загрузку аудиторий</button></div> : legacy ? <p>Этот Simulator не поддерживает выбор аудитории.</p> : !catalog ? <p>Загрузка аудиторий…</p> : channels.length > 0 && <>
      <label><input type="checkbox" checked={allAudiences} disabled={!segments.length} onChange={e => e.target.checked ? onChange(undefined) : selectSegments(segments.map(segmentKey))} /> Все аудитории</label>
      {!segments.length && <p>В каталоге нет общих сегментов для всех каналов. Доступны все аудитории.</p>}
      {!allAudiences && <>
        {segments.map(s => <label key={segmentKey(s)} style={{ display: 'block' }}><input type="checkbox" checked={selectedKeys.includes(segmentKey(s))} onChange={e => selectSegments(e.target.checked ? [...selectedKeys, segmentKey(s)] : selectedKeys.filter(key => key !== segmentKey(s)))} />{s.geo === 'moscow' ? 'Москва' : s.geo === 'other' ? 'Другие регионы' : s.geo} · {s.gender === 'female' ? 'Женщины' : s.gender === 'male' ? 'Мужчины' : s.gender} · {s.age_from}–{s.age_to_exclusive - 1}</label>)}
        {!selectedKeys.length && <p role="alert">Выберите хотя бы один сегмент.</p>}
      </>}
    </>}
  </fieldset>
}
