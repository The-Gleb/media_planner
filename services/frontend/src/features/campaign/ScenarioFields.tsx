import type { ScenarioDraft } from '../../domain/types'
import type { FieldErrors } from './validation'

export function ScenarioFields({ value, channelIds, disableRandomEvents, disabled, errors, onChange, onRandomEventsChange }: {
  value: ScenarioDraft; channelIds: readonly string[]; disableRandomEvents: boolean; disabled: boolean;
  errors: FieldErrors; onChange: (value: ScenarioDraft) => void; onRandomEventsChange: (value: boolean) => void
}) {
  const set = <K extends keyof ScenarioDraft>(key: K, next: ScenarioDraft[K]) => onChange({ ...value, [key]: next })
  return <div className="scenario-fields stack"><h3>Сценарий рынка</h3>
    <label><input type="checkbox" checked={disableRandomEvents} disabled={disabled} onChange={(event) => onRandomEventsChange(event.target.checked)} /> Отключить случайные drift и shock</label>
    <label><input type="checkbox" checked={value.enabled} disabled={disabled} onChange={(event) => set('enabled', event.target.checked)} /> Добавить управляемое событие</label>
    {value.enabled && <div className="form-grid">
      <label className="field">Канал<select value={value.channelId} disabled={disabled} onChange={(event) => set('channelId', event.target.value)}>{channelIds.map((id) => <option key={id}>{id}</option>)}</select></label>
      <label className="field">Метрика<select value={value.metric} disabled={disabled} onChange={(event) => set('metric', event.target.value as ScenarioDraft['metric'])}><option value="supply">Supply</option><option value="cpm">CPM</option><option value="ctr">CTR</option><option value="cr">CR</option><option value="pause">Пауза</option></select></label>
      <Field label="Начало, индекс часа" value={value.startIndex} error={errors['simulation.scenario.startIndex']} disabled={disabled} onChange={(next) => set('startIndex', next)} />
      <Field label="Длительность, часов" value={value.durationHours} error={errors['simulation.scenario.durationHours']} disabled={disabled} onChange={(next) => set('durationHours', next)} />
      <Field label={value.metric === 'pause' ? 'Множитель (для паузы игнорируется)' : 'Множитель'} value={value.multiplier} error={errors['simulation.scenario.multiplier']} disabled={disabled} onChange={(next) => set('multiplier', next)} />
    </div>}
  </div>
}

function Field({ label, value, error, disabled, onChange }: { label: string; value: string; error?: string; disabled: boolean; onChange: (value: string) => void }) {
  return <label className="field">{label}<input value={value} inputMode="decimal" disabled={disabled} onChange={(event) => onChange(event.target.value)} aria-invalid={Boolean(error)} />{error && <span className="field-error">{error}</span>}</label>
}
