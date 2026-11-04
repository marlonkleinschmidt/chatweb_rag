// Mirrors the backend Pydantic schemas (PRD §5.1 and §5.3).

export type DocumentStatus = 'received' | 'processing' | 'ready' | 'failed'

export interface Document {
  id: string
  filename: string
  status: DocumentStatus
  error_code: string | null
  error_message: string | null
  page_count: number | null
  chunk_count: number | null
  created_at: string
  updated_at: string
}

// `POST /documents` only: `warning` is set when the same file was already sent (RF-01).
export interface DocumentUploadResponse extends Document {
  warning: string | null
}

export interface DocumentListResponse {
  items: Document[]
  // True when stored vectors were made with another embedding model (PRD §8.3).
  embedding_model_changed: boolean
}

// One previous message of the conversation (PRD §13.6), in chronological order.
export interface ChatHistoryMessage {
  role: 'user' | 'assistant'
  content: string
}

export interface ChatRequest {
  question: string
  document_ids: string[]
  // Sent explicitly on every query (PRD §12.6): true keeps the [n] markers and sources;
  // false returns a continuous answer with sources: [].
  show_sources: boolean
  // Optional (PRD §13.6): omitted or [] keeps the behaviour without history. Over
  // 2 × MAX_HISTORY_TURNS messages or MAX_HISTORY_CHARS characters → 422 history_invalid.
  history?: ChatHistoryMessage[]
}

// Body of POST /chat/query/stream (PRD §12.6): the route always answers without sources,
// so `show_sources` can only be false — sending `true` returns 422 stream_sources_unsupported.
export interface ChatStreamRequest {
  question: string
  document_ids: string[]
  show_sources: false
  // Same optional history and limits as ChatRequest (inherited by the backend schema).
  history?: ChatHistoryMessage[]
}

export interface Source {
  index: number
  document_id: string
  filename: string
  page: number | null
  excerpt: string
}

export interface ChatResponse {
  answer: string
  has_evidence: boolean
  sources: Source[]
}

export interface HealthResponse {
  status: 'ok'
}

export interface ErrorDetail {
  code: string
  message: string
}

export interface ErrorResponse {
  error: ErrorDetail
}
