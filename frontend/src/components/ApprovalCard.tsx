interface ApprovalCardProps {
  tool: string | null
  description: string | null
  preview: string | null
  busy?: boolean
  onApprove: () => void
  onReject: () => void
}

/**
 * Human-in-the-loop card. Hidden when there is no pending write.
 */
export function ApprovalCard({
  tool,
  description,
  preview,
  busy = false,
  onApprove,
  onReject,
}: ApprovalCardProps) {
  if (!description || !tool) {
    return null
  }
  return (
    <section className="approval" data-testid="approval-card">
      <h2>Proposed action</h2>
      <p>{description}</p>
      {preview ? <pre className="approval-preview">{preview}</pre> : null}
      <div className="approval-actions">
        <button type="button" disabled={busy} onClick={onApprove}>
          Approve
        </button>
        <button type="button" className="danger" disabled={busy} onClick={onReject}>
          Reject
        </button>
      </div>
    </section>
  )
}
