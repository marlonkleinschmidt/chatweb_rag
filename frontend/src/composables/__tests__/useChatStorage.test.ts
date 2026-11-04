import { afterEach, describe, expect, it, vi } from 'vitest'

import type { ChatEntry } from '@/composables/useChat'
import { MAX_STORED_ENTRIES, useChatStorage } from '@/composables/useChatStorage'
import type { Source } from '@/types/api'

import { blockedStorage, storageMock } from './testUtils'

// Conversation saved in the browser (RF-29): key chat_history, {version: 1, entries}, silent
// fallback for blocked, corrupted or unknown data, at most 50 entries.

const sources: Source[] = [
  { index: 1, document_id: 'doc-1', filename: 'a.pdf', page: 3, excerpt: 'Trecho A.' },
  { index: 2, document_id: 'doc-2', filename: 'b.pdf', page: null, excerpt: 'Trecho B.' },
]

const entries: ChatEntry[] = [
  { id: 7, role: 'user', content: 'Qual é a placa?' },
  { id: 8, role: 'assistant', content: 'A placa é ABC1D23 [1].', sources, markdown: false },
  { id: 9, role: 'user', content: 'E a cor?' },
  {
    id: 10,
    role: 'assistant',
    content: 'Sem evidência.',
    sources: [],
    markdown: false,
    noEvidence: true,
  },
  { id: 11, role: 'user', content: 'Como reinicio?' },
  {
    id: 12,
    role: 'assistant',
    content: 'Desligue',
    sources: [],
    markdown: true,
    interrupted: true,
  },
  { id: 13, role: 'error', content: 'O serviço de IA não respondeu.' },
]

function stored(value: unknown): string {
  return JSON.stringify(value)
}

describe('useChatStorage', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('salva no formato versionado, sem ids, na chave chat_history', () => {
    const storage = storageMock()
    vi.stubGlobal('localStorage', storage)

    useChatStorage().save(entries.slice(0, 2))

    expect(JSON.parse(storage.data.get('chat_history') ?? 'null')).toEqual({
      version: 1,
      entries: [
        { role: 'user', content: 'Qual é a placa?' },
        { role: 'assistant', content: 'A placa é ABC1D23 [1].', sources, markdown: false },
      ],
    })
  })

  it('restaura entradas, fontes e marcas, com ids renumerados a partir de 1', () => {
    vi.stubGlobal('localStorage', storageMock())
    const storage = useChatStorage()

    storage.save(entries)
    const restored = storage.load()

    expect(restored).toEqual(entries.map((entry, index) => ({ ...entry, id: index + 1 })))
  })

  it('sem nada salvo, abre vazio', () => {
    vi.stubGlobal('localStorage', storageMock())

    expect(useChatStorage().load()).toEqual([])
  })

  it('versão desconhecida é descartada em silêncio', () => {
    vi.stubGlobal(
      'localStorage',
      storageMock({
        chat_history: stored({ version: 2, entries: [{ role: 'user', content: 'Olá' }] }),
      }),
    )

    expect(useChatStorage().load()).toEqual([])
  })

  it('JSON corrompido é descartado em silêncio', () => {
    vi.stubGlobal('localStorage', storageMock({ chat_history: '{"version": 1, "entries": [' }))

    expect(useChatStorage().load()).toEqual([])
  })

  it.each([
    { name: 'raiz não é objeto', value: [1, 2] },
    { name: 'entries ausente', value: { version: 1 } },
    {
      name: 'papel desconhecido',
      value: { version: 1, entries: [{ role: 'system', content: 'x' }] },
    },
    { name: 'content ausente', value: { version: 1, entries: [{ role: 'user' }] } },
    {
      name: 'fonte inválida',
      value: {
        version: 1,
        entries: [{ role: 'assistant', content: 'x', sources: [{ index: '1' }], markdown: false }],
      },
    },
    {
      name: 'assistente sem markdown',
      value: { version: 1, entries: [{ role: 'assistant', content: 'x', sources: [] }] },
    },
    {
      name: 'marca com tipo errado',
      value: {
        version: 1,
        entries: [
          { role: 'assistant', content: 'x', sources: [], markdown: false, interrupted: 'sim' },
        ],
      },
    },
  ])('formato inválido ($name) é descartado em silêncio', ({ value }) => {
    vi.stubGlobal('localStorage', storageMock({ chat_history: stored(value) }))

    expect(useChatStorage().load()).toEqual([])
  })

  it('storage bloqueado não quebra: leitura vazia, escrita e limpeza sem erro', () => {
    vi.stubGlobal('localStorage', blockedStorage())
    const storage = useChatStorage()

    expect(storage.load()).toEqual([])
    expect(() => storage.save(entries)).not.toThrow()
    expect(() => storage.clear()).not.toThrow()
  })

  it('sem localStorage no ambiente, abre vazio e não quebra', () => {
    // The node test environment has no localStorage: accessing it throws ReferenceError.
    const storage = useChatStorage()

    expect(storage.load()).toEqual([])
    expect(() => storage.save(entries)).not.toThrow()
  })

  it(`guarda no máximo ${MAX_STORED_ENTRIES} entradas: as mais antigas saem`, () => {
    const storage = storageMock()
    vi.stubGlobal('localStorage', storage)
    const many: ChatEntry[] = Array.from({ length: 60 }, (_, index) => ({
      id: index + 1,
      role: 'user',
      content: `Mensagem ${index + 1}`,
    }))

    useChatStorage().save(many)

    const saved: unknown = JSON.parse(storage.data.get('chat_history') ?? 'null')
    expect(saved).toMatchObject({ version: 1 })
    const restored = useChatStorage().load()
    expect(restored).toHaveLength(50)
    expect(restored[0]).toEqual({ id: 1, role: 'user', content: 'Mensagem 11' })
    expect(restored[49]).toEqual({ id: 50, role: 'user', content: 'Mensagem 60' })
  })

  it('dados gravados com mais de 50 entradas são restaurados só com as 50 mais recentes', () => {
    const raw = Array.from({ length: 55 }, (_, index) => ({
      role: 'user',
      content: `Mensagem ${index + 1}`,
    }))
    vi.stubGlobal(
      'localStorage',
      storageMock({ chat_history: stored({ version: 1, entries: raw }) }),
    )

    const restored = useChatStorage().load()

    expect(restored).toHaveLength(50)
    expect(restored[0]).toMatchObject({ content: 'Mensagem 6' })
  })

  it('clear remove a chave chat_history', () => {
    const storage = storageMock({
      chat_history: stored({ version: 1, entries: [] }),
      theme: 'dark',
    })
    vi.stubGlobal('localStorage', storage)

    useChatStorage().clear()

    expect(storage.data.has('chat_history')).toBe(false)
    // Other preferences are untouched.
    expect(storage.data.get('theme')).toBe('dark')
  })
})
