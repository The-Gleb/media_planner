import type { ActiveRun, ExecutionStatus } from '../../domain/types'

export function RunProgress({ session, status }: { session: ActiveRun; status: ExecutionStatus }) {
  const completed = session.durationHours - session.remainingHours
  const percent = session.durationHours === 0 ? 0 : completed / session.durationHours * 100
  return <div aria-live={status === 'running' ? 'off' : 'polite'}>
    <label htmlFor="campaign-progress">Прогресс: {completed} выполнено, {session.remainingHours} осталось, {percent.toFixed(1)}%</label>
    <progress id="campaign-progress" max={session.durationHours} value={completed}>{percent.toFixed(1)}%</progress>
  </div>
}
