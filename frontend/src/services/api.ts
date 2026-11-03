import { ptBR } from '@/locales/pt-BR'
import type {
  ChatRequest,
  ChatResponse,
  DocumentListResponse,
  DocumentUploadResponse,
  ErrorResponse,
  HealthResponse,
} from '@/types/api'

const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '')

// Error codes produced only by the frontend (the others come from the API envelope).
export const CONFIG_MISSING = 'config_missing'
export const NETWORK_ERROR = 'network_error'
export const UNEXPECTED_RESPONSE = 'unexpected_response'

export class ApiError extends Error {
  readonly code: string
  // HTTP status, or null when the request never got a response.
  readonly status: number | null

  constructor(code: string, message: string, status: number | null) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

function isErrorResponse(value: unknown): value is ErrorResponse {
  if (typeof value !== 'object' || value === null || !('error' in value)) return false
  const { error } = value
  return (
    typeof error === 'object' &&
    error !== null &&
    'code' in error &&
    typeof error.code === 'string' &&
    'message' in error &&
    typeof error.message === 'string'
  )
}

async function readJson(response: Response): Promise<unknown> {
  try {
    return await response.json()
  } catch {
    return null
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  if (!baseUrl) {
    throw new ApiError(CONFIG_MISSING, ptBR.errors.configMissing, null)
  }

  let response: Response
  try {
    response = await fetch(`${baseUrl}${path}`, {
      ...init,
      headers: { Accept: 'application/json', ...init?.headers },
    })
  } catch {
    throw new ApiError(NETWORK_ERROR, ptBR.errors.network, null)
  }

  // 204 No Content (DELETE): there is no body to read.
  if (response.status === 204) return undefined as T

  const body = await readJson(response)

  if (!response.ok) {
    if (isErrorResponse(body)) {
      throw new ApiError(body.error.code, body.error.message, response.status)
    }
    throw new ApiError(UNEXPECTED_RESPONSE, ptBR.errors.unexpected, response.status)
  }

  if (body === null) {
    throw new ApiError(UNEXPECTED_RESPONSE, ptBR.errors.unexpected, response.status)
  }
  return body as T
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health')
}

export function listDocuments(): Promise<DocumentListResponse> {
  return request<DocumentListResponse>('/documents')
}

// Multipart with the field `file`. Content-Type is left to the browser (it adds the boundary).
export function uploadDocument(file: File): Promise<DocumentUploadResponse> {
  const form = new FormData()
  form.append('file', file)
  return request<DocumentUploadResponse>('/documents', { method: 'POST', body: form })
}

export function deleteDocument(id: string): Promise<void> {
  return request<void>(`/documents/${encodeURIComponent(id)}`, { method: 'DELETE' })
}

// Each question is sent alone (no chat history), as PRD RF-15 requires.
export function queryChat(payload: ChatRequest): Promise<ChatResponse> {
  return request<ChatResponse>('/chat/query', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  })
}
