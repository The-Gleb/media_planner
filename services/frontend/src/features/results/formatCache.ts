/** Memoises a pure label formatter by its input; Intl formatting is the costliest part of a chart redraw. */
export function cachedFormatter<T>(format: (value: T) => string, limit = 4096): (value: T) => string {
  const cache = new Map<T, string>()
  return (value: T) => {
    const hit = cache.get(value)
    if (hit !== undefined) return hit
    const label = format(value)
    if (cache.size >= limit) cache.clear()
    cache.set(value, label)
    return label
  }
}
