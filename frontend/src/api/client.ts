import { ApiError } from './types'
import type {
  ChatRequest,
  ChatResponse,
  DocumentListResponse,
  DocumentRecord,
  EvalReport,
  HealthResponse,
  MetricsSnapshot,
  ToolListResponse,
} from './types'

export { ApiError } from './types'

const DEFAULT_BASE_URL = 'http://localhost:8000'
const MAX_HISTORY_TURNS = 20

export function apiBaseUrl(): string {
  const configured = import.meta.env.VITE_API_BASE_URL
  return (configured ?? DEFAULT_BASE_URL).replace(/\/$/, '')
}

export function newRequestId(): string {
  return crypto.randomUUID().replaceAll('-', '')
}

export function trimHistory(history: ChatRequest['history']): ChatRequest['history'] {
  if (history.length <= MAX_HISTORY_TURNS) {
    return history
  }
  return history.slice(-MAX_HISTORY_TURNS)
}

export function parseApiErrorBody(status: number, body: string, requestId: string | null): ApiError {
  let detail = `Request failed (${status}).`
  try {
    const parsed = JSON.parse(body) as { detail?: unknown; request_id?: string }
    if (typeof parsed.detail === 'string' && parsed.detail.trim()) {
      detail = parsed.detail
    }
    if (typeof parsed.request_id === 'string' && parsed.request_id) {
      requestId = parsed.request_id
    }
  } catch {
    if (body.trim()) {
      detail = body.trim().slice(0, 400)
    }
  }
  return new ApiError(status, detail, requestId)
}

export interface ClientOptions {
  baseUrl?: string
  fetch?: typeof fetch
}

export function createClient(options: ClientOptions = {}) {
  const baseUrl = (options.baseUrl ?? apiBaseUrl()).replace(/\/$/, '')
  const http = options.fetch ?? fetch

  async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const requestId = newRequestId()
    const headers = new Headers(init.headers)
    headers.set('X-Request-ID', requestId)
    if (init.body && !(init.body instanceof FormData) && !headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }

    let response: Response
    try {
      response = await http(`${baseUrl}${path}`, { ...init, headers })
    } catch (error) {
      const reason = error instanceof Error ? error.message : 'network error'
      throw new ApiError(0, `Cannot reach the API at ${baseUrl} (${reason}).`, requestId)
    }

    const echoedId = response.headers.get('X-Request-ID') ?? requestId
    if (response.status === 204) {
      return undefined as T
    }
    const text = await response.text()
    if (!response.ok) {
      throw parseApiErrorBody(response.status, text, echoedId)
    }
    return text ? (JSON.parse(text) as T) : (undefined as T)
  }

  return {
    baseUrl,
    getHealth: () => request<HealthResponse>('/health'),
    listDocuments: () => request<DocumentListResponse>('/documents'),
    uploadDocument: (file: File) => {
      const form = new FormData()
      form.append('file', file)
      return request<DocumentRecord>('/documents/upload', { method: 'POST', body: form })
    },
    deleteDocument: (id: string) =>
      request<void>(`/documents/${encodeURIComponent(id)}`, { method: 'DELETE' }),
    chat: (payload: ChatRequest) =>
      request<ChatResponse>('/chat', {
        method: 'POST',
        body: JSON.stringify({
          ...payload,
          history: trimHistory(payload.history),
        }),
      }),
    listTools: () => request<ToolListResponse>('/agent/tools'),
    decideRun: (requestId: string, approved: boolean) =>
      request<ChatResponse>(`/agent/runs/${encodeURIComponent(requestId)}/decision`, {
        method: 'POST',
        body: JSON.stringify({ approved }),
      }),
    getMetrics: () => request<MetricsSnapshot>('/metrics'),
    runEval: () => request<EvalReport>('/eval/run', { method: 'POST' }),
    getLatestEval: () => request<EvalReport | undefined>('/eval/latest'),
  }
}

export const api = createClient()
