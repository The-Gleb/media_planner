import type { ActiveRun, HourlyResult, PendingStep } from '../../domain/types'

export interface AutoRunPort {
  getSession(): ActiveRun
  createPending(session: ActiveRun): PendingStep
  submit(session: ActiveRun, pending: PendingStep): Promise<{ data: HourlyResult; etag: string | null }>
  commit(pending: PendingStep, response: { data: HourlyResult; etag: string | null }): Promise<void> | void
  shouldStop(): boolean
  waitBeforeNext?: () => Promise<void>
}

export async function runRemaining(port: AutoRunPort): Promise<'finished' | 'stopped'> {
  while (port.getSession().status === 'active' && port.getSession().remainingHours > 0) {
    if (port.shouldStop()) return 'stopped'
    const session = port.getSession()
    const pending = port.createPending(session)
    const response = await port.submit(session, pending)
    await port.commit(pending, response)
    if (response.data.status === 'finished') return 'finished'
    if (port.shouldStop()) return 'stopped'
    await port.waitBeforeNext?.()
  }
  return port.shouldStop() ? 'stopped' : 'finished'
}
