import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { ApprovalCard } from './ApprovalCard'

describe('ApprovalCard', () => {
  it('is hidden without a pending action', () => {
    const { container } = render(
      <ApprovalCard tool={null} description={null} preview={null} onApprove={vi.fn()} onReject={vi.fn()} />,
    )
    expect(container).toBeEmptyDOMElement()
  })

  it('shows the proposal and fires approve or reject', async () => {
    const onApprove = vi.fn()
    const onReject = vi.fn()
    render(
      <ApprovalCard
        tool="save_note"
        description="Save a note to the local notebook."
        preview="Buy milk"
        onApprove={onApprove}
        onReject={onReject}
      />,
    )
    expect(screen.getByTestId('approval-card')).toHaveTextContent('Buy milk')
    await userEvent.click(screen.getByRole('button', { name: 'Approve' }))
    expect(onApprove).toHaveBeenCalledOnce()
    await userEvent.click(screen.getByRole('button', { name: 'Reject' }))
    expect(onReject).toHaveBeenCalledOnce()
  })
})
