import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'

import { MetricsPanel } from './MetricsPanel'

vi.mock('../api/client', () => ({
  ApiError: class ApiError extends Error {
    status = 500
    requestId = null
  },
  api: {
    getMetrics: vi.fn(async () => ({
      chats: 4,
      chats_completed: 3,
      chats_paused: 1,
      chats_rag: 2,
      chats_refused: 0,
      http_requests: 12,
      http_errors: 0,
      tool_calls: 1,
      approvals_approved: 1,
      approvals_rejected: 0,
      prompt_tokens: 80,
      completion_tokens: 20,
      llm: { count: 3, avg_ms: 12, p50_ms: 10, p95_ms: 18, max_ms: 18 },
      retrieval: { count: 2, avg_ms: 4, p50_ms: 4, p95_ms: 5, max_ms: 5 },
      citation_rate_avg: 0.5,
      groundedness_avg: 0.82,
      tools: { calculator: 1 },
      routes: { 'POST /chat': 4 },
    })),
    getLatestEval: vi.fn(async () => {
      throw new Error('none yet')
    }),
    runEval: vi.fn(async () => ({
      ran_at: '2026-10-27T16:00:00+00:00',
      total: 6,
      passed: 6,
      failed: 0,
      duration_ms: 42,
      cases: [],
    })),
  },
}))

describe('MetricsPanel', () => {
  it('renders live snapshot numbers and runs eval', async () => {
    render(<MetricsPanel />)
    expect(await screen.findByText('4 chats')).toBeInTheDocument()
    expect(screen.getByText('50%')).toBeInTheDocument()
    expect(screen.getByText('82%')).toBeInTheDocument()
    expect(screen.getByText('18 ms')).toBeInTheDocument()
    await userEvent.click(screen.getByRole('button', { name: /run golden eval/i }))
    expect(await screen.findByTestId('eval-summary')).toHaveTextContent('6/6 pass')
  })
})
