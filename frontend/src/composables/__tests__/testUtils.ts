import { vi } from 'vitest'

import type { Document, DocumentListResponse } from '@/types/api'

// Mirrors the baseUrl computed in services/api.ts so tests can assert exact request URLs.
const baseUrl = (import.meta.env.VITE_API_BASE_URL ?? '').replace(/\/+$/, '')

export function apiUrl(path: string): string {
  return `${baseUrl}${path}`
}

export function jsonResponse(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { 'Content-Type': 'application/json' },
  })
}

// 204 No Content: DELETE success has no body, and services/api.ts skips reading it.
export function noContentResponse(): Response {
  return new Response(null, { status: 204 })
}

// Error envelope expected by services/api.ts: {"error": {"code", "message"}} (docs/api.md).
export function errorResponse(status: number, code: string, message: string): Response {
  return jsonResponse({ error: { code, message } }, status)
}

export function makeDocument(id: string, overrides: Partial<Document> = {}): Document {
  return {
    id,
    filename: `${id}.pdf`,
    status: 'ready',
    error_code: null,
    error_message: null,
    page_count: 10,
    chunk_count: 20,
    created_at: '2026-01-01T12:00:00Z',
    updated_at: '2026-01-01T12:00:00Z',
    ...overrides,
  }
}

export function listResponse(items: Document[], embeddingModelChanged = false): Response {
  const body: DocumentListResponse = { items, embedding_model_changed: embeddingModelChanged }
  return jsonResponse(body)
}

// Lets a test hold a request open and resolve it later (in-flight states, ignored sends).
export function pendingResponse(): {
  response: Promise<Response>
  resolve: (value: Response) => void
} {
  let resolveValue!: (value: Response) => void
  const response = new Promise<Response>((resolve) => {
    resolveValue = resolve
  })
  return { response, resolve: resolveValue }
}

export type FetchQueueItem = Response | Error | Promise<Response>

// Stubs the global fetch with a queue of responses, one per request. An Error entry rejects
// the request (network failure); a Promise entry resolves when the test decides. Any call
// beyond the queue rejects, so unexpected requests fail the call-count assertions.
export function stubFetchResponses(queue: FetchQueueItem[]) {
  const pending = [...queue]
  const fetchMock = vi.fn((...args: Parameters<typeof fetch>): Promise<Response> => {
    const next = pending.shift()
    if (next === undefined) {
      return Promise.reject(new Error(`unexpected extra fetch call: ${String(args[0])}`))
    }
    if (next instanceof Error) {
      return Promise.reject(next)
    }
    return Promise.resolve(next)
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

// One SSE event block exactly as the backend sends it (PRD §12.6): a `data:` line with the
// JSON payload, framed by the blank line that ends an event.
export function sseEvent(payload: Record<string, unknown>): string {
  return `data: ${JSON.stringify(payload)}\n\n`
}

// A network chunk of the stream body: text encoded to UTF-8, or raw bytes when a test needs
// to cut a multi-byte character in half.
export type SseChunk = string | Uint8Array

const encoder = new TextEncoder()

function encodeChunk(chunk: SseChunk): Uint8Array {
  return typeof chunk === 'string' ? encoder.encode(chunk) : chunk
}

const SSE_HEADERS = {
  'Content-Type': 'text/event-stream',
  'Cache-Control': 'no-cache',
}

// An SSE response fully known up front: every chunk is enqueued and the stream closes, so
// the real streamChat in services/api.ts consumes it with its own reader/decoder.
export function sseResponse(chunks: SseChunk[]): Response {
  return new Response(
    new ReadableStream<Uint8Array>({
      start(controller) {
        for (const chunk of chunks) controller.enqueue(encodeChunk(chunk))
        controller.close()
      },
    }),
    { status: 200, headers: SSE_HEADERS },
  )
}

// An SSE response the test controls chunk by chunk: the initial chunks are delivered, then
// the stream stays open until the test pushes more, closes it (a clean end) or errors it
// (a network failure or an aborted fetch mid-stream).
export function pendingSseResponse(chunks: SseChunk[]): {
  response: Response
  push: (chunk: SseChunk) => void
  close: () => void
  error: (reason?: unknown) => void
} {
  let controller!: ReadableStreamDefaultController<Uint8Array>
  const body = new ReadableStream<Uint8Array>({
    start(c) {
      controller = c
      for (const chunk of chunks) c.enqueue(encodeChunk(chunk))
    },
  })
  return {
    response: new Response(body, { status: 200, headers: SSE_HEADERS }),
    push: (chunk: SseChunk) => controller.enqueue(encodeChunk(chunk)),
    close: () => controller.close(),
    error: (reason?: unknown) => controller.error(reason),
  }
}
