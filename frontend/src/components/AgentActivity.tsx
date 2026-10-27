import { useEffect, useState } from 'react'

import { api } from '../api/client'
import type { ToolInfo, WorkflowEvent } from '../api/types'

interface AgentActivityProps {
  events: WorkflowEvent[]
}

export function AgentActivity({ events }: AgentActivityProps) {
  const [open, setOpen] = useState(true)
  const [tools, setTools] = useState<ToolInfo[]>([])

  useEffect(() => {
    let cancelled = false
    void api
      .listTools()
      .then((result) => {
        if (!cancelled) {
          setTools(result.tools)
        }
      })
      .catch(() => undefined)
    return () => {
      cancelled = true
    }
  }, [])

  return (
    <section className="panel activity" data-testid="agent-activity">
      <button type="button" className="panel-head collapsible" onClick={() => setOpen((value) => !value)}>
        <h2>Agent activity</h2>
        <span className="muted">{open ? 'Hide' : 'Show'}</span>
      </button>
      {open ? (
        events.length === 0 ? (
          <p className="empty">
            High-level workflow steps will appear after you ask a question. Hidden model
            reasoning is never shown.
          </p>
        ) : (
          <ol className="activity-list">
            {events.map((event) => (
              <li key={event.id} className={event.done ? 'done' : 'pending'}>
                <span className="tick" aria-hidden="true">
                  {event.done ? '✓' : '…'}
                </span>
                {event.label}
              </li>
            ))}
          </ol>
        )
      ) : null}
      {tools.length > 0 ? (
        <p className="footnote" data-testid="tool-list">
          Tools: {tools.map((tool) => tool.name).join(', ')}
        </p>
      ) : null}
      <p className="footnote">
        Steps come from the LangGraph run. Only observable actions, never chain-of-thought.
      </p>
    </section>
  )
}
