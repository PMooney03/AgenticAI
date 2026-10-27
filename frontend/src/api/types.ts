export type DocumentStatus = 'processing' | 'ready' | 'failed'
export type ChatMode = 'rag' | 'chat'
export type HealthStatus = 'ok' | 'degraded'

export interface DocumentRecord {
  id: string
  name: string
  content_type: string
  size_bytes: number
  status: DocumentStatus
  chunk_count: number
  page_count: number | null
  error: string | null
  created_at: string
  updated_at: string
}

export interface DocumentListResponse {
  documents: DocumentRecord[]
  total: number
}

export interface Source {
  label: number
  document_id: string
  document_name: string
  page: number | null
  score: number
  snippet: string
  cited: boolean
}

export interface RetrievalStats {
  retrieved_chunks: number
  retrieval_ms: number
  cited_sources: number
}

export interface ChatResponse {
  answer: string
  mode: ChatMode
  model: string
  prompt_version: string
  request_id: string
  latency_ms: number
  sources: Source[]
  retrieval: RetrievalStats | null
  prompt_tokens: number | null
  completion_tokens: number | null
}

export interface HistoryTurn {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatRequest {
  message: string
  history: HistoryTurn[]
  use_documents: boolean
  top_k?: number
}

export interface HealthResponse {
  status: HealthStatus
  app: string
  version: string
  ollama: { reachable: boolean; model: string; base_url: string }
  embeddings: { reachable: boolean; model: string }
  qdrant: { reachable: boolean; url: string; collection: string; chunks: number | null }
  documents_ready: number
}

export class ApiError extends Error {
  readonly status: number
  readonly requestId: string | null

  constructor(status: number, detail: string, requestId: string | null) {
    super(detail)
    this.name = 'ApiError'
    this.status = status
    this.requestId = requestId
  }
}
