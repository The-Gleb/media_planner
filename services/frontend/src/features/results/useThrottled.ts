import { useEffect, useRef, useState } from 'react'

/**
 * Value that follows `input` immediately when idle and at most once per `intervalMs` while
 * `running`. Charts redraw thousands of SVG nodes per update; during a timelapse the eye cannot
 * follow every hour anyway, and re-rendering every hour dominated the per-hour cycle.
 */
export function useThrottled<T>(input: T, running: boolean, intervalMs = 700): T {
  const [shown, setShown] = useState(input)
  const lastRef = useRef(0)
  useEffect(() => {
    if (!running) return
    const wait = Math.max(0, intervalMs - (Date.now() - lastRef.current))
    const timer = setTimeout(() => {
      lastRef.current = Date.now()
      setShown(input)
    }, wait)
    return () => clearTimeout(timer)
  }, [input, running, intervalMs])
  return running ? shown : input
}
