interface ApprovalCardProps {
  description: string | null
  onApprove: () => void
  onReject: () => void
}

/**
 * Human-in-the-loop card. Phase 6 wires this to LangGraph interrupts.
 * Hidden when there is no pending action (the Phase 3 default).
 */
export function ApprovalCard({ description, onApprove, onReject }: ApprovalCardProps) {
  if (!description) {
    return null
  }
  return (
    <section className="approval" data-testid="approval-card">
      <h2>Proposed action</h2>
      <p>{description}</p>
      <div className="approval-actions">
        <button type="button" onClick={onApprove}>
          Approve
        </button>
        <button type="button" className="danger" onClick={onReject}>
          Reject
        </button>
      </div>
    </section>
  )
}
