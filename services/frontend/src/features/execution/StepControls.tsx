import { useEffect, useRef } from 'react'
import type { ActiveRun, ExecutionStatus } from '../../domain/types'

interface Props {
  session: ActiveRun
  status: ExecutionStatus
  onStep: () => void
  onRun: () => void
  onStop: () => void
  blocked?: boolean
}

export function StepControls({ session, status, onStep, onRun, onStop, blocked = false }: Props) {
  const runRef = useRef<HTMLButtonElement>(null)
  const statusRef = useRef<HTMLSpanElement>(null)
  const previous = useRef(status)
  const running = status === 'running' || status === 'stopping'
  const busy = running || status === 'stepping'
  const finished = session.status === 'finished' || session.remainingHours === 0
  useEffect(() => {
    if ((previous.current === 'running' || previous.current === 'stopping') && (status === 'stopped' || status === 'idle')) {
      if (session.status === 'finished') statusRef.current?.focus()
      else runRef.current?.focus()
    }
    previous.current = status
  }, [status, session.status])
  return <div className="actions" aria-label="Управление симуляцией">
    <button type="button" onClick={onStep} disabled={busy || finished || blocked}>Один час</button>
    <button ref={runRef} type="button" onClick={onRun} disabled={busy || finished || blocked}>До конца</button>
    <button type="button" className="danger" onClick={onStop} disabled={!running || status === 'stopping'}>Остановить</button>
    <span ref={statusRef} tabIndex={-1} className="muted">{status === 'stepping' ? 'Выполняется час…' : status === 'running' ? 'Автоматический прогон…' : status === 'stopping' ? 'Остановка после текущего часа…' : status === 'stopped' ? 'Прогон остановлен' : finished ? 'Кампания завершена' : 'Готово к запуску'}</span>
  </div>
}
