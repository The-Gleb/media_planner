import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react'

export type ViewMode = 'business' | 'expert'
const STORAGE_KEY = 'media-planner.view-mode'

interface ViewModeValue { mode: ViewMode; expert: boolean; setMode: (mode: ViewMode) => void }
const ViewModeContext = createContext<ViewModeValue>({ mode: 'business', expert: false, setMode: () => {} })

function readStored(): ViewMode {
  try { return localStorage.getItem(STORAGE_KEY) === 'expert' ? 'expert' : 'business' } catch { return 'business' }
}

export function ViewModeProvider({ children, initial }: { children: ReactNode; initial?: ViewMode }) {
  const [mode, setModeState] = useState<ViewMode>(() => initial ?? readStored())
  const setMode = useCallback((next: ViewMode) => {
    setModeState(next)
    try { localStorage.setItem(STORAGE_KEY, next) } catch { /* storage unavailable */ }
  }, [])
  const value = useMemo(() => ({ mode, expert: mode === 'expert', setMode }), [mode, setMode])
  return <ViewModeContext.Provider value={value}>{children}</ViewModeContext.Provider>
}

export function useViewMode(): ViewModeValue { return useContext(ViewModeContext) }

/** Renders children only in expert mode. */
export function ExpertOnly({ children }: { children: ReactNode }) {
  const { expert } = useViewMode()
  return expert ? <>{children}</> : null
}

export function ViewModeToggle() {
  const { mode, setMode } = useViewMode()
  return <div className="segmented" role="radiogroup" aria-label="Режим интерфейса">
    <button type="button" role="radio" aria-checked={mode === 'business'} onClick={() => setMode('business')}>Бизнес</button>
    <button type="button" role="radio" aria-checked={mode === 'expert'} onClick={() => setMode('expert')}>Эксперт</button>
  </div>
}
