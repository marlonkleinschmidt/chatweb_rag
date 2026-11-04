import { ptBR } from '@/locales/pt-BR'
import type {
  ChatRequest,
  ChatResponse,
  ChatStreamRequest,
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

// A stream interrupted by the caller (Parar, RF-23): a dedicated type so useChat can treat
// it as "stopped" — partial text kept, no error entry — instead of a failed request.
export const STREAM_ABORTED = 'stream_aborted'

export class StreamAbortedError extends ApiError {
  constructor() {
    // The message is never displayed: callers handle the abort, not the error.
    super(STREAM_ABORTED, ptBR.errors.unexpected, null)
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

// Callbacks plus the abort signal of a streamed query (PRD §12.6).
export interface StreamOptions {
  onDelta: (text: string) => void
  onDone: (hasEvidence: boolean) => void
  signal?: AbortSignal
}

// A fetch/read failure is a network error, unless the caller aborted (RF-23): the abort gets
// a dedicated error type so the caller can keep the partial answer without showing an error.
function streamFailure(error: unknown, signal: AbortSignal | undefined): ApiError {
  if (signal?.aborted || (error instanceof DOMException && error.name === 'AbortError')) {
    return new StreamAbortedError()
  }
  return new ApiError(NETWORK_ERROR, ptBR.errors.network, null)
}

// Extracts the `data` payload of one SSE event block (lines separated by \n): comment lines
// and other fields are ignored; multiple data lines are joined per the SSE format. Returns
// null when the block carries no data at all.
function sseData(block: string): string | null {
  const dataLines: string[] = []
  for (const line of block.split('\n')) {
    if (line === '' || line.startsWith(':')) continue
    const colon = line.indexOf(':')
    const field = colon === -1 ? line : line.slice(0, colon)
    if (field !== 'data') continue
    const value = colon === -1 ? '' : line.slice(colon + 1)
    dataLines.push(value.startsWith(' ') ? value.slice(1) : value)
  }
  return dataLines.length > 0 ? dataLines.join('\n') : null
}

// Streams the answer without sources (POST /chat/query/stream, PRD §12.6). Deltas are
// delivered through onDelta as they arrive; onDone fires exactly once, when the `done`
// event arrives. Rejects with ApiError — the API envelope (JSON before the stream starts,
// or an `error` event during it), NETWORK_ERROR, or UNEXPECTED_RESPONSE — and with
// StreamAbortedError when the caller aborted via the signal.
export async function streamChat(
  payload: ChatStreamRequest,
  options: StreamOptions,
): Promise<void> {
  if (!baseUrl) {
    throw new ApiError(CONFIG_MISSING, ptBR.errors.configMissing, null)
  }

  let response: Response
  try {
    response = await fetch(`${baseUrl}/chat/query/stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Accept: 'text/event-stream' },
      body: JSON.stringify(payload),
      signal: options.signal,
    })
  } catch (error) {
    throw streamFailure(error, options.signal)
  }

  if (!response.ok) {
    // Errors detected before the stream starts arrive as a JSON error envelope with the
    // real HTTP status (422/409/502/504).
    const body = await readJson(response)
    if (isErrorResponse(body)) {
      throw new ApiError(body.error.code, body.error.message, response.status)
    }
    throw new ApiError(UNEXPECTED_RESPONSE, ptBR.errors.unexpected, response.status)
  }

  const mediaType = (response.headers.get('Content-Type') ?? '').split(';')[0]?.trim().toLowerCase()
  if (mediaType !== 'text/event-stream') {
    throw new ApiError(UNEXPECTED_RESPONSE, ptBR.errors.unexpected, response.status)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new ApiError(UNEXPECTED_RESPONSE, ptBR.errors.unexpected, response.status)
  }

  // `done` must arrive exactly once, as the last event (PRD §12.6); anything after it and
  // a stream that ends without it are both unexpected.
  let doneReceived = false

  function unexpected(): ApiError {
    return new ApiError(UNEXPECTED_RESPONSE, ptBR.errors.unexpected, response.status)
  }

  function handleData(data: string): void {
    if (doneReceived) return
    let event: unknown
    try {
      event = JSON.parse(data)
    } catch {
      throw unexpected()
    }
    if (typeof event !== 'object' || event === null || !('type' in event)) throw unexpected()
    if (event.type === 'delta' && 'text' in event && typeof event.text === 'string') {
      options.onDelta(event.text)
      return
    }
    if (
      event.type === 'done' &&
      'has_evidence' in event &&
      typeof event.has_evidence === 'boolean'
    ) {
      doneReceived = true
      options.onDone(event.has_evidence)
      return
    }
    if (event.type === 'error' && isErrorResponse(event)) {
      // The 200 was already committed when the stream started: only the envelope travels.
      throw new ApiError(event.error.code, event.error.message, response.status)
    }
    throw unexpected()
  }

  // Events are framed by a blank line; a block may arrive split across network chunks, and
  // multi-byte UTF-8 characters may be split too — the decoder stays in stream mode until
  // the final flush so both are reassembled.
  const decoder = new TextDecoder()
  let buffer = ''

  function drainBuffer(): void {
    let separator = buffer.indexOf('\n\n')
    while (separator !== -1) {
      const block = buffer.slice(0, separator)
      buffer = buffer.slice(separator + 2)
      const data = sseData(block)
      if (data !== null) handleData(data)
      separator = buffer.indexOf('\n\n')
    }
  }

  try {
    for (;;) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      drainBuffer()
    }
    // Flushes any pending multi-byte character and dispatches a trailing event block that
    // was not followed by a blank line before the stream ended.
    buffer += decoder.decode()
    const trailing = sseData(buffer)
    if (trailing !== null) handleData(trailing)
    if (!doneReceived) throw unexpected()
  } catch (error) {
    // Releases the connection so a broken stream does not stay open; cancel may itself fail
    // when the fetch was aborted or the connection dropped, which is ignored.
    void reader.cancel().catch(() => {})
    if (error instanceof ApiError) throw error
    throw streamFailure(error, options.signal)
  }
}
