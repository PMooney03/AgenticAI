import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { AgentActivity } from './AgentActivity'

vi.mock('../api/client', () => ({
  api: {
    listTools: vi.fn(async () => ({
      tools: [
        {
          name: 'calculator',
          description: 'arithmetic',
          read_only: true,
          requires_approval: false,
          source: 'mcp' as const,
        },
        {
          name: 'clock',
          description: 'local time',
          read_only: true,
          requires_approval: false,
          source: 'mcp' as const,
        },
      ],
    })),
  },
}))

describe('AgentActivity', () => {
  it('lists high-level events from the graph and can collapse', async () => {
    render(
      <AgentActivity
        events={[
          { id: 'a', node: 'plan', label: 'Analysed request', done: true },
          { id: 'b', node: 'retrieve', label: 'Retrieved 3 chunks', done: true },
        ]}
      />,
    )
    expect(screen.getByText('Analysed request')).toBeInTheDocument()
    expect(screen.getByText('Retrieved 3 chunks')).toBeInTheDocument()
    expect(screen.getByText(/never chain-of-thought/i)).toBeInTheDocument()
    expect(await screen.findByTestId('tool-list')).toHaveTextContent('calculator, clock')
    await userEvent.click(screen.getByRole('button', { name: /agent activity/i }))
    expect(screen.queryByText('Analysed request')).not.toBeInTheDocument()
  })
})
