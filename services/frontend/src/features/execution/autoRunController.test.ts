import { describe, expect, it } from 'vitest'
import { runRemaining } from './autoRunController'
import { result, session } from '../../test/fixtures'
import type { ActiveRun, PendingStep } from '../../domain/types'

describe('automatic run barrier', () => {
  it('awaits commit, replanning and playback pacing before a next step', async () => {
    let current: ActiveRun = session, calls = 0
    let releaseReplan!: () => void, releasePace!: () => void
    const order: string[] = []
    const replanBarrier = new Promise<void>((resolve) => { releaseReplan = resolve })
    const paceBarrier = new Promise<void>((resolve) => { releasePace = resolve })
    const pending: PendingStep = { stepId: 'id', expectedHour: session.currentHour, actions: [], etag: null, attempt: 1 }
    const running = runRemaining({
      getSession: () => current,
      createPending: () => pending,
      submit: async () => {
        calls++
        order.push('step')
        return { data: result({ status: calls === 2 ? 'finished' : 'active', remainingHours: 2 - calls }), etag: null }
      },
      commit: async () => {
        order.push('facts')
        await replanBarrier
        order.push('replan')
        current = { ...current, remainingHours: current.remainingHours - 1, status: calls === 2 ? 'finished' : 'active' }
      },
      shouldStop: () => false,
      waitBeforeNext: async () => { order.push('pace'); await paceBarrier },
    })
    await Promise.resolve()
    await Promise.resolve()
    expect(calls).toBe(1)
    releaseReplan()
    await Promise.resolve()
    await Promise.resolve()
    expect(calls).toBe(1)
    releasePace()
    await running
    expect(order).toEqual(['step', 'facts', 'replan', 'pace', 'step', 'facts', 'replan'])
  })
})
