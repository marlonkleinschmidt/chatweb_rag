import { afterEach, describe, expect, it, vi } from 'vitest'

import { useChat } from '@/composables/useChat'
import { ptBR } from '@/locales/pt-BR'
import type { Source } from '@/types/api'

import {
  apiUrl,
  errorResponse,
  jsonResponse,
  pendingSseResponse,
  sseEvent,
  sseResponse,
  stubFetchResponses,
} from './testUtils'

// Streaming mode (show sources off, PRD §12): POST /chat/query/stream. The JSON mode lives
// in useChat.test.ts; this suite covers only the streaming path and how both modes share
// the same session without changing past entries.
describe('useChat no modo streaming', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('acumula os deltas numa única entrada do assistente, em markdown e sem fontes', async () => {
    const stream = pendingSseResponse([])
    const fetchMock = stubFetchResponses([stream.response])
    const store = useChat()

    const sending = store.send('Como reinicializar o equipamento?', ['doc-1'], false)
    await vi.waitFor(() => {
      // The assistant entry is born empty right after the user entry (RF-22).
      expect(store.entries).toHaveLength(2)
    })
    expect(store.entries[1]).toEqual({
      id: 2,
      role: 'assistant',
      content: '',
      sources: [],
      markdown: true,
    })

    stream.push(sseEvent({ type: 'delta', text: 'Desligue o equipamento' }))
    await vi.waitFor(() => {
      expect(store.entries[1]).toMatchObject({ content: 'Desligue o equipamento' })
    })
    stream.push(sseEvent({ type: 'delta', text: ' e aguarde 30 segundos' }))
    await vi.waitFor(() => {
      expect(store.entries[1]).toMatchObject({
        content: 'Desligue o equipamento e aguarde 30 segundos',
      })
    })
    // Still the same single entry: each delta grows it in place instead of appending.
    expect(store.entries).toHaveLength(2)

    stream.push(sseEvent({ type: 'done', has_evidence: true }))
    stream.close()

    expect(await sending).toBe(true)
    expect(store.generating).toBe(false)
    expect(store.entries).toEqual([
      { id: 1, role: 'user', content: 'Como reinicializar o equipamento?' },
      {
        id: 2,
        role: 'assistant',
        content: 'Desligue o equipamento e aguarde 30 segundos',
        sources: [],
        markdown: true,
      },
    ])

    // Only the question and the selection travel, with sources explicitly off: no history.
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0]?.[0]).toBe(apiUrl('/chat/query/stream'))
    const init = fetchMock.mock.calls[0]?.[1]
    expect(init?.method).toBe('POST')
    expect(init?.headers).toEqual({
      'Content-Type': 'application/json',
      Accept: 'text/event-stream',
    })
    expect(JSON.parse(String(init?.body))).toEqual({
      question: 'Como reinicializar o equipamento?',
      document_ids: ['doc-1'],
      show_sources: false,
    })
  })

  it('Parar interrompe o stream, mantém o parcial e não cria entrada de erro', async () => {
    const stream = pendingSseResponse([sseEvent({ type: 'delta', text: 'Desligue o ' })])
    stubFetchResponses([
      stream.response,
      sseResponse([
        sseEvent({ type: 'delta', text: 'Segunda resposta.' }),
        sseEvent({ type: 'done', has_evidence: true }),
      ]),
    ])
    const store = useChat()

    const first = store.send('Como reinicializar?', ['doc-1'], false)
    await vi.waitFor(() => {
      expect(store.entries[1]).toMatchObject({ role: 'assistant', content: 'Desligue o ' })
    })

    store.stop()
    // The aborted fetch rejects the pending read; the partial text stays (RF-23).
    stream.error(new DOMException('This operation was aborted', 'AbortError'))

    expect(await first).toBe(true)
    expect(store.generating).toBe(false)
    expect(store.entries).toEqual([
      { id: 1, role: 'user', content: 'Como reinicializar?' },
      { id: 2, role: 'assistant', content: 'Desligue o ', sources: [], markdown: true },
    ])

    // After Parar a new send is accepted immediately (RF-23).
    expect(await store.send('Outra pergunta', ['doc-1'], false)).toBe(true)
    expect(store.entries[3]).toEqual({
      id: 4,
      role: 'assistant',
      content: 'Segunda resposta.',
      sources: [],
      markdown: true,
    })
  })

  it('erro no meio do stream mantém o parcial e acrescenta entrada com a mensagem do envelope', async () => {
    stubFetchResponses([
      sseResponse([
        sseEvent({ type: 'delta', text: 'Parcial que chegou antes da falha' }),
        sseEvent({
          type: 'error',
          error: {
            code: 'provider_error',
            message: 'O serviço de IA não respondeu corretamente. Tente novamente.',
          },
        }),
      ]),
    ])
    const store = useChat()

    const result = await store.send('Pergunta qualquer', ['doc-1'], false)

    expect(result).toBe(false)
    expect(store.generating).toBe(false)
    expect(store.entries).toEqual([
      { id: 1, role: 'user', content: 'Pergunta qualquer' },
      {
        id: 2,
        role: 'assistant',
        content: 'Parcial que chegou antes da falha',
        sources: [],
        markdown: true,
      },
      {
        id: 3,
        role: 'error',
        content: 'O serviço de IA não respondeu corretamente. Tente novamente.',
      },
    ])
  })

  // 7.27: a failure before the first delta must not leave an empty assistant bubble, which
  // the screen reader would announce as "Assistente:" with no content.
  it.each([
    {
      name: 'erro de rede',
      failure: (): Response | Error => new TypeError('Failed to fetch'),
      message: ptBR.errors.network,
    },
    {
      name: 'HTTP 409',
      failure: (): Response | Error =>
        errorResponse(409, 'document_not_ready', 'Um dos documentos ainda não está pronto.'),
      message: 'Um dos documentos ainda não está pronto.',
    },
    {
      name: 'HTTP 504',
      failure: (): Response | Error =>
        errorResponse(504, 'provider_timeout', 'O serviço de IA demorou para responder.'),
      message: 'O serviço de IA demorou para responder.',
    },
    {
      name: 'evento de erro antes do primeiro delta',
      failure: (): Response | Error =>
        sseResponse([
          sseEvent({
            type: 'error',
            error: { code: 'provider_error', message: 'O serviço de IA não respondeu.' },
          }),
        ]),
      message: 'O serviço de IA não respondeu.',
    },
  ])('$name antes do primeiro delta não deixa bolha vazia do assistente', async (scenario) => {
    stubFetchResponses([scenario.failure()])
    const store = useChat()

    const result = await store.send('Pergunta qualquer', ['doc-1'], false)

    expect(result).toBe(false)
    expect(store.generating).toBe(false)
    // Only the question and the error remain: the empty assistant entry (id 2) was dropped.
    expect(store.entries).toEqual([
      { id: 1, role: 'user', content: 'Pergunta qualquer' },
      { id: 3, role: 'error', content: scenario.message },
    ])
  })

  it('Parar antes do primeiro delta remove a bolha vazia e não cria entrada de erro', async () => {
    const stream = pendingSseResponse([])
    stubFetchResponses([stream.response])
    const store = useChat()

    const sending = store.send('Como reinicializar?', ['doc-1'], false)
    await vi.waitFor(() => {
      expect(store.entries).toHaveLength(2)
    })

    store.stop()
    stream.error(new DOMException('This operation was aborted', 'AbortError'))

    expect(await sending).toBe(true)
    expect(store.generating).toBe(false)
    expect(store.entries).toEqual([{ id: 1, role: 'user', content: 'Como reinicializar?' }])
  })

  it('mudar o modo não altera as entradas anteriores da conversa', async () => {
    const sources: Source[] = [
      { index: 1, document_id: 'doc-1', filename: 'doc-1.pdf', page: 2, excerpt: 'Trecho citado.' },
    ]
    stubFetchResponses([
      jsonResponse({
        answer: 'Afirmação apoiada no documento [1].',
        has_evidence: true,
        sources,
      }),
      sseResponse([
        sseEvent({ type: 'delta', text: 'Resposta em texto corrido.' }),
        sseEvent({ type: 'done', has_evidence: true }),
      ]),
    ])
    const store = useChat()

    // Default showSources keeps the JSON path exactly as today (RF-20/RF-24).
    expect(await store.send('Pergunta com fontes', ['doc-1'])).toBe(true)
    expect(await store.send('Pergunta sem fontes', ['doc-1'], false)).toBe(true)

    expect(store.entries).toEqual([
      { id: 1, role: 'user', content: 'Pergunta com fontes' },
      {
        id: 2,
        role: 'assistant',
        content: 'Afirmação apoiada no documento [1].',
        sources,
        markdown: false,
      },
      { id: 3, role: 'user', content: 'Pergunta sem fontes' },
      {
        id: 4,
        role: 'assistant',
        content: 'Resposta em texto corrido.',
        sources: [],
        markdown: true,
      },
    ])
  })
})
