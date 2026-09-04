import type { ActiveRun, LaunchDraft } from '../../domain/types'

export function CampaignSummary({ session, activeDraft }: { session: ActiveRun; activeDraft: LaunchDraft }) {
  const completed = session.durationHours - session.remainingHours
  return <div className="summary-sections">
    <section className="card" aria-labelledby="simulation-summary-title">
      <h2 id="simulation-summary-title">Симуляция {session.simulationId}</h2>
      <dl className="summary-grid">
        <Item label="World seed" value={activeDraft.simulation.worldSeed} />
        <Item label="Campaign seed" value={activeDraft.simulation.campaignSeed} />
        <Item label="Начальный час" value={activeDraft.simulation.startHour} />
        <Item label="Часовой пояс" value={session.timeZone} />
        <Item label="Модель" value={`${session.engineVersion} · ${session.worldConfigDigest.slice(0, 12)}…`} />
      </dl>
    </section>
    <section className="card" aria-labelledby="campaign-summary-title">
      <div className="status-line"><h2 id="campaign-summary-title">Кампания</h2><span className="status-badge" data-tone="ok">{session.status === 'active' ? 'Активна' : 'Завершена'}</span></div>
      <dl className="summary-grid">
        <Item label="Следующий час" value={session.currentHour} />
        <Item label="Конец (не включительно)" value={session.endHourExclusive} />
        <Item label="Выполнено" value={`${completed} из ${session.durationHours}`} />
        <Item label="Осталось" value={`${session.remainingHours} ч`} />
        <Item label="Валюта" value={session.currency} />
        <Item label="Каналы" value={session.channelIds.join(', ')} />
      </dl>
    </section>
  </div>
}
function Item({ label, value }: { label: string; value: string }) { return <div className="summary-item"><dt>{label}</dt><dd>{value}</dd></div> }
