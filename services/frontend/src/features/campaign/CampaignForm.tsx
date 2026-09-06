import type { LaunchDraft, SimulationDraft, WorldMetadata } from '../../domain/types'
import type { FieldErrors } from './validation'
import { PlanningFields } from './PlanningFields'
import { ScenarioFields } from './ScenarioFields'
import { useState } from 'react'
import { AudienceFields } from './AudienceFields'

interface Props {
  metadata: WorldMetadata
  draft: LaunchDraft
  errors: FieldErrors
  busy: boolean
  hasSession: boolean
  onChange: (draft: LaunchDraft) => void
  onSubmit: () => void
}

export function CampaignForm({ metadata, draft, errors, busy, hasSession, onChange, onSubmit }: Props) {
  const segmented = metadata.engineVersion === 'sim-v2-delivery'
  const [audienceReady, setAudienceReady] = useState(false)
  const [editAudience, setEditAudience] = useState(false)
  const emptyAudience = Object.values(draft.campaign.audience ?? {}).some(s => s.segment_ids.length === 0)
  const setSimulation = (field: keyof SimulationDraft, value: string) => onChange({
    ...draft,
    simulation: { ...draft.simulation, [field]: value },
  })

  return <section className="card" aria-labelledby="launch-form-title">
    <h2 id="launch-form-title">Настройка запуска</h2>
    {Object.keys(errors).length > 0 && <p className="error" role="alert">Проверьте отмеченные поля.</p>}
    <form onSubmit={(event) => { event.preventDefault(); if (segmented && (!audienceReady || emptyAudience)) return; setEditAudience(false); onSubmit() }} noValidate className="stack">
      <fieldset>
        <legend><strong>Симуляция</strong></legend>
        <p className="field-hint">Мир и начальное состояние. После создания эти параметры сохраняются для повторных запусков кампании.</p>
        <div className="form-grid">
          <Field id="simulationId" label="ID симуляции" value={draft.simulation.simulationId} error={errors['simulation.simulationId']} onChange={(v) => setSimulation('simulationId', v)} disabled={hasSession || busy} />
          <Field id="worldSeed" label="World seed" value={draft.simulation.worldSeed} error={errors['simulation.worldSeed']} onChange={(v) => setSimulation('worldSeed', v)} inputMode="numeric" disabled={hasSession || busy} />
          <Field id="campaignSeed" label="Campaign seed" value={draft.simulation.campaignSeed} error={errors['simulation.campaignSeed']} onChange={(v) => setSimulation('campaignSeed', v)} inputMode="numeric" disabled={hasSession || busy} />
          <Field id="startHour" label="Начальный час симуляции (RFC 3339)" value={draft.simulation.startHour} error={errors['simulation.startHour']} onChange={(v) => setSimulation('startHour', v)} placeholder="2026-09-03T06:00:00Z" disabled={hasSession || busy} />
          <Field id="timeZone" label="Часовой пояс IANA" value={draft.simulation.timeZone} error={errors['simulation.timeZone']} onChange={(v) => setSimulation('timeZone', v)} placeholder="Europe/Moscow" disabled={hasSession || busy} />
        </div>
        <ScenarioFields value={draft.simulation.scenario} channelIds={metadata.channelIds} disableRandomEvents={draft.simulation.disableRandomEvents} disabled={hasSession || busy} errors={errors} onChange={(scenario) => onChange({ ...draft, simulation: { ...draft.simulation, scenario } })} onRandomEventsChange={(disableRandomEvents) => onChange({ ...draft, simulation: { ...draft.simulation, disableRandomEvents } })} />
      </fieldset>

      <fieldset>
        <legend><strong>Кампания</strong></legend>
        <p className="field-hint">План строится до запуска симуляции. Бюджет равномерно распределяется по всем часам и каналам.</p>
        <div className="form-grid campaign-fields">
          <Field id="durationHours" label="Длительность, часов" value={draft.campaign.durationHours} error={errors['campaign.durationHours']} onChange={(value) => onChange({ ...draft, campaign: { ...draft.campaign, durationHours: value } })} inputMode="numeric" disabled={busy} />
        </div>
        <PlanningFields value={draft.campaign} currency={metadata.currency} errors={errors} disabled={busy} onChange={(campaign) => onChange({ ...draft, campaign })} />
      </fieldset>

      {segmented && <>
        {hasSession && <button type="button" disabled={busy} onClick={() => setEditAudience(true)}>Изменить аудиторию для нового запуска</button>}
        <AudienceFields digest={metadata.worldConfigDigest} value={draft.campaign.audience} onReady={setAudienceReady} disabled={busy || (hasSession && !editAudience)} onChange={audience => onChange({ ...draft, campaign: { ...draft.campaign, audience } })} />
      </>}
      <div className="actions"><button type="submit" disabled={busy || (segmented && (!audienceReady || emptyAudience))}>{busy ? 'Построение плана…' : hasSession ? 'Перепланировать, сбросить и запустить' : 'Построить план и запустить'}</button></div>
    </form>
  </section>
}

function Field({ id, label, value, error, onChange, ...rest }: { id: string; label: string; value: string; error?: string; onChange: (value: string) => void } & Pick<React.InputHTMLAttributes<HTMLInputElement>, 'disabled' | 'inputMode' | 'placeholder'>) {
  const errorID = `${id}-error`
  return <div className="field"><label htmlFor={id}>{label}</label><input {...rest} id={id} value={value} onChange={(e) => onChange(e.target.value)} aria-invalid={Boolean(error)} aria-describedby={error ? errorID : undefined} />{error && <span id={errorID} className="field-error">{error}</span>}</div>
}
