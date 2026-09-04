import type { BootstrapState } from '../../app/useSimulatorBootstrap'

export function SimulatorStatus({ state, onRetry }: { state: BootstrapState; onRetry: () => void }) {
  const ready = state.status === 'ready'
  return <section className="card" aria-labelledby="simulator-status-title">
    <div className="status-line">
      <h2 id="simulator-status-title">Simulator</h2>
      <span className="status-badge" data-tone={ready ? 'ok' : state.status === 'unavailable' ? 'bad' : undefined}>
        {ready ? 'Готов' : state.status === 'checking' ? 'Проверка…' : 'Недоступен'}
      </span>
      {state.status === 'unavailable' && <button type="button" className="secondary" onClick={onRetry}>Повторить</button>}
    </div>
    {ready && <p className="muted">Модель {state.metadata.engineVersion} · валюта {state.metadata.currency} · каналов {state.metadata.channelIds.length} · digest {state.metadata.worldConfigDigest.slice(0, 12)}…</p>}
    {state.status === 'unavailable' && <p className="error" role="alert">{state.error}</p>}
  </section>
}
