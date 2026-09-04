import { useCallback, useEffect, useState } from 'react'
import { plannerClient } from '../api/plannerClient'
import { simulatorClient } from '../api/simulatorClient'
import type { WorldMetadata } from '../domain/types'

export interface ServiceBootstrap {
  simulator: 'checking' | 'ready' | 'unavailable'
  planner: 'checking' | 'ready' | 'unavailable'
  metadata: WorldMetadata | null
}

export function useServicesBootstrap() {
  const [state, setState] = useState<ServiceBootstrap>({ simulator: 'checking', planner: 'checking', metadata: null })
  const check = useCallback(async () => {
    const [planner, simulator] = await Promise.allSettled([
      plannerClient.ready(),
      (async () => {
        if (!await simulatorClient.ready()) throw new Error('not_ready')
        return simulatorClient.metadata()
      })(),
    ])
    setState({
      planner: planner.status === 'fulfilled' && planner.value ? 'ready' : 'unavailable',
      simulator: simulator.status === 'fulfilled' ? 'ready' : 'unavailable',
      metadata: simulator.status === 'fulfilled' ? simulator.value : null,
    })
  }, [])
  const refresh = useCallback(async () => {
    setState({ simulator: 'checking', planner: 'checking', metadata: null })
    await check()
  }, [check])
  useEffect(() => {
    const timer = window.setTimeout(() => { void check() }, 0)
    return () => window.clearTimeout(timer)
  }, [check])
  return { ...state, refresh }
}
