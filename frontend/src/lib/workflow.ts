import type { ChatMode, RetrievalStats } from '../api/types'

export interface WorkflowEvent {
  id: string
  label: string
  done: boolean
}

/**
 * High-level events derived from the API response.
 *
 * Phase 4 will replace this with the agent's real trace. Until then we only
 * surface observable facts (retrieval happened, N chunks came back) — never
 * hidden model reasoning.
 */
export function workflowEvents(
  mode: ChatMode | undefined,
  retrieval: RetrievalStats | null | undefined,
  loading: boolean,
): WorkflowEvent[] {
  if (loading) {
    return [
      { id: 'analyse', label: 'Analysing request', done: true },
      {
        id: 'retrieve',
        label: mode === 'chat' ? 'Skipping document search' : 'Searching documents',
        done: false,
      },
    ]
  }
  if (!mode) {
    return []
  }
  const events: WorkflowEvent[] = [{ id: 'analyse', label: 'Analysed request', done: true }]
  if (mode === 'rag') {
    const n = retrieval?.retrieved_chunks ?? 0
    events.push({ id: 'search', label: 'Searched documents', done: true })
    events.push({
      id: 'chunks',
      label: n === 1 ? 'Retrieved 1 chunk' : `Retrieved ${n} chunks`,
      done: true,
    })
  }
  events.push({ id: 'answer', label: 'Generated response', done: true })
  return events
}
