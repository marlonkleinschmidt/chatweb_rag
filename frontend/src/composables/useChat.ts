import { reactive, ref } from 'vue'

import { ptBR } from '@/locales/pt-BR'
import { ApiError, queryChat, streamChat, StreamAbortedError } from '@/services/api'
import type { Source } from '@/types/api'

export type ChatEntry =
  | { id: number; role: 'user'; content: string }
  // `markdown` is true only for streamed answers (show sources off, RF-24): the model writes
  // prose and the answer renders through MarkdownText. With sources it stays plain text.
  | { id: number; role: 'assistant'; content: string; sources: Source[]; markdown: boolean }
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
  // Aborts the in-flight streamed answer (Parar, RF-23); null outside a streaming send.
  let controller: AbortController | null = null

  // Show sources off: the answer is streamed (POST /chat/query/stream, RF-22). The
  // assistant entry is born empty right after the user entry and grows with each delta
  // through the reactive proxy taken from the entries array, so the log updates in place.
  async function sendStreamed(question: string, documentIds: string[]): Promise<void> {
    const entryId = nextId++
    entries.value.push({
      id: entryId,
      role: 'assistant',
      content: '',
      sources: [],
      markdown: true,
    })
    const entry = entries.value[entries.value.length - 1]
    if (!entry || entry.role !== 'assistant') return
    controller = new AbortController()
    try {
      await streamChat(
        { question, document_ids: documentIds, show_sources: false },
        {
          signal: controller.signal,
          onDelta: (text: string) => {
            entry.content += text
          },
          // The fixed no-evidence answer (RF-14) arrives as a delta; nothing to do on done.
          onDone: () => {},
        },
      )
    } catch (error) {
      // Failed or stopped before the first delta: drop the empty bubble, so the log (and the
      // screen reader) never shows an assistant entry without content. A partial text stays.
      if (entry.content === '') {
        entries.value = entries.value.filter((item) => item.id !== entryId)
      }
      throw error
    }
  }

  // `showSources` is captured per question (RF-20): toggling it does not change entries
  // that already have an answer, and the choice travels explicitly in every payload.
  async function send(
    question: string,
    documentIds: string[],
    showSources = true,
  ): Promise<boolean> {
    // One question at a time: no duplicate sending while an answer is being generated.
    if (generating.value) return false
    entries.value.push({ id: nextId++, role: 'user', content: question })
    generating.value = true
    try {
      if (showSources) {
        const response = await queryChat({
          question,
          document_ids: documentIds,
          show_sources: true,
        })
        entries.value.push({
          id: nextId++,
          role: 'assistant',
          content: response.answer,
          sources: response.sources,
          markdown: false,
        })
      } else {
        await sendStreamed(question, documentIds)
      }
      return true
    } catch (error) {
      if (error instanceof StreamAbortedError) {
        // Parar (RF-23): the partial text stays (an empty entry was already dropped), no error
        // entry, and a new send is accepted.
        return true
      }
      // A failure keeps the partial text (if any) and appends the error right after it (RF-22).
      entries.value.push({ id: nextId++, role: 'error', content: errorMessage(error) })
      return false
    } finally {
      controller = null
      generating.value = false
    }
  }

  // Interrupts the in-flight streamed answer (RF-23). A no-op while a JSON answer is being
  // generated or when nothing is in flight.
  function stop(): void {
    controller?.abort()
  }

  return reactive({ entries, generating, send, stop })
}
