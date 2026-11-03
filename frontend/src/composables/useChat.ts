import { reactive, ref } from 'vue'

import { ptBR } from '@/locales/pt-BR'
import { ApiError, queryChat } from '@/services/api'
import type { Source } from '@/types/api'

export type ChatEntry =
  | { id: number; role: 'user'; content: string }
  | { id: number; role: 'assistant'; content: string; sources: Source[] }
  | { id: number; role: 'error'; content: string }

function errorMessage(error: unknown): string {
  // ApiError messages are pt-BR: the API envelope message (provider_error, provider_timeout,
  // document_not_ready...) or a frontend locale text (network error).
  return error instanceof ApiError ? error.message : ptBR.errors.unexpected
}

// Chat session kept only in memory: reloading the page clears it (RF-15).
export function useChat() {
  const entries = ref<ChatEntry[]>([])
  const generating = ref(false)
  let nextId = 1

  async function send(question: string, documentIds: string[]): Promise<boolean> {
    // One question at a time: no duplicate sending while an answer is being generated.
    if (generating.value) return false
    entries.value.push({ id: nextId++, role: 'user', content: question })
    generating.value = true
    try {
      // Only the current question and selection; previous messages are never sent.
      const response = await queryChat({ question, document_ids: documentIds })
      entries.value.push({
        id: nextId++,
        role: 'assistant',
        content: response.answer,
        sources: response.sources,
      })
      return true
    } catch (error) {
      entries.value.push({ id: nextId++, role: 'error', content: errorMessage(error) })
      return false
    } finally {
      generating.value = false
    }
  }

  return reactive({ entries, generating, send })
}
