import { useState, useEffect, useCallback } from 'react'

export function useApi<T>(
  fetcher: () => Promise<T>,
  deps: unknown[] = [],
  options: { interval?: number } = {}
) {
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const load = useCallback(async () => {
    try {
      setError(null)
      const result = await fetcher()
      setData(result)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load')
    } finally {
      setLoading(false)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  useEffect(() => {
    load()
    if (options.interval) {
      const id = setInterval(load, options.interval)
      return () => clearInterval(id)
    }
  }, [load, options.interval])

  return { data, loading, error, reload: load }
}

export function useMutation<T, A extends unknown[]>(
  fn: (...args: A) => Promise<T>
) {
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const mutate = useCallback(async (...args: A): Promise<T | null> => {
    setLoading(true)
    setError(null)
    try {
      const result = await fn(...args)
      return result
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed')
      return null
    } finally {
      setLoading(false)
    }
  }, [fn])

  return { mutate, loading, error }
}
