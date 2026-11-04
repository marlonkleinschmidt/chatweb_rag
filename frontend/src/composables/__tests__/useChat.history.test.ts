import { afterEach, describe, expect, it, vi } from 'vitest'

import { useChat, type HistoryLimits } from '@/composables/useChat'
import type { ChatHistoryMessage, Source } from '@/types/api'

import {
  errorResponse,
  jsonResponse,
  pendingSseResponse,
  sseEvent,
  sseResponse,
  storageMock,
  stubFetchResponses,
} from './testUtils'

// Conversation history sent with each question (Sprint 8, RF-25 and RF-28/RF-29 in useChat).
// Every scenario runs on both paths: JSON (show sources on) and streaming (show sources off).

type Mode = 'json' | 'stream'
const modes: Mode[] = ['json', 'stream']

const sources: Source[] = [
  { index: 1, document_id: 'doc-1', filename: 'crlv.pdf', page: 1, excerpt: 'Placa ABC1D23.' },
]

const limits: HistoryLimits = { maxTurns: 4, maxChars: 4000 }

// One successful answer in the given mode.
function answer(mode: Mode, text: string, hasEvidence = true): Response {
  if (mode === 'json') {
    return jsonResponse({
      answer: text,
      has_evidence: hasEvidence,
      sources: hasEvidence ? sources : [],
    })
  }
  return sseResponse([
    sseEvent({ type: 'delta', text }),
    sseEvent({ type: 'done', has_evidence: hasEvidence }),
  ])
}

type FetchMock = ReturnType<typeof stubFetchResponses>

// `history` exactly as it went in the request body of the given call.
function sentHistory(fetchMock: FetchMock, call: number): unknown {
  const body: unknown = JSON.parse(String(fetchMock.mock.calls[call]?.[1]?.body))
  return typeof body === 'object' && body !== null && 'history' in body ? body.history : undefined
}

function turn(question: string, reply: string): ChatHistoryMessage[] {
  return [
    { role: 'user', content: question },
    { role: 'assistant', content: reply },
  ]
}

describe('useChat: histórico da conversa', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it.each(modes)('%s: primeira pergunta vai com history: [] explícito', async (mode) => {
    const fetchMock = stubFetchResponses([answer(mode, 'Resposta.')])
    const store = useChat(limits)

    await store.send('Primeira pergunta', ['doc-1'], mode === 'json')

    expect(sentHistory(fetchMock, 0)).toEqual([])
  })

  it.each(modes)('%s: envia só as últimas MAX_HISTORY_TURNS trocas, em ordem', async (mode) => {
    const fetchMock = stubFetchResponses([
      answer(mode, 'Resposta 1.'),
      answer(mode, 'Resposta 2.'),
      answer(mode, 'Resposta 3.'),
      answer(mode, 'Resposta 4.'),
    ])
    const store = useChat({ maxTurns: 2, maxChars: 4000 })
    const showSources = mode === 'json'

    await store.send('Pergunta 1', ['doc-1'], showSources)
    await store.send('Pergunta 2', ['doc-1'], showSources)
    await store.send('Pergunta 3', ['doc-1'], showSources)
    await store.send('Pergunta 4', ['doc-1'], showSources)

    expect(sentHistory(fetchMock, 1)).toEqual(turn('Pergunta 1', 'Resposta 1.'))
    expect(sentHistory(fetchMock, 3)).toEqual([
      ...turn('Pergunta 2', 'Resposta 2.'),
      ...turn('Pergunta 3', 'Resposta 3.'),
    ])
  })

  it.each(modes)('%s: limite de caracteres corta as trocas mais antigas', async (mode) => {
    // Each turn has 10 + 11 = 21 characters: two fit in 50, three do not.
    const fetchMock = stubFetchResponses([
      answer(mode, 'Resposta 1.'),
      answer(mode, 'Resposta 2.'),
      answer(mode, 'Resposta 3.'),
      answer(mode, 'Resposta 4.'),
    ])
    const store = useChat({ maxTurns: 4, maxChars: 50 })
    const showSources = mode === 'json'

    for (const n of [1, 2, 3, 4]) await store.send(`Pergunta ${n}`, ['doc-1'], showSources)

    expect(sentHistory(fetchMock, 3)).toEqual([
      ...turn('Pergunta 2', 'Resposta 2.'),
      ...turn('Pergunta 3', 'Resposta 3.'),
    ])
  })

  it.each(modes)('%s: troca mais recente acima do limite sozinha não é enviada', async (mode) => {
    const fetchMock = stubFetchResponses([answer(mode, 'Resposta 1.'), answer(mode, 'Ok.')])
    const store = useChat({ maxTurns: 4, maxChars: 20 })

    await store.send('Pergunta 1', ['doc-1'], mode === 'json')
    await store.send('Pergunta 2', ['doc-1'], mode === 'json')

    expect(sentHistory(fetchMock, 1)).toEqual([])
  })

  it.each(modes)('%s: MAX_HISTORY_TURNS = 0 envia sempre history: []', async (mode) => {
    const fetchMock = stubFetchResponses([answer(mode, 'Resposta 1.'), answer(mode, 'Ok.')])
    const store = useChat({ maxTurns: 0, maxChars: 4000 })

    await store.send('Pergunta 1', ['doc-1'], mode === 'json')
    await store.send('Pergunta 2', ['doc-1'], mode === 'json')

    expect(sentHistory(fetchMock, 1)).toEqual([])
  })

  it.each(modes)('%s: pergunta que terminou em erro fica fora do histórico', async (mode) => {
    const fetchMock = stubFetchResponses([
      answer(mode, 'Resposta 1.'),
      errorResponse(502, 'provider_error', 'O serviço de IA não respondeu corretamente.'),
      answer(mode, 'Resposta 3.'),
    ])
    const store = useChat(limits)
    const showSources = mode === 'json'

    await store.send('Pergunta 1', ['doc-1'], showSources)
    expect(await store.send('Pergunta 2', ['doc-1'], showSources)).toBe(false)
    await store.send('Pergunta 3', ['doc-1'], showSources)

    expect(sentHistory(fetchMock, 2)).toEqual(turn('Pergunta 1', 'Resposta 1.'))
  })

  it.each(modes)('%s: resposta fixa de "sem evidência" fica fora do histórico', async (mode) => {
    const noEvidence =
      'Não encontrei evidências suficientes nos documentos selecionados para responder a essa pergunta.'
    const fetchMock = stubFetchResponses([
      answer(mode, 'Resposta 1.'),
      answer(mode, noEvidence, false),
      answer(mode, 'Resposta 3.'),
    ])
    const store = useChat(limits)
    const showSources = mode === 'json'

    await store.send('Pergunta 1', ['doc-1'], showSources)
    await store.send('Pergunta fora do tema', ['doc-1'], showSources)
    await store.send('Pergunta 3', ['doc-1'], showSources)

    expect(store.entries[3]).toMatchObject({ role: 'assistant', noEvidence: true })
    expect(sentHistory(fetchMock, 2)).toEqual(turn('Pergunta 1', 'Resposta 1.'))
  })

  it('resposta interrompida por Parar fica fora do histórico', async () => {
    const stream = pendingSseResponse([sseEvent({ type: 'delta', text: 'Parcial' })])
    const fetchMock = stubFetchResponses([
      answer('json', 'Resposta 1.'),
      stream.response,
      answer('stream', 'Resposta 3.'),
    ])
    const store = useChat(limits)

    await store.send('Pergunta 1', ['doc-1'])
    const stopped = store.send('Pergunta 2', ['doc-1'], false)
    await vi.waitFor(() => {
      expect(store.entries[3]).toMatchObject({ role: 'assistant', content: 'Parcial' })
    })
    store.stop()
    stream.error(new DOMException('This operation was aborted', 'AbortError'))
    expect(await stopped).toBe(true)
    await store.send('Pergunta 3', ['doc-1'], false)

    expect(store.entries[3]).toMatchObject({ interrupted: true })
    expect(sentHistory(fetchMock, 2)).toEqual(turn('Pergunta 1', 'Resposta 1.'))
  })

  it('parcial seguido de erro no meio do stream fica fora do histórico', async () => {
    const fetchMock = stubFetchResponses([
      sseResponse([
        sseEvent({ type: 'delta', text: 'Parcial' }),
        sseEvent({ type: 'error', error: { code: 'provider_error', message: 'Falhou.' } }),
      ]),
      answer('stream', 'Resposta 2.'),
    ])
    const store = useChat(limits)

    expect(await store.send('Pergunta 1', ['doc-1'], false)).toBe(false)
    await store.send('Pergunta 2', ['doc-1'], false)

    expect(sentHistory(fetchMock, 1)).toEqual([])
  })

  it('a pergunta em andamento não entra no próprio histórico', async () => {
    const fetchMock = stubFetchResponses([answer('json', 'Resposta 1.'), answer('json', 'Ok.')])
    const store = useChat(limits)

    await store.send('Pergunta 1', ['doc-1'])
    await store.send('Pergunta 2', ['doc-1'])

    const history = sentHistory(fetchMock, 1)
    expect(history).toEqual(turn('Pergunta 1', 'Resposta 1.'))
    expect(JSON.stringify(history)).not.toContain('Pergunta 2')
  })

  it('respostas com fontes vão sem os marcadores [n]', async () => {
    const fetchMock = stubFetchResponses([
      answer('json', 'A placa é ABC1D23 [1] e o ano é 2020 [1, 2]. Cor prata [1-3].'),
      answer('stream', 'Ok.'),
    ])
    const store = useChat(limits)

    await store.send('Qual é a placa?', ['doc-1'])
    await store.send('E a cor?', ['doc-1'], false)

    expect(sentHistory(fetchMock, 1)).toEqual(
      turn('Qual é a placa?', 'A placa é ABC1D23 e o ano é 2020. Cor prata.'),
    )
    // The entry on screen keeps its markers.
    expect(store.entries[1]).toMatchObject({
      content: 'A placa é ABC1D23 [1] e o ano é 2020 [1, 2]. Cor prata [1-3].',
    })
  })

  it('mudar o modo entre perguntas mantém o histórico (JSON → stream → JSON)', async () => {
    const fetchMock = stubFetchResponses([
      answer('json', 'Resposta 1 [1].'),
      answer('stream', 'Resposta 2.'),
      answer('json', 'Resposta 3.'),
    ])
    const store = useChat(limits)

    await store.send('Pergunta 1', ['doc-1'])
    await store.send('Pergunta 2', ['doc-2'], false)
    await store.send('Pergunta 3', ['doc-1', 'doc-2'])

    expect(sentHistory(fetchMock, 2)).toEqual([
      ...turn('Pergunta 1', 'Resposta 1.'),
      ...turn('Pergunta 2', 'Resposta 2.'),
    ])
  })
})

describe('useChat: Nova conversa', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it.each(modes)('%s: zera mensagens e histórico e apaga a chave salva', async (mode) => {
    const storage = storageMock()
    vi.stubGlobal('localStorage', storage)
    const fetchMock = stubFetchResponses([answer(mode, 'Resposta 1.'), answer(mode, 'Ok.')])
    const store = useChat(limits)
    const showSources = mode === 'json'

    await store.send('Pergunta 1', ['doc-1'], showSources)
    expect(storage.data.has('chat_history')).toBe(true)

    expect(store.newConversation()).toBe(true)

    expect(store.entries).toEqual([])
    expect(storage.data.has('chat_history')).toBe(false)

    await store.send('Pergunta 2', ['doc-1'], showSources)
    expect(sentHistory(fetchMock, 1)).toEqual([])
    // New ids keep growing: no collision with entries that were on screen.
    expect(store.entries[0]?.id).toBe(3)
  })

  it('é ignorada durante a geração', async () => {
    const stream = pendingSseResponse([])
    stubFetchResponses([stream.response])
    const store = useChat(limits)

    const sending = store.send('Pergunta 1', ['doc-1'], false)
    expect(store.newConversation()).toBe(false)
    expect(store.entries).toHaveLength(2)

    stream.push(sseEvent({ type: 'delta', text: 'Resposta.' }))
    stream.push(sseEvent({ type: 'done', has_evidence: true }))
    stream.close()
    await sending
  })
})

describe('useChat: conversa salva no navegador', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('restaura a conversa, continua o histórico e numera as novas entradas depois dela', async () => {
    const saved = {
      version: 1,
      entries: [
        { role: 'user', content: 'Qual é a placa?' },
        {
          role: 'assistant',
          content: 'A placa é ABC1D23 [1].',
          sources,
          markdown: false,
        },
        { role: 'user', content: 'E a cor?' },
        {
          role: 'assistant',
          content: 'Não encontrei.',
          sources: [],
          markdown: false,
          noEvidence: true,
        },
      ],
    }
    vi.stubGlobal('localStorage', storageMock({ chat_history: JSON.stringify(saved) }))
    const fetchMock = stubFetchResponses([answer('json', 'Ano 2020 [1].')])
    const store = useChat(limits)

    expect(store.entries.map((entry) => entry.id)).toEqual([1, 2, 3, 4])

    await store.send('E o ano?', ['doc-1'])

    // The restored no-evidence answer stays out of the history, as before reloading.
    expect(sentHistory(fetchMock, 0)).toEqual(turn('Qual é a placa?', 'A placa é ABC1D23.'))
    expect(store.entries.map((entry) => entry.id)).toEqual([1, 2, 3, 4, 5, 6])
  })

  it('não salva a resposta em streaming pela metade; salva quando termina', async () => {
    const storage = storageMock()
    vi.stubGlobal('localStorage', storage)
    const stream = pendingSseResponse([sseEvent({ type: 'delta', text: 'Parte 1' })])
    stubFetchResponses([stream.response])
    const store = useChat(limits)

    const sending = store.send('Pergunta 1', ['doc-1'], false)
    await vi.waitFor(() => {
      expect(store.entries[1]).toMatchObject({ content: 'Parte 1' })
    })
    expect(storage.data.has('chat_history')).toBe(false)

    stream.push(sseEvent({ type: 'delta', text: ' e parte 2.' }))
    stream.push(sseEvent({ type: 'done', has_evidence: true }))
    stream.close()
    await sending

    expect(JSON.parse(storage.data.get('chat_history') ?? 'null')).toEqual({
      version: 1,
      entries: [
        { role: 'user', content: 'Pergunta 1' },
        { role: 'assistant', content: 'Parte 1 e parte 2.', sources: [], markdown: true },
      ],
    })
  })

  it('resposta interrompida é salva como está, com a marca de interrompida', async () => {
    const storage = storageMock()
    vi.stubGlobal('localStorage', storage)
    const stream = pendingSseResponse([sseEvent({ type: 'delta', text: 'Parcial' })])
    stubFetchResponses([stream.response])
    const store = useChat(limits)

    const sending = store.send('Pergunta 1', ['doc-1'], false)
    await vi.waitFor(() => {
      expect(store.entries[1]).toMatchObject({ content: 'Parcial' })
    })
    store.stop()
    stream.error(new DOMException('This operation was aborted', 'AbortError'))
    await sending

    const restored = useChat(limits)
    expect(restored.entries[1]).toEqual({
      id: 2,
      role: 'assistant',
      content: 'Parcial',
      sources: [],
      markdown: true,
      interrupted: true,
    })
  })
})
