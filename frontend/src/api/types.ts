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

export interface QualityStats {
  citation_rate: number | null
  groundedness: number | null
  refused: boolean
}

export interface LatencyStats {
  count: number
  avg_ms: number | null
  p50_ms: number | null
  p95_ms: number | null
  max_ms: number | null
}

export interface MetricsSnapshot {
  chats: number
  chats_completed: number
  chats_paused: number
  chats_rag: number
  chats_refused: number
  http_requests: number
  http_errors: number
  tool_calls: number
  approvals_approved: number
  approvals_rejected: number
  prompt_tokens: number
  completion_tokens: number
  llm: LatencyStats
  retrieval: LatencyStats
  citation_rate_avg: number | null
  groundedness_avg: number | null
  tools: Record<string, number>
  routes: Record<string, number>
}

export interface EvalCaseResult {
  id: string
  passed: boolean
  checks: Record<string, boolean>
  failures: string[]
  nodes_visited: string[]
  tools: string[]
  retrieved_chunks: number
  cited_sources: number
  citation_rate: number | null
  groundedness: number | null
  refused: boolean
  pending: boolean
  llm_ms: number
}

export interface EvalReport {
  ran_at: string
  total: number
  passed: number
  failed: number
  duration_ms: number
  cases: EvalCaseResult[]
}

export interface WorkflowEvent {
  id: string
  node: string
  label: string
  done: boolean
}

export interface PendingApproval {
  tool: string
  description: string
  preview: string
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
  quality: QualityStats | null
  workflow: WorkflowEvent[]
  pending_approval: PendingApproval | null
}

export interface ToolInfo {
  name: string
  description: string
  read_only: boolean
  requires_approval: boolean
  source: 'mcp'
}

export interface ToolListResponse {
  tools: ToolInfo[]
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
