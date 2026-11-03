import { ptBR } from '@/locales/pt-BR'
import type { ErrorResponse, HealthResponse } from '@/types/api'

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
