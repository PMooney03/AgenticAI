import { useState } from 'react'

import type { WorkflowEvent } from '../lib/workflow'

interface AgentActivityProps {
  events: WorkflowEvent[]
}

export function AgentActivity({ events }: AgentActivityProps) {
  const [open, setOpen] = useState(true)

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
      <p className="footnote">
        Placeholder for the LangGraph trace (Phase 4). Only observable steps, never chain-of-thought.
      </p>
    </section>
  )
}
