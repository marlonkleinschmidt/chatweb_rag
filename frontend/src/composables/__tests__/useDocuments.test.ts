import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope } from 'vue'
import type { EffectScope } from 'vue'

import { useDocuments } from '@/composables/useDocuments'
import type { DocumentsStore } from '@/composables/useDocuments'
import { config } from '@/config'
import { ptBR } from '@/locales/pt-BR'

import {
  apiUrl,
  errorResponse,
  jsonResponse,
  listResponse,
  makeDocument,
  noContentResponse,
  pendingResponse,
  stubFetchResponses,
} from './testUtils'

// Each test gets its own effect scope so onScopeDispose (polling teardown) is exercised.
describe('useDocuments', () => {
  let scope: EffectScope
  let store: DocumentsStore

  beforeEach(() => {
    scope = effectScope()
    const created = scope.run(() => useDocuments())
    if (created === undefined) throw new Error('useDocuments returned undefined inside the scope')
    store = created
  })

  afterEach(() => {
    // Stopping the scope clears any pending polling timer (onScopeDispose).
    scope.stop()
    vi.unstubAllGlobals()
    vi.useRealTimers()
  })

  it('carrega a lista na ordem da API e reflete embedding_model_changed', async () => {
    const fetchMock = stubFetchResponses([
      listResponse([makeDocument('doc-2', { status: 'processing' }), makeDocument('doc-1')], true),
    ])

    await store.load()

    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(fetchMock.mock.calls[0]?.[0]).toBe(apiUrl('/documents'))
    expect(store.documents.map((d) => d.id)).toEqual(['doc-2', 'doc-1'])
    expect(store.embeddingModelChanged).toBe(true)
    expect(store.loaded).toBe(true)
    expect(store.loading).toBe(false)
    expect(store.loadError).toBeNull()
  })

  it('agenda exatamente um timer de polling enquanto há pendente e para quando todos terminam', async () => {
    vi.useFakeTimers()
    const fetchMock = stubFetchResponses([
      listResponse([makeDocument('doc-1', { status: 'received' })]),
      listResponse([makeDocument('doc-1', { status: 'processing' })]),
      listResponse([makeDocument('doc-1')]),
    ])

    await store.load()
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(vi.getTimerCount()).toBe(1)

    await vi.advanceTimersByTimeAsync(config.pollIntervalMs)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(vi.getTimerCount()).toBe(1)

    await vi.advanceTimersByTimeAsync(config.pollIntervalMs)
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(vi.getTimerCount()).toBe(0)

    // All documents finished: no more calls, no matter how much time passes.
    await vi.advanceTimersByTimeAsync(config.pollIntervalMs * 3)
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(vi.getTimerCount()).toBe(0)
  })

  it('não agenda polling quando nenhum documento está pendente', async () => {
    vi.useFakeTimers()
    const fetchMock = stubFetchResponses([
      listResponse([
        makeDocument('doc-1'),
        makeDocument('doc-2', {
          status: 'failed',
          error_code: 'pdf_no_text',
          error_message:
            'Este PDF não contém texto pesquisável. PDFs digitalizados ainda não são suportados.',
        }),
      ]),
    ])

    await store.load()

    expect(vi.getTimerCount()).toBe(0)
    await vi.advanceTimersByTimeAsync(config.pollIntervalMs * 2)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('para o polling em erro de rede e retoma com load()', async () => {
    vi.useFakeTimers()
    const fetchMock = stubFetchResponses([
      listResponse([makeDocument('doc-1', { status: 'processing' })]),
      new TypeError('Failed to fetch'),
      listResponse([makeDocument('doc-1')]),
    ])

    await store.load()
    expect(vi.getTimerCount()).toBe(1)

    // The scheduled poll fails at the network level: polling stops, no retry by timer.
    await vi.advanceTimersByTimeAsync(config.pollIntervalMs)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(store.loadError).toBe(ptBR.errors.network)
    expect(vi.getTimerCount()).toBe(0)
    expect(store.documents.map((d) => d.id)).toEqual(['doc-1'])

    await vi.advanceTimersByTimeAsync(config.pollIntervalMs * 2)
    expect(fetchMock).toHaveBeenCalledTimes(2)

    // "Tentar novamente" calls load() and everything is back to normal.
    await store.load()
    expect(fetchMock).toHaveBeenCalledTimes(3)
    expect(store.loadError).toBeNull()
    expect(store.documents.map((d) => d.id)).toEqual(['doc-1'])
    expect(vi.getTimerCount()).toBe(0)
  })

  it('rejeita upload de arquivo que não é PDF sem chamar a API', async () => {
    const fetchMock = stubFetchResponses([])

    const result = await store.upload(new File(['anotações'], 'notas.txt', { type: 'text/plain' }))

    expect(result).toBe(false)
    expect(store.uploadError).toBe(ptBR.upload.notPdf)
    expect(store.uploadNotice).toBeNull()
    expect(store.uploading).toBe(false)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('rejeita upload de arquivo vazio sem chamar a API', async () => {
    const fetchMock = stubFetchResponses([])

    const result = await store.upload(new File([], 'vazio.pdf', { type: 'application/pdf' }))

    expect(result).toBe(false)
    expect(store.uploadError).toBe(ptBR.upload.empty)
    expect(store.uploadNotice).toBeNull()
    expect(store.uploading).toBe(false)
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('upload aceito mostra aviso de sucesso, envia multipart e recarrega a lista', async () => {
    const file = new File(['%PDF-1.4 conteúdo'], 'novo.pdf', { type: 'application/pdf' })
    const uploadBody = { ...makeDocument('doc-9', { status: 'received' }), warning: null }
    const fetchMock = stubFetchResponses([
      jsonResponse(uploadBody, 202),
      listResponse([makeDocument('doc-9', { status: 'received' })]),
    ])

    const result = await store.upload(file)

    expect(result).toBe(true)
    expect(store.uploading).toBe(false)
    expect(store.uploadError).toBeNull()
    expect(store.uploadNotice).toEqual({ variant: 'success', text: ptBR.upload.accepted })
    // POST /documents as multipart with the `file` field (boundary left to the browser).
    expect(fetchMock.mock.calls[0]?.[0]).toBe(apiUrl('/documents'))
    const init = fetchMock.mock.calls[0]?.[1]
    expect(init?.method).toBe('POST')
    const body = init?.body
    expect(body).toBeInstanceOf(FormData)
    expect((body as FormData).get('file')).toBe(file)
    // The list is refreshed right after the upload.
    expect(fetchMock.mock.calls[1]?.[0]).toBe(apiUrl('/documents'))
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(store.documents.map((d) => d.id)).toEqual(['doc-9'])
  })

  it('upload duplicado mostra aviso de atenção com o warning da API', async () => {
    const file = new File(['%PDF-1.4 duplicado'], 'duplicado.pdf', { type: 'application/pdf' })
    const uploadBody = { ...makeDocument('doc-1'), warning: 'Este arquivo já foi enviado.' }
    const fetchMock = stubFetchResponses([
      jsonResponse(uploadBody, 202),
      listResponse([makeDocument('doc-1')]),
    ])

    const result = await store.upload(file)

    expect(result).toBe(true)
    expect(store.uploadError).toBeNull()
    expect(store.uploadNotice).toEqual({ variant: 'warning', text: 'Este arquivo já foi enviado.' })
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('sinaliza uploading enquanto o upload está em andamento', async () => {
    const inFlight = pendingResponse()
    const fetchMock = stubFetchResponses([
      inFlight.response,
      listResponse([makeDocument('doc-5', { status: 'received' })]),
    ])
    const file = new File(['%PDF-1.4 lento'], 'lento.pdf', { type: 'application/pdf' })

    const uploadPromise = store.upload(file)
    expect(store.uploading).toBe(true)

    inFlight.resolve(
      jsonResponse({ ...makeDocument('doc-5', { status: 'received' }), warning: null }, 202),
    )
    await uploadPromise

    expect(store.uploading).toBe(false)
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('sinaliza removingId durante a remoção', async () => {
    const inFlight = pendingResponse()
    const fetchMock = stubFetchResponses([inFlight.response])

    const removalPromise = store.remove('doc-1')
    expect(store.removingId).toBe('doc-1')

    inFlight.resolve(noContentResponse())
    await removalPromise

    expect(store.removingId).toBeNull()
    expect(store.isRemoved('doc-1')).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })

  it('remoção concluída marca removedIds, retira o documento da lista e poda a seleção', async () => {
    const fetchMock = stubFetchResponses([
      listResponse([makeDocument('doc-1'), makeDocument('doc-2')]),
      noContentResponse(),
    ])
    await store.load()
    store.setSelected('doc-1', true)
    store.setSelected('doc-2', true)

    const result = await store.remove('doc-1')

    expect(result).toBe(true)
    expect(store.removeError).toBeNull()
    expect(store.removingId).toBeNull()
    expect(store.isRemoved('doc-1')).toBe(true)
    expect(store.isRemoved('doc-2')).toBe(false)
    expect(store.documents.map((d) => d.id)).toEqual(['doc-2'])
    expect(store.selectedIds).toEqual(['doc-2'])
    // Success path filters the list locally: no extra load.
    expect(fetchMock).toHaveBeenCalledTimes(2)
  })

  it('trata 404 document_not_found na remoção como sucesso', async () => {
    const fetchMock = stubFetchResponses([
      listResponse([makeDocument('doc-1')]),
      errorResponse(404, 'document_not_found', 'Documento não encontrado.'),
      listResponse([]),
    ])
    await store.load()

    const result = await store.remove('doc-1')

    expect(result).toBe(true)
    expect(store.removeError).toBeNull()
    expect(store.removingId).toBeNull()
    expect(store.isRemoved('doc-1')).toBe(true)
    expect(store.documents).toHaveLength(0)
    // list + delete + refresh load
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('remoção com 409 document_processing mostra o erro e recarrega a lista', async () => {
    const fetchMock = stubFetchResponses([
      listResponse([makeDocument('doc-1', { status: 'processing' })]),
      errorResponse(
        409,
        'document_processing',
        'Aguarde o fim do processamento para remover este documento.',
      ),
      listResponse([makeDocument('doc-1', { status: 'processing' })]),
    ])
    await store.load()

    const result = await store.remove('doc-1')

    expect(result).toBe(false)
    expect(store.removeError).toBe('Aguarde o fim do processamento para remover este documento.')
    expect(store.isRemoved('doc-1')).toBe(false)
    expect(store.documents.map((d) => d.id)).toEqual(['doc-1'])
    expect(fetchMock).toHaveBeenCalledTimes(3)
  })

  it('só permite selecionar documentos ready existentes', async () => {
    stubFetchResponses([
      listResponse([makeDocument('ready-1'), makeDocument('busy-1', { status: 'processing' })]),
    ])
    await store.load()

    store.setSelected('ready-1', true)
    expect(store.isSelected('ready-1')).toBe(true)

    // processing documents are never selectable
    store.setSelected('busy-1', true)
    expect(store.isSelected('busy-1')).toBe(false)

    // unknown ids are ignored
    store.setSelected('ghost-1', true)
    expect(store.isSelected('ghost-1')).toBe(false)

    // deselecting works
    store.setSelected('ready-1', false)
    expect(store.isSelected('ready-1')).toBe(false)
    expect(store.selectedIds).toEqual([])
  })

  it('limita a seleção a maxDocumentsPerQuery documentos', async () => {
    const max = config.maxDocumentsPerQuery
    const docs = Array.from({ length: max + 1 }, (_, index) => makeDocument(`doc-${index}`))
    stubFetchResponses([listResponse(docs)])
    await store.load()

    for (let index = 0; index < max; index++) {
      store.setSelected(`doc-${index}`, true)
    }
    expect(store.selectedIds).toHaveLength(max)
    expect(store.selectionFull).toBe(true)

    // one more would exceed the limit: ignored
    store.setSelected(`doc-${max}`, true)
    expect(store.isSelected(`doc-${max}`)).toBe(false)
    expect(store.selectedIds).toHaveLength(max)

    // deselecting frees a slot for another document
    store.setSelected('doc-0', false)
    expect(store.selectionFull).toBe(false)
    store.setSelected(`doc-${max}`, true)
    expect(store.isSelected(`doc-${max}`)).toBe(true)
    expect(store.selectedIds).toHaveLength(max)
  })

  it('poda a seleção quando um documento deixa de estar ready', async () => {
    stubFetchResponses([
      listResponse([makeDocument('doc-1'), makeDocument('doc-2')]),
      listResponse([makeDocument('doc-1', { status: 'processing' }), makeDocument('doc-2')]),
    ])
    await store.load()
    store.setSelected('doc-1', true)
    store.setSelected('doc-2', true)

    await store.load()

    expect(store.selectedIds).toEqual(['doc-2'])
  })

  it('poda a seleção quando um documento some da lista', async () => {
    stubFetchResponses([
      listResponse([makeDocument('doc-1'), makeDocument('doc-2')]),
      listResponse([makeDocument('doc-2')]),
    ])
    await store.load()
    store.setSelected('doc-1', true)
    store.setSelected('doc-2', true)

    await store.load()

    expect(store.selectedIds).toEqual(['doc-2'])
    expect(store.isRemoved('doc-1')).toBe(true)
  })

  it('load com falha não marca nenhum documento como removido', async () => {
    stubFetchResponses([
      listResponse([makeDocument('doc-1'), makeDocument('doc-2')]),
      errorResponse(500, 'internal_error', 'Ocorreu um erro inesperado. Tente novamente.'),
    ])
    await store.load()

    await store.load()

    expect(store.isRemoved('doc-1')).toBe(false)
    expect(store.isRemoved('doc-2')).toBe(false)
    expect(store.loadError).toBe('Ocorreu um erro inesperado. Tente novamente.')
    // the previous list is kept
    expect(store.documents.map((d) => d.id)).toEqual(['doc-1', 'doc-2'])
  })

  it('marca como removido o documento que sumiu da lista em um load bem-sucedido', async () => {
    stubFetchResponses([
      listResponse([makeDocument('doc-1'), makeDocument('doc-2')]),
      listResponse([makeDocument('doc-2')]),
    ])
    await store.load()

    await store.load()

    expect(store.isRemoved('doc-1')).toBe(true)
    expect(store.isRemoved('doc-2')).toBe(false)
  })

  it('para o polling quando o escopo é descartado', async () => {
    vi.useFakeTimers()
    const fetchMock = stubFetchResponses([
      listResponse([makeDocument('doc-1', { status: 'processing' })]),
    ])
    await store.load()
    expect(vi.getTimerCount()).toBe(1)

    scope.stop()

    expect(vi.getTimerCount()).toBe(0)
    await vi.advanceTimersByTimeAsync(config.pollIntervalMs * 2)
    expect(fetchMock).toHaveBeenCalledTimes(1)
  })
})
