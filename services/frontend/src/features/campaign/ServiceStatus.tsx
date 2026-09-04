import type { ServiceBootstrap } from '../../app/useServicesBootstrap'

export function ServiceStatus({ state, onRetry }: { state: ServiceBootstrap; onRetry: () => void }) {
  return <section className="card" aria-labelledby="services-title"><div className="status-line">
    <h2 id="services-title">Сервисы</h2>
    <Badge name="Simulator" status={state.simulator} /><Badge name="Planner" status={state.planner} />
    {(state.simulator === 'unavailable' || state.planner === 'unavailable') && <button className="secondary" type="button" onClick={onRetry}>Повторить</button>}
  </div>{state.metadata && <p className="muted">Модель {state.metadata.engineVersion} · валюта {state.metadata.currency} · каналов {state.metadata.channelIds.length}</p>}</section>
}

function Badge({ name, status }: { name: string; status: ServiceBootstrap['planner'] }) {
  return <span className="status-badge" data-tone={status === 'ready' ? 'ok' : status === 'unavailable' ? 'bad' : undefined}>{name}: {status === 'ready' ? 'Готов' : status === 'checking' ? 'Проверка…' : 'Недоступен'}</span>
}
