import { useCallback, useEffect, useState } from 'react'
import { simulatorClient } from '../api/simulatorClient'
import type { WorldMetadata } from '../domain/types'
import { userError } from './messages'

export type BootstrapState =
  | { status: 'checking'; metadata: null; error: null }
  | { status: 'ready'; metadata: WorldMetadata; error: null }
  | { status: 'unavailable'; metadata: null; error: string }

export function useSimulatorBootstrap() {
  const [state, setState] = useState<BootstrapState>({ status: 'checking', metadata: null, error: null })
  const refresh = useCallback(async () => {
    setState({ status: 'checking', metadata: null, error: null })
    try {
      if (!await simulatorClient.ready()) throw new Error('not_ready')
      const metadata = await simulatorClient.metadata()
      setState({ status: 'ready', metadata, error: null })
    } catch (error) {
      setState({ status: 'unavailable', metadata: null, error: userError(error, 'Проверка готовности') })
    }
  }, [])
  useEffect(() => {
    let active = true
    void (async () => {
      try {
        if (!await simulatorClient.ready()) throw new Error('not_ready')
        const metadata = await simulatorClient.metadata()
        if (active) setState({ status: 'ready', metadata, error: null })
      } catch (error) {
        if (active) setState({ status: 'unavailable', metadata: null, error: userError(error, 'Проверка готовности') })
      }
    })()
    return () => { active = false }
  }, [])
  return { ...state, refresh }
}
