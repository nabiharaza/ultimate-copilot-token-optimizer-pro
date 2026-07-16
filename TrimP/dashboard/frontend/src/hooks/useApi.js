import { useState, useEffect, useCallback, useRef } from 'react'

const BASE = ''
export const REFRESH_EVENT = 'trimp:refresh'

export function useRefreshTick() {
  const [tick, setTick] = useState(0)

  useEffect(() => {
    const handleRefresh = () => setTick(value => value + 1)
    window.addEventListener(REFRESH_EVENT, handleRefresh)
    return () => window.removeEventListener(REFRESH_EVENT, handleRefresh)
  }, [])

  return tick
}

export function useApi(path, deps = []) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const requestRef = useRef(null)

  const fetch_ = useCallback(async () => {
    if (!path) {
      setLoading(false)
      return
    }
    requestRef.current?.abort()
    const controller = new AbortController()
    requestRef.current = controller
    setLoading(true)
    try {
      const res = await fetch(BASE + path, { signal: controller.signal })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setData(await res.json())
      setError(null)
    } catch (e) {
      if (e.name !== 'AbortError') setError(e.message)
    } finally {
      if (requestRef.current === controller) {
        requestRef.current = null
        setLoading(false)
      }
    }
  }, [path])

  useEffect(() => {
    fetch_()
    window.addEventListener(REFRESH_EVENT, fetch_)
    return () => {
      window.removeEventListener(REFRESH_EVENT, fetch_)
      requestRef.current?.abort()
    }
  }, [fetch_, ...deps])

  return { data, loading, error, refetch: fetch_ }
}

export function usePolling(path, intervalMs = 5000) {
  // Keep the legacy interval argument for callers, but use the shared one-second
  // refresh signal so every page follows the same update contract.
  return useApi(path)
}
