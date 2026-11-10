import { describe, expect, it, vi } from 'vitest'

import { createClient, parseApiErrorBody, trimHistory } from './client'
import { ApiError } from './types'

describe('trimHistory', () => {
  it('keeps the last 20 turns', () => {
    const history = Array.from({ length: 25 }, (_, i) => ({
      role: i % 2 === 0 ? ('user' as const) : ('assistant' as const),
      content: `m${i}`,
    }))
    const trimmed = trimHistory(history)
    expect(trimmed).toHaveLength(20)
    expect(trimmed[0]?.content).toBe('m5')
    expect(trimmed.at(-1)?.content).toBe('m24')
  })
})

describe('parseApiErrorBody', () => {
  it('reads detail and request_id from JSON', () => {
    const error = parseApiErrorBody(
      503,
      JSON.stringify({ detail: 'The language model is currently unavailable.', request_id: 'abc' }),
      'fallback',
    )
    expect(error).toBeInstanceOf(ApiError)
    expect(error.status).toBe(503)
    expect(error.message).toContain('unavailable')
    expect(error.requestId).toBe('abc')
  })

  it('falls back when the body is not JSON', () => {
    const error = parseApiErrorBody(500, 'nope', 'rid')
    expect(error.message).toBe('nope')
    expect(error.requestId).toBe('rid')
  })
})

describe('createClient', () => {
  it('sends chat payload with a request id and returns sources', async () => {
    const fetchMock = vi.fn<typeof fetch>(async (_input, init) => {
      const headers = new Headers(init?.headers)
      expect(headers.get('X-Request-ID')).toMatch(/^[a-f0-9]{32}$/)
      expect(headers.get('Content-Type')).toBe('application/json')
      const body = JSON.parse(String(init?.body)) as { message: string; use_documents: boolean }
      expect(body.message).toBe('How much leave?')
      expect(body.use_documents).toBe(true)
      return new Response(
        JSON.stringify({
          answer: '27 days [Source 1].',
          mode: 'rag',
          model: 'qwen2.5:14b',
          prompt_version: 'rag-system-v1',
          request_id: 'abc',
          latency_ms: 12,
          sources: [
            {
              label: 1,
              document_id: 'd1',
              document_name: 'handbook.md',
              page: null,
              score: 0.81,
              snippet: '27 days',
              cited: true,
            },
          ],
          retrieval: { retrieved_chunks: 1, retrieval_ms: 4, cited_sources: 1 },
          prompt_tokens: 10,
          completion_tokens: 5,
          workflow: [
            { id: 'plan-0', node: 'plan', label: 'Analysed request', done: true },
            { id: 'retrieve-1', node: 'retrieve', label: 'Searched documents', done: true },
            { id: 'answer-2', node: 'generate_answer', label: 'Generated response', done: true },
          ],
        }),
        { status: 200, headers: { 'Content-Type': 'application/json', 'X-Request-ID': 'abc' } },
      )
    })

    const client = createClient({ baseUrl: 'http://api.test', fetch: fetchMock })
    const result = await client.chat({
      message: 'How much leave?',
      history: [],
      use_documents: true,
    })
    expect(result.sources[0]?.document_name).toBe('handbook.md')
    expect(result.prompt_version).toBe('rag-system-v1')
    expect(result.workflow.map((event) => event.label)).toContain('Searched documents')
  })

  it('lists allowlisted tools', async () => {
    const fetchMock = vi.fn<typeof fetch>(async () => {
      return new Response(
        JSON.stringify({
          tools: [
            {
              name: 'calculator',
              description: 'math',
              read_only: true,
              requires_approval: false,
              source: 'mcp',
            },
          ],
        }),
        { status: 200 },
      )
    })
    const client = createClient({ baseUrl: 'http://api.test', fetch: fetchMock })
    const result = await client.listTools()
    expect(result.tools[0]?.name).toBe('calculator')
    expect(String(fetchMock.mock.calls[0]?.[0])).toBe('http://api.test/agent/tools')
  })

  it('posts an approval decision', async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      expect(String(input)).toBe('http://api.test/agent/runs/abc/decision')
      expect(init?.method).toBe('POST')
      expect(JSON.parse(String(init?.body))).toEqual({ approved: true })
      return new Response(
        JSON.stringify({
          answer: 'Saved.',
          mode: 'chat',
          model: 'm',
          prompt_version: 'agent-answer-v1',
          request_id: 'abc',
          latency_ms: 1,
          sources: [],
          retrieval: null,
          prompt_tokens: 1,
          completion_tokens: 1,
          workflow: [],
          pending_approval: null,
        }),
        { status: 200 },
      )
    })
    const client = createClient({ baseUrl: 'http://api.test', fetch: fetchMock })
    const result = await client.decideRun('abc', true)
    expect(result.answer).toBe('Saved.')
    expect(result.pending_approval).toBeNull()
  })

  it('fetches metrics and runs eval', async () => {
    const fetchMock = vi.fn<typeof fetch>(async (input, init) => {
      const url = String(input)
      if (url.endsWith('/metrics')) {
        return new Response(
          JSON.stringify({
            chats: 1,
            chats_completed: 1,
            chats_paused: 0,
            chats_rag: 1,
            chats_refused: 0,
            http_requests: 3,
            http_errors: 0,
            tool_calls: 0,
            approvals_approved: 0,
            approvals_rejected: 0,
            prompt_tokens: 10,
            completion_tokens: 4,
            llm: { count: 1, avg_ms: 12, p50_ms: 12, p95_ms: 12, max_ms: 12 },
            retrieval: { count: 1, avg_ms: 3, p50_ms: 3, p95_ms: 3, max_ms: 3 },
            citation_rate_avg: 1,
            groundedness_avg: 0.9,
            tools: {},
            routes: { 'GET /metrics': 1 },
          }),
          { status: 200 },
        )
      }
      expect(url).toBe('http://api.test/eval/run')
      expect(init?.method).toBe('POST')
      return new Response(
        JSON.stringify({
          ran_at: '2026-10-27T16:00:00+00:00',
          total: 6,
          passed: 6,
          failed: 0,
          duration_ms: 20,
          cases: [],
        }),
        { status: 200 },
      )
    })
    const client = createClient({ baseUrl: 'http://api.test', fetch: fetchMock })
    const metrics = await client.getMetrics()
    expect(metrics.chats).toBe(1)
    const report = await client.runEval()
    expect(report.passed).toBe(6)
  })

  it('uploads with multipart and no forced JSON content-type', async () => {
    const fetchMock = vi.fn<typeof fetch>(async (_input, init) => {
      const headers = new Headers(init?.headers)
      expect(headers.get('Content-Type')).toBeNull()
      expect(init?.body).toBeInstanceOf(FormData)
      return new Response(
        JSON.stringify({
          id: '1',
          name: 'notes.txt',
          content_type: 'text/plain',
          size_bytes: 4,
          status: 'ready',
          chunk_count: 1,
          page_count: null,
          error: null,
          created_at: '2026-01-01T00:00:00Z',
          updated_at: '2026-01-01T00:00:00Z',
        }),
        { status: 201 },
      )
    })
    const client = createClient({ baseUrl: 'http://api.test', fetch: fetchMock })
    const record = await client.uploadDocument(new File(['hi\n'], 'notes.txt', { type: 'text/plain' }))
    expect(record.status).toBe('ready')
  })

  it('treats an empty latest eval as undefined, not an error', async () => {
    const client = createClient({
      baseUrl: 'http://api.test',
      fetch: async () => new Response(null, { status: 204 }),
    })
    await expect(client.getLatestEval()).resolves.toBeUndefined()
  })

  it('turns a refused connection into ApiError', async () => {
    const client = createClient({
      baseUrl: 'http://api.test',
      fetch: async () => {
        throw new TypeError('Failed to fetch')
      },
    })
    await expect(client.getHealth()).rejects.toMatchObject({
      name: 'ApiError',
      status: 0,
    })
  })
})
