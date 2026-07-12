import { useState, useEffect, useCallback } from 'react'

const BASE = ''

export function useApi(path, deps = []) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const fetch_ = useCallback(async () => {
    setLoading(true)
    try {
      const res = await fetch(BASE + path)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setData(await res.json())
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [path])

  useEffect(() => { fetch_() }, [fetch_, ...deps])

  return { data, loading, error, refetch: fetch_ }
}

export function usePolling(path, intervalMs = 5000) {
  const { data, loading, error, refetch } = useApi(path)
  useEffect(() => {
    const id = setInterval(refetch, intervalMs)
    return () => clearInterval(id)
  }, [refetch, intervalMs])
  return { data, loading, error }
}
