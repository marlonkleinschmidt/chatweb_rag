import { afterEach, describe, expect, it, vi } from 'vitest'

import { useShowSources } from '@/composables/useShowSources'

// In-memory stand-in for localStorage: the node test environment has no storage at all.
function storageMock(initial: Record<string, string> = {}) {
  const store = new Map<string, string>(Object.entries(initial))
  return {
    getItem: (key: string): string | null => store.get(key) ?? null,
    setItem: (key: string, value: string): void => {
      store.set(key, value)
    },
  }
}

// Storage that throws on the given operation (blocked storage, e.g. private mode).
function blockedStorage(block: 'read' | 'write') {
  const boom = (): never => {
    throw new Error('storage blocked')
  }
  return {
    getItem: block === 'read' ? boom : (): string | null => null,
    setItem: block === 'write' ? boom : (): void => {},
  }
}

// "Exibir fontes" preference (RF-20): default on, persisted per browser, silent fallback.
describe('useShowSources', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('primeira visita vem ligado: true sem valor armazenado', () => {
    vi.stubGlobal('localStorage', storageMock())
    const store = useShowSources()

    expect(store.showSources).toBe(true)
  })

  it('desligar persiste "false" na chave show_sources e uma nova instância lê de volta', () => {
    const storage = storageMock()
    vi.stubGlobal('localStorage', storage)
    const store = useShowSources()

    store.setShowSources(false)

    expect(store.showSources).toBe(false)
    expect(storage.getItem('show_sources')).toBe('false')
    // Reloading the page: the next instance starts with the persisted choice.
    expect(useShowSources().showSources).toBe(false)
  })

  it('religar persiste "true" e uma nova instância volta ligado', () => {
    const storage = storageMock({ show_sources: 'false' })
    vi.stubGlobal('localStorage', storage)
    const store = useShowSources()

    expect(store.showSources).toBe(false)

    store.setShowSources(true)

    expect(storage.getItem('show_sources')).toBe('true')
    expect(useShowSources().showSources).toBe(true)
  })

  it('valor armazenado inválido cai no padrão ligado', () => {
    vi.stubGlobal('localStorage', storageMock({ show_sources: 'banana' }))

    expect(useShowSources().showSources).toBe(true)
  })

  it('storage bloqueado na leitura não quebra: usa o padrão ligado', () => {
    vi.stubGlobal('localStorage', blockedStorage('read'))

    expect(useShowSources().showSources).toBe(true)
  })

  it('storage bloqueado na escrita não quebra: a escolha vale na sessão', () => {
    vi.stubGlobal('localStorage', blockedStorage('write'))
    const store = useShowSources()

    store.setShowSources(false)

    expect(store.showSources).toBe(false)
  })
})
