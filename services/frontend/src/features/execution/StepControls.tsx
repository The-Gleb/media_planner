import { useEffect, useRef } from 'react'
import type { ActiveRun, ExecutionStatus } from '../../domain/types'

interface Props {
  session: ActiveRun
  status: ExecutionStatus
  onStep: () => void
  onRun: () => void
  onStop: () => void
  playbackDelayMs: number
  onPlaybackDelayChange: (delayMs: number) => void
  blocked?: boolean
}

const SPEEDS = [
  { delayMs: 1000, label: '1 час/сек' },
  { delayMs: 500, label: '2 часа/сек' },
  { delayMs: 200, label: '5 часов/сек' },
  { delayMs: 0, label: 'Без задержки' },
] as const

export function StepControls({ session, status, onStep, onRun, onStop, playbackDelayMs, onPlaybackDelayChange, blocked = false }: Props) {
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
  return <div className="timelapse-controls">
    <div className="playback-speed field">
      <label htmlFor="playback-speed">Скорость таймлапса</label>
      <select id="playback-speed" value={playbackDelayMs} onChange={(event) => onPlaybackDelayChange(Number(event.target.value))} disabled={finished || blocked}>
        {SPEEDS.map((speed) => <option key={speed.delayMs} value={speed.delayMs}>{speed.label}</option>)}
      </select>
    </div>
    <div className="actions" aria-label="Управление симуляцией">
      <button type="button" className="secondary" onClick={onStep} disabled={busy || finished || blocked}>Один час</button>
      <button ref={runRef} type="button" onClick={onRun} disabled={busy || finished || blocked}>{status === 'stopped' ? 'Продолжить таймлапс' : 'Запустить таймлапс'}</button>
      <button type="button" className="danger" onClick={onStop} disabled={!running || status === 'stopping'}>Пауза</button>
    </div>
    <span ref={statusRef} tabIndex={-1} className="playback-status muted">{status === 'stepping' ? 'Выполняется один час…' : status === 'running' ? 'Кампания идёт в ускоренном времени' : status === 'stopping' ? 'Пауза после текущего часа…' : status === 'stopped' ? 'Таймлапс на паузе' : finished ? 'Кампания завершена' : 'Готово к запуску'}</span>
  </div>
}
