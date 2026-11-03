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
