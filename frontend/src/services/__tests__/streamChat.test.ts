import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  apiUrl,
  errorResponse,
  pendingSseResponse,
  sseEvent,
  sseResponse,
  stubFetchResponses,
} from '@/composables/__tests__/testUtils'
import {
  ApiError,
  STREAM_ABORTED,
  StreamAbortedError,
  streamChat,
  UNEXPECTED_RESPONSE,
} from '@/services/api'
import type { StreamOptions } from '@/services/api'
import type { ChatStreamRequest } from '@/types/api'

const payload: ChatStreamRequest = {
  question: 'Como reinicializar o equipamento?',
  document_ids: ['doc-1'],
  show_sources: false,
}

// StreamOptions that record every callback call, so assertions can check order and count.
function recordingOptions(): { options: StreamOptions; deltas: string[]; done: boolean[] } {
  const deltas: string[] = []
  const done: boolean[] = []
  return {
    deltas,
    done,
    options: {
      onDelta: (text: string) => {
        deltas.push(text)
      },
      onDone: (hasEvidence: boolean) => {
        done.push(hasEvidence)
      },
    },
  }
}

// Awaits the promise and returns what it rejected with; an Error marker when it resolved,
// so a missing rejection fails the instanceof assertions below.
async function rejection(promise: Promise<void>): Promise<unknown> {
  try {
    await promise
    return new Error('expected the promise to reject, but it resolved')
  } catch (error) {
    return error
  }
}

// SSE parser of POST /chat/query/stream (PRD §12.6): buffering across network chunks,
// UTF-8 reassembly, strict delta/done/error dispatch and pre-stream error envelopes.
describe('streamChat', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('entrega cada delta na ordem e o done exatamente uma vez', async () => {
    const fetchMock = stubFetchResponses([
      sseResponse([
        sseEvent({ type: 'delta', text: 'Desligue o equipamento' }),
        sseEvent({ type: 'delta', text: ' e aguarde 30 segundos.' }),
        sseEvent({ type: 'done', has_evidence: true }),
      ]),
    ])
    const { options, deltas, done } = recordingOptions()

    await streamChat(payload, options)

    expect(deltas).toEqual(['Desligue o equipamento', ' e aguarde 30 segundos.'])
    expect(done).toEqual([true])

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0]?.[0]).toBe(apiUrl('/chat/query/stream'))
    const init = fetchMock.mock.calls[0]?.[1]
    expect(init?.method).toBe('POST')
    expect(init?.headers).toEqual({
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    })
    expect(JSON.parse(String(init?.body))).toEqual(payload)
  })

  it('remonta um evento dividido entre chunks de rede', async () => {
    const event = sseEvent({ type: 'delta', text: 'Desligue o equipamento e aguarde 30 segundos' })
    const cut = Math.floor(event.length / 2)
    stubFetchResponses([
      sseResponse([
        event.slice(0, cut), // cuts in the middle of the JSON payload
        event.slice(cut),
        sseEvent({ type: 'done', has_evidence: false }),
      ]),
    ])
    const { options, deltas, done } = recordingOptions()

    await streamChat(payload, options)

    expect(deltas).toEqual(['Desligue o equipamento e aguarde 30 segundos'])
    expect(done).toEqual([false])
  })

  it('decodifica um caractere UTF-8 multibyte dividido entre chunks', async () => {
    const text = 'Reinicialize 🔄 o equipamento'
    const event = sseEvent({ type: 'delta', text })
    const bytes = new TextEncoder().encode(event)
    // Byte offset that lands inside the 4-byte emoji: the first chunk ends with an
    // incomplete sequence, which the decoder must hold until the next chunk completes it.
    const emojiStart = new TextEncoder().encode(event.slice(0, event.indexOf('🔄'))).length
    stubFetchResponses([
      sseResponse([
        bytes.slice(0, emojiStart + 1),
        bytes.slice(emojiStart + 1),
        sseEvent({ type: 'done', has_evidence: true }),
      ]),
    ])
    const { options, deltas, done } = recordingOptions()

    await streamChat(payload, options)

    // The emoji arrives whole: no replacement character from a bad split.
    expect(deltas).toEqual([text])
    expect(done).toEqual([true])
  })

  it('evento de erro no meio do stream rejeita com o código e a mensagem do envelope', async () => {
    stubFetchResponses([
      sseResponse([
        sseEvent({ type: 'delta', text: 'Parcial' }),
        sseEvent({
          type: 'error',
          error: {
            code: 'provider_error',
            message: 'O serviço de IA não respondeu corretamente. Tente novamente.',
          },
        }),
      ]),
    ])
    const { options, deltas, done } = recordingOptions()

    const caught = await rejection(streamChat(payload, options))

    expect(caught).toBeInstanceOf(ApiError)
    const apiError = caught as ApiError
    expect(apiError.code).toBe('provider_error')
    expect(apiError.message).toBe('O serviço de IA não respondeu corretamente. Tente novamente.')
    // The 200 was already committed when the stream started (PRD §12.6).
    expect(apiError.status).toBe(200)
    // Deltas delivered before the failure stay delivered.
    expect(deltas).toEqual(['Parcial'])
    expect(done).toEqual([])
  })

  it('erro antes do stream chega como JSON com o status HTTP real', async () => {
    stubFetchResponses([
      errorResponse(422, 'stream_sources_unsupported', 'Esta rota sempre responde sem fontes.'),
    ])
    const { options, deltas, done } = recordingOptions()

    const caught = await rejection(streamChat(payload, options))

    expect(caught).toBeInstanceOf(ApiError)
    const apiError = caught as ApiError
    expect(apiError.code).toBe('stream_sources_unsupported')
    expect(apiError.message).toBe('Esta rota sempre responde sem fontes.')
    expect(apiError.status).toBe(422)
    expect(deltas).toEqual([])
    expect(done).toEqual([])
  })

  it('stream que termina sem done rejeita com unexpected_response', async () => {
    stubFetchResponses([sseResponse([sseEvent({ type: 'delta', text: 'Só o delta' })])])
    const { options, deltas, done } = recordingOptions()

    const caught = await rejection(streamChat(payload, options))

    expect(caught).toBeInstanceOf(ApiError)
    const apiError = caught as ApiError
    expect(apiError.code).toBe(UNEXPECTED_RESPONSE)
    expect(apiError.status).toBe(200)
    expect(deltas).toEqual(['Só o delta'])
    expect(done).toEqual([])
  })

  it('interrupção via signal rejeita com StreamAbortedError', async () => {
    const stream = pendingSseResponse([sseEvent({ type: 'delta', text: 'Parcial ' })])
    stubFetchResponses([stream.response])
    const controller = new AbortController()
    const { options, deltas } = recordingOptions()

    const promise = streamChat(payload, { ...options, signal: controller.signal })
    await vi.waitFor(() => {
      expect(deltas).toEqual(['Parcial '])
    })

    controller.abort()
    // The aborted fetch rejects the pending read (Parar, RF-23).
    stream.error(new DOMException('This operation was aborted', 'AbortError'))

    const caught = await rejection(promise)

    expect(caught).toBeInstanceOf(StreamAbortedError)
    const aborted = caught as StreamAbortedError
    expect(aborted.code).toBe(STREAM_ABORTED)
    expect(deltas).toEqual(['Parcial '])
  })
})
