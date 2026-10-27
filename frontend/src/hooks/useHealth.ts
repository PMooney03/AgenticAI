import { useCallback, useEffect, useState } from 'react'

import { api } from '../api/client'
import type { HealthResponse } from '../api/types'

const POLL_MS = 20_000

export function useHealth() {
  const [health, setHealth] = useState<HealthResponse | null>(null)
  const [error, setError] = useState<string | null>(null)

  const refresh = useCallback(async () => {
    try {
      const result = await api.getHealth()
      setHealth(result)
      setError(null)
    } catch (err) {
      setHealth(null)
      setError(err instanceof Error ? err.message : 'API unreachable.')
    }
  }, [])

  useEffect(() => {
    void refresh()
    const timer = window.setInterval(() => {
      void refresh()
    }, POLL_MS)
    return () => window.clearInterval(timer)
  }, [refresh])

  return { health, error, refresh }
}
