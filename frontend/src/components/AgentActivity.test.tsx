import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'

import { AgentActivity } from './AgentActivity'

describe('AgentActivity', () => {
  it('lists high-level events and can collapse', async () => {
    render(
      <AgentActivity
        events={[
          { id: 'a', label: 'Analysed request', done: true },
          { id: 'b', label: 'Retrieved 3 chunks', done: true },
        ]}
      />,
    )
    expect(screen.getByText('Analysed request')).toBeInTheDocument()
    expect(screen.getByText('Retrieved 3 chunks')).toBeInTheDocument()
    expect(screen.getByText(/never chain-of-thought/i)).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /agent activity/i }))
    expect(screen.queryByText('Analysed request')).not.toBeInTheDocument()
  })
})
