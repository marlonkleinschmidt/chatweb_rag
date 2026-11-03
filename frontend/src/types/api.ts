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

export interface ChatRequest {
  question: string
  document_ids: string[]
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
