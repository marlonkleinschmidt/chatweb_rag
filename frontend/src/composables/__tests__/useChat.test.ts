import { afterEach, describe, expect, it, vi } from 'vitest'

import { useChat } from '@/composables/useChat'
import { ptBR } from '@/locales/pt-BR'
import type { ChatResponse, Source } from '@/types/api'

import {
  apiUrl,
  errorResponse,
  jsonResponse,
  pendingResponse,
  stubFetchResponses,
} from './testUtils'

// Fixed no-evidence answer required by PRD RF-14.
const noEvidenceAnswer =
  'Não encontrei evidências suficientes nos documentos selecionados para responder a essa pergunta.'

const defaultSources: Source[] = [
  {
    index: 1,
    document_id: 'doc-1',
    filename: 'doc-1.pdf',
    page: 2,
    excerpt: 'Trecho citado na resposta.',
  },
]

function chatResponse(overrides: Partial<ChatResponse> = {}): ChatResponse {
  return {
    answer: 'Afirmação apoiada no documento [1].',
    has_evidence: true,
    sources: defaultSources,
    ...overrides,
  }
}

describe('useChat', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('envia apenas pergunta e seleção, sem histórico da conversa', async () => {
    const fetchMock = stubFetchResponses([
      jsonResponse(chatResponse()),
      jsonResponse(chatResponse()),
    ])
    const store = useChat()

    expect(await store.send('Qual é o prazo de entrega?', ['doc-1'])).toBe(true)
    expect(await store.send('E qual o valor total?', ['doc-1', 'doc-2'])).toBe(true)

    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(fetchMock.mock.calls[0]?.[0]).toBe(apiUrl('/chat/query'))
    expect(fetchMock.mock.calls[1]?.[0]).toBe(apiUrl('/chat/query'))

    const firstInit = fetchMock.mock.calls[0]?.[1]
    const secondInit = fetchMock.mock.calls[1]?.[1]
    expect(firstInit?.method).toBe('POST')
    // Only the current question and selection travel: no previous messages.
    expect(JSON.parse(String(firstInit?.body))).toEqual({
      question: 'Qual é o prazo de entrega?',
      document_ids: ['doc-1'],
    })
    expect(JSON.parse(String(secondInit?.body))).toEqual({
      question: 'E qual o valor total?',
      document_ids: ['doc-1', 'doc-2'],
    })
  })

  it('mantém a conversa em memória, na ordem das mensagens', async () => {
    stubFetchResponses([
      jsonResponse(chatResponse({ answer: 'Primeira resposta.' })),
      jsonResponse(chatResponse({ answer: 'Segunda resposta.' })),
    ])
    const store = useChat()

    await store.send('Primeira pergunta', ['doc-1'])
    await store.send('Segunda pergunta', ['doc-1'])

    expect(store.entries).toEqual([
      { id: 1, role: 'user', content: 'Primeira pergunta' },
      { id: 2, role: 'assistant', content: 'Primeira resposta.', sources: defaultSources },
      { id: 3, role: 'user', content: 'Segunda pergunta' },
      { id: 4, role: 'assistant', content: 'Segunda resposta.', sources: defaultSources },
    ])
  })

  it('ignora novo envio enquanto gera a resposta', async () => {
    const inFlight = pendingResponse()
    const fetchMock = stubFetchResponses([inFlight.response, jsonResponse(chatResponse())])
    const store = useChat()

    const first = store.send('Primeira pergunta', ['doc-1'])
    expect(store.generating).toBe(true)

    // A second send while generating is ignored: no new message, no new request.
    const second = await store.send('Segunda pergunta', ['doc-1'])
    expect(second).toBe(false)
    expect(store.generating).toBe(true)
    expect(store.entries).toEqual([{ id: 1, role: 'user', content: 'Primeira pergunta' }])
    expect(fetchMock).toHaveBeenCalledTimes(1)

    inFlight.resolve(jsonResponse(chatResponse({ answer: 'Resposta concluída.' })))
    expect(await first).toBe(true)

    expect(store.generating).toBe(false)
    expect(store.entries).toEqual([
      { id: 1, role: 'user', content: 'Primeira pergunta' },
      { id: 2, role: 'assistant', content: 'Resposta concluída.', sources: defaultSources },
    ])
  })

  it('resposta sem evidência chega com o texto fixo e sem fontes', async () => {
    stubFetchResponses([
      jsonResponse(chatResponse({ answer: noEvidenceAnswer, has_evidence: false, sources: [] })),
    ])
    const store = useChat()

    expect(await store.send('Pergunta fora do tema dos documentos', ['doc-1'])).toBe(true)

    expect(store.entries).toEqual([
      { id: 1, role: 'user', content: 'Pergunta fora do tema dos documentos' },
      { id: 2, role: 'assistant', content: noEvidenceAnswer, sources: [] },
    ])
  })

  it('resposta com evidência chega com as fontes citadas', async () => {
    const sources: Source[] = [
      { index: 1, document_id: 'doc-1', filename: 'a.pdf', page: 3, excerpt: 'Trecho A.' },
      { index: 2, document_id: 'doc-2', filename: 'b.pdf', page: null, excerpt: 'Trecho B.' },
    ]
    stubFetchResponses([
      jsonResponse(chatResponse({ answer: 'Afirmação [1] e complemento [2].', sources })),
    ])
    const store = useChat()

    expect(await store.send('O que dizem os documentos?', ['doc-1', 'doc-2'])).toBe(true)

    expect(store.entries).toEqual([
      { id: 1, role: 'user', content: 'O que dizem os documentos?' },
      { id: 2, role: 'assistant', content: 'Afirmação [1] e complemento [2].', sources },
    ])
  })

  it('erro da API vira mensagem de erro na conversa logo após a pergunta', async () => {
    stubFetchResponses([
      errorResponse(
        502,
        'provider_error',
        'O serviço de IA não respondeu corretamente. Tente novamente.',
      ),
    ])
    const store = useChat()

    const result = await store.send('Pergunta qualquer', ['doc-1'])

    expect(result).toBe(false)
    expect(store.generating).toBe(false)
    expect(store.entries).toEqual([
      { id: 1, role: 'user', content: 'Pergunta qualquer' },
      {
        id: 2,
        role: 'error',
        content: 'O serviço de IA não respondeu corretamente. Tente novamente.',
      },
    ])
  })

  it('erro de rede vira mensagem de erro na conversa', async () => {
    stubFetchResponses([new TypeError('Failed to fetch')])
    const store = useChat()

    const result = await store.send('Pergunta qualquer', ['doc-1'])

    expect(result).toBe(false)
    expect(store.generating).toBe(false)
    expect(store.entries).toEqual([
      { id: 1, role: 'user', content: 'Pergunta qualquer' },
      { id: 2, role: 'error', content: ptBR.errors.network },
    ])
  })
})
