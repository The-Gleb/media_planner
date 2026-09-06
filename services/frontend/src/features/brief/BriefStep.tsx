import { useState } from 'react'
import { AudienceFields } from '../campaign/AudienceFields'
import type { CampaignDraft, LaunchDraft, ScenarioDraft, SimulationDraft, WorldMetadata } from '../../domain/types'
import type { PastCampaignRecord } from '../../domain/history'
import type { FieldErrors } from '../campaign/validation'
import { ScenarioFields } from '../campaign/ScenarioFields'
import { useViewMode } from '../../app/viewMode'
import { channelLabel, currencySign, EXECUTION_HINT, EXECUTION_LABEL, KPI_LABEL, plural } from '../../app/format'
import type { ExecutionMode } from '../../domain/types'

interface Props {
  metadata: WorldMetadata
  draft: LaunchDraft
  errors: FieldErrors
  busy: boolean
  hasSession: boolean
  pastCampaigns: readonly PastCampaignRecord[]
  onClearHistory: () => void
  onChange: (draft: LaunchDraft) => void
  onSubmit: () => void
}

type Preset = 'none' | 'ctr_drop' | 'cpm_spike' | 'supply_drop' | 'pause' | 'custom'
const PRESETS: { id: Preset; label: string; hint: string }[] = [
  { id: 'none', label: 'Без шока', hint: 'Рынок меняется только за счёт случайных колебаний мира.' },
  { id: 'ctr_drop', label: 'Падение CTR на 40 %', hint: 'С середины кампании выбранный канал кликается на 40 % хуже.' },
  { id: 'cpm_spike', label: 'Скачок CPM ×1,5', hint: 'С середины кампании цена тысячи показов в канале растёт в полтора раза.' },
  { id: 'supply_drop', label: 'Исчерпание ёмкости', hint: 'С середины кампании доступный инвентарь канала падает вдвое.' },
  { id: 'pause', label: 'Приостановка канала', hint: 'Канал полностью останавливается с середины кампании.' },
]

function presetOf(scenario: ScenarioDraft): Preset {
  if (!scenario.enabled) return 'none'
  const m = Number(scenario.multiplier)
  if (scenario.metric === 'ctr' && Math.abs(m - 0.6) < 1e-9) return 'ctr_drop'
  if (scenario.metric === 'cpm' && Math.abs(m - 1.5) < 1e-9) return 'cpm_spike'
  if (scenario.metric === 'supply' && Math.abs(m - 0.5) < 1e-9) return 'supply_drop'
  if (scenario.metric === 'pause') return 'pause'
  return 'custom'
}

function applyPreset(scenario: ScenarioDraft, preset: Preset, durationHours: number): ScenarioDraft {
  const start = Math.floor(durationHours / 2)
  const base = { ...scenario, startIndex: String(start), durationHours: String(Math.max(1, durationHours - start)) }
  switch (preset) {
    case 'none': return { ...scenario, enabled: false }
    case 'ctr_drop': return { ...base, enabled: true, metric: 'ctr', multiplier: '0.6' }
    case 'cpm_spike': return { ...base, enabled: true, metric: 'cpm', multiplier: '1.5' }
    case 'supply_drop': return { ...base, enabled: true, metric: 'supply', multiplier: '0.5' }
    case 'pause': return { ...base, enabled: true, metric: 'pause', multiplier: '0' }
    default: return scenario
  }
}

export function BriefStep({ metadata, draft, errors, busy, hasSession, pastCampaigns, onClearHistory, onChange, onSubmit }: Props) {
  const [audienceReady, setAudienceReady] = useState(false)
  const [editAudience, setEditAudience] = useState(false)
  const segmented = metadata.engineVersion === 'sim-v2-delivery'
  const audienceBlocked = segmented && (!audienceReady || Object.values(draft.campaign.audience ?? {}).some(selection => !selection.segment_ids.length))
  const { expert } = useViewMode()
  const { campaign, simulation } = draft
  const setCampaign = <K extends keyof CampaignDraft>(key: K, value: CampaignDraft[K]) => {
    const next: LaunchDraft = { ...draft, campaign: { ...campaign, [key]: value } }
    if (key === 'durationHours') {
      const current = presetOf(simulation.scenario)
      const nextHours = Number(value)
      if (current !== 'none' && current !== 'custom' && Number.isFinite(nextHours) && nextHours > 0) next.simulation = { ...simulation, scenario: applyPreset(simulation.scenario, current, nextHours) }
    }
    onChange(next)
  }
  const setSimulation = <K extends keyof SimulationDraft>(key: K, value: SimulationDraft[K]) => onChange({ ...draft, simulation: { ...simulation, [key]: value } })
  const hours = Number(campaign.durationHours)
  const days = Number.isFinite(hours) && hours % 24 === 0 ? String(hours / 24) : ''
  const preset = presetOf(simulation.scenario)
  const sign = currencySign(metadata.currency)
  const hasErrors = Object.keys(errors).length > 0

  return <form className="stack" noValidate onSubmit={(event) => { event.preventDefault(); if (busy || audienceBlocked) return; setEditAudience(false); onSubmit() }} aria-labelledby="brief-title">
    <section className="card stack">
      <div className="card-head"><div><h2 id="brief-title">Бриф кампании</h2><p className="muted">Медиапланер задаёт постановку, сервис строит достижимый медиаплан и прогноз по восьми абстрактным каналам.</p></div></div>
      {hasErrors && <p className="inline-alert" role="alert">Проверьте отмеченные поля.{!expert && Object.entries(errors).filter(([key]) => key.startsWith('simulation.')).map(([key, text]) => <span key={key} className="block"> Условия рынка: {text} Откройте экспертный режим, чтобы поправить параметры стенда.</span>)}</p>}

      <div className="segmented segmented-wide" role="radiogroup" aria-label="Постановка задачи">
        <button type="button" role="radio" aria-checked={campaign.planType === 'fixed_budget'} disabled={busy} onClick={() => setCampaign('planType', 'fixed_budget')}><strong>Задача A · Фиксированный бюджет</strong><span>Максимизировать клики, конверсии или охват</span></button>
        <button type="button" role="radio" aria-checked={campaign.planType === 'target_kpi'} disabled={busy} onClick={() => onChange({ ...draft, campaign: { ...campaign, planType: 'target_kpi', strategy: 'optimized' } })}><strong>Задача B · Целевой объём</strong><span>Найти достаточный бюджет под цель</span></button>
      </div>

      <div className="form-grid">
        {campaign.planType === 'fixed_budget'
          ? <>
            <Field id="totalBudget" label={`Бюджет, ${sign}`} value={campaign.totalBudget} error={errors['campaign.totalBudget']} inputMode="decimal" disabled={busy} onChange={(v) => setCampaign('totalBudget', v)} />
            <div className="field"><label htmlFor="optimize">Что максимизируем</label><select id="optimize" value={campaign.optimize} disabled={busy} onChange={(e) => setCampaign('optimize', e.target.value as CampaignDraft['optimize'])}>{(Object.keys(KPI_LABEL) as CampaignDraft['optimize'][]).map((id) => <option key={id} value={id}>{KPI_LABEL[id]}</option>)}</select></div>
          </>
          : <>
            <div className="field"><label htmlFor="targetMetric">Целевая метрика</label><select id="targetMetric" value={campaign.targetMetric} disabled={busy} onChange={(e) => setCampaign('targetMetric', e.target.value as CampaignDraft['targetMetric'])}>{(Object.keys(KPI_LABEL) as CampaignDraft['targetMetric'][]).map((id) => <option key={id} value={id}>{KPI_LABEL[id]}</option>)}</select></div>
            <Field id="targetValue" label="Целевой объём" value={campaign.targetValue} error={errors['campaign.targetValue']} inputMode="numeric" disabled={busy} onChange={(v) => setCampaign('targetValue', v)} />
          </>}
        <Field id="durationDays" label="Срок кампании, дней" value={days} error={errors['campaign.durationHours'] && !expert ? errors['campaign.durationHours'] : undefined} inputMode="numeric" disabled={busy} placeholder={days ? undefined : `${hours} ч`} onChange={(v) => { const n = Number(v); setCampaign('durationHours', v === '' ? '' : Number.isFinite(n) ? String(Math.round(n * 24)) : campaign.durationHours) }} />
        {expert && <Field id="durationHours" label="Срок кампании, часов" value={campaign.durationHours} error={errors['campaign.durationHours']} inputMode="numeric" disabled={busy} onChange={(v) => setCampaign('durationHours', v)} />}
      </div>
      {campaign.planType === 'target_kpi' && <p className="note">Сервис подберёт минимальный бюджет по публичному каталогу. Если ёмкость каналов не позволяет достичь цели, вы получите диагноз и рекомендацию вместо плана.</p>}
    </section>

    <section className="card stack">
      <div className="card-head"><div><h2>Ведение кампании после запуска</h2><p className="muted">Как трафик-менеджер будет реагировать на расхождение факта с планом.</p></div></div>
      <div className="option-cards" role="radiogroup" aria-label="Исполнение после запуска">
        {(Object.keys(EXECUTION_LABEL) as ExecutionMode[]).map((mode) => <label key={mode} className="option-card" data-checked={campaign.execution === mode}>
          <input type="radio" name="execution" value={mode} checked={campaign.execution === mode} disabled={busy} onChange={() => setCampaign('execution', mode)} />
          <strong>{EXECUTION_LABEL[mode]}</strong><span>{EXECUTION_HINT[mode]}</span>
        </label>)}
      </div>
      <label className="check"><input type="checkbox" checked={campaign.useHistory} disabled={busy} onChange={(e) => setCampaign('useHistory', e.target.checked)} /> Учитывать опыт прошлых кампаний на этом рынке
        <span className="muted"> · {pastCampaigns.length === 0 ? 'завершённых кампаний пока нет, план строится по каталогу' : `доступно ${pastCampaigns.length} ${plural(pastCampaigns.length, 'кампания', 'кампании', 'кампаний')}`}</span>
        {pastCampaigns.length > 0 && <> <button type="button" className="link-button" disabled={busy} onClick={onClearHistory}>очистить</button></>}
      </label>
      {expert && <div className="form-grid">
        <div className="field"><label htmlFor="strategy">Алгоритм распределения</label><select id="strategy" value={campaign.planType === 'target_kpi' ? 'optimized' : campaign.strategy} disabled={busy || campaign.planType === 'target_kpi'} onChange={(e) => setCampaign('strategy', e.target.value as CampaignDraft['strategy'])}><option value="optimized">Water-filling по каталогу (optimized)</option><option value="uniform">Равномерно по каналам и часам (uniform)</option></select></div>
      </div>}
    </section>

    {segmented && <section className="card stack">
      {hasSession && <button type="button" className="secondary" disabled={busy} onClick={() => setEditAudience(true)}>Изменить аудиторию для нового запуска</button>}
      <AudienceFields digest={metadata.worldConfigDigest} value={campaign.audience} onReady={setAudienceReady} disabled={busy || (hasSession && !editAudience)} onChange={audience => setCampaign('audience', audience)} />
      {errors['campaign.audience'] && <p role="alert" className="field-error">{errors['campaign.audience']}</p>}
    </section>}

    <details className="card details" open={expert || preset !== 'none'}>
      <summary><h2>Условия рынка · стенд</h2><span className="muted">Симулятор заменяет рекламные кабинеты. Здесь задаётся шоковый сценарий для проверки устойчивости.</span></summary>
      <div className="stack">
        <div className="form-grid">
          <div className="field"><label htmlFor="shock-preset">Шоковый сценарий</label><select id="shock-preset" value={preset} disabled={busy} onChange={(e) => setSimulation('scenario', applyPreset(simulation.scenario, e.target.value as Preset, hours || 504))}>{PRESETS.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}{preset === 'custom' && <option value="custom">Своё событие</option>}</select><span className="field-hint">{PRESETS.find((item) => item.id === preset)?.hint ?? 'Параметры события заданы вручную.'}</span></div>
          {preset !== 'none' && <div className="field"><label htmlFor="shock-channel">Канал под ударом</label><select id="shock-channel" value={simulation.scenario.channelId} disabled={busy} onChange={(e) => setSimulation('scenario', { ...simulation.scenario, channelId: e.target.value })}>{metadata.channelIds.map((id) => <option key={id} value={id}>{channelLabel(id)}</option>)}</select></div>}
          <label className="check field-check"><input type="checkbox" checked={simulation.disableRandomEvents} disabled={busy} onChange={(e) => setSimulation('disableRandomEvents', e.target.checked)} /> Отключить случайные колебания рынка</label>
        </div>
        {expert && <>
          <h3>Параметры мира</h3><p className="field-hint">Seed и старт фиксируются после первого запуска, чтобы прогоны с разными стратегиями сравнивались на одном рынке. Шок и случайные колебания можно менять между прогонами.</p>
          <div className="form-grid">
            <Field id="simulationId" label="ID симуляции" value={simulation.simulationId} error={errors['simulation.simulationId']} disabled={hasSession || busy} onChange={(v) => setSimulation('simulationId', v)} />
            <Field id="worldSeed" label="Seed мира" value={simulation.worldSeed} error={errors['simulation.worldSeed']} inputMode="numeric" disabled={hasSession || busy} onChange={(v) => setSimulation('worldSeed', v)} />
            <Field id="campaignSeed" label="Seed кампании" value={simulation.campaignSeed} error={errors['simulation.campaignSeed']} inputMode="numeric" disabled={hasSession || busy} onChange={(v) => setSimulation('campaignSeed', v)} />
            <Field id="startHour" label="Старт (RFC 3339)" value={simulation.startHour} error={errors['simulation.startHour']} disabled={hasSession || busy} onChange={(v) => setSimulation('startHour', v)} />
            <Field id="timeZone" label="Часовой пояс IANA" value={simulation.timeZone} error={errors['simulation.timeZone']} disabled={hasSession || busy} onChange={(v) => setSimulation('timeZone', v)} />
          </div>
          <ScenarioFields value={simulation.scenario} channelIds={metadata.channelIds} disableRandomEvents={simulation.disableRandomEvents} disabled={busy} errors={errors} onChange={(scenario) => setSimulation('scenario', scenario)} onRandomEventsChange={(value) => setSimulation('disableRandomEvents', value)} />
        </>}
      </div>
    </details>

    <div className="actions actions-end">
      {hasSession && <span className="muted">Текущая кампания будет сброшена, симуляция начнётся заново.</span>}
      <button type="submit" className="primary" disabled={busy || audienceBlocked}>{busy ? 'Строим медиаплан…' : hasSession ? 'Пересчитать медиаплан' : 'Рассчитать медиаплан'}</button>
    </div>
  </form>
}

function Field({ id, label, value, error, onChange, ...rest }: { id: string; label: string; value: string; error?: string; onChange: (value: string) => void } & Pick<React.InputHTMLAttributes<HTMLInputElement>, 'disabled' | 'inputMode' | 'placeholder'>) {
  const errorID = `${id}-error`
  return <div className="field"><label htmlFor={id}>{label}</label><input {...rest} id={id} value={value} onChange={(e) => onChange(e.target.value)} aria-invalid={Boolean(error)} aria-describedby={error ? errorID : undefined} />{error && <span id={errorID} className="field-error">{error}</span>}</div>
}
