import type { ActiveRun, ExecutionStatus } from '../../domain/types'

export function RunProgress({ session, status }: { session: ActiveRun; status: ExecutionStatus }) {
  const completed = session.durationHours - session.remainingHours
  const percent = session.durationHours === 0 ? 0 : completed / session.durationHours * 100
  const virtualTime = new Intl.DateTimeFormat('ru-RU', {
    timeZone: session.timeZone,
    day: '2-digit', month: 'short', year: 'numeric', hour: '2-digit', minute: '2-digit',
  }).format(new Date(session.currentHour))
  return <div className="run-progress" aria-live={status === 'running' ? 'off' : 'polite'}>
    <div className="virtual-clock"><span>Виртуальное время кампании</span><strong>{virtualTime}</strong><small>{session.timeZone}</small></div>
    <label htmlFor="campaign-progress">Прогресс: {completed} выполнено, {session.remainingHours} {session.completionReason ? 'не использовано' : 'осталось'}, {percent.toFixed(1)}% · час {completed} из {session.durationHours}</label>
    <progress id="campaign-progress" max={session.durationHours} value={completed}>{percent.toFixed(1)}%</progress>
  </div>
}
