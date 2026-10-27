import type { WorkflowEvent } from '../api/types'

export type { WorkflowEvent }

/**
 * Placeholder steps shown while the request is in flight.
 * Completed steps come from ``ChatResponse.workflow`` (the LangGraph trace).
 */
export function pendingWorkflow(): WorkflowEvent[] {
  return [{ id: 'plan', node: 'plan', label: 'Analysing request', done: false }]
}
