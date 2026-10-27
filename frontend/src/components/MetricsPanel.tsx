import { useCallback, useEffect, useState } from 'react'

import { ApiError, api } from '../api/client'
import type { EvalReport, MetricsSnapshot } from '../api/types'

function pct(value: number | null | undefined): string {
  if (value == null) {
    return '—'
  }
  return `${Math.round(value * 100)}%`
}

function ms(value: number | null | undefined): string {
  if (value == null) {
    return '—'
  }
  return `${Math.round(value)} ms`
}

export function MetricsPanel() {
  const [metrics, setMetrics] = useState<MetricsSnapshot | null>(null)
  const [report, setReport] = useState<EvalReport | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [running, setRunning] = useState(false)

  const refresh = useCallback(async () => {
    try {
      const snapshot = await api.getMetrics()
      setMetrics(snapshot)
      setError(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Metrics unavailable.')
    }
  }, [])

  useEffect(() => {
    void refresh()
    const timer = window.setInterval(() => {
      void refresh()
    }, 20_000)
    return () => window.clearInterval(timer)
  }, [refresh])

  useEffect(() => {
    let cancelled = false
    void api
      .getLatestEval()
      .then((latest) => {
        if (!cancelled) {
          setReport(latest)
        }
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [])

  async function handleEval() {
    setRunning(true)
    setError(null)
    try {
      const latest = await api.runEval()
      setReport(latest)
      await refresh()
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Eval failed.')
    } finally {
      setRunning(false)
    }
  }

  return (
    <section className="panel metrics" data-testid="metrics-panel">
      <div className="panel-head">
        <h2>LLMOps</h2>
        <span className="muted">{metrics ? `${metrics.chats} chats` : '…'}</span>
      </div>
      {error ? <p className="banner error">{error}</p> : null}
      {metrics ? (
        <div className="metrics-grid">
          <div className="metric">
            <span className="metric-label">LLM p95</span>
            <span className="metric-value">{ms(metrics.llm.p95_ms)}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Cited</span>
            <span className="metric-value">{pct(metrics.citation_rate_avg)}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Grounded</span>
            <span className="metric-value">{pct(metrics.groundedness_avg)}</span>
          </div>
          <div className="metric">
            <span className="metric-label">Tools</span>
            <span className="metric-value">{metrics.tool_calls}</span>
          </div>
        </div>
      ) : (
        <p className="empty">Live counts appear after the first chat.</p>
      )}
      <div className="eval-row">
        <button type="button" className="text-btn" disabled={running} onClick={() => void handleEval()}>
          {running ? 'Running eval…' : 'Run golden eval'}
        </button>
        {report ? (
          <span
            className={`eval-badge ${report.failed === 0 ? 'eval-pass' : 'eval-fail'}`}
            data-testid="eval-summary"
          >
            {report.passed}/{report.total} pass · {report.duration_ms} ms
          </span>
        ) : (
          <span className="muted">Offline fakes, no Ollama.</span>
        )}
      </div>
    </section>
  )
}
