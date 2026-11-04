import { reactive, ref } from 'vue'

import { useChatStorage } from '@/composables/useChatStorage'
import { config } from '@/config'
import { ptBR } from '@/locales/pt-BR'
import { ApiError, queryChat, streamChat, StreamAbortedError } from '@/services/api'
import type { ChatHistoryMessage, Source } from '@/types/api'

export type ChatEntry =
  | { id: number; role: 'user'; content: string }
  // `markdown` is true only for streamed answers (show sources off, RF-24): the model writes
  // prose and the answer renders through MarkdownText. With sources it stays plain text.
  // `noEvidence` (the fixed RF-14 answer) and `interrupted` (stopped by Parar, RF-23) are set
  // only when true; both keep the answer out of the history sent to the API (RF-25).
  | {
      id: number
      role: 'assistant'
      content: string
      sources: Source[]
      markdown: boolean
      noEvidence?: boolean
      interrupted?: boolean
    }
  | { id: number; role: 'error'; content: string }

export interface HistoryLimits {
  maxTurns: number
  maxChars: number
}

// Same marker pattern as MODEL_MARKER_PATTERN in the backend: `[3]`, `[1, 2]`, `[1-3]`.
const CITATION_MARKER_PATTERN = /\[\s*\d+(?:\s*[,;\-–]\s*\d+)*\s*\]/g

// Removes the [n] markers of an answer with sources, so the model never reuses an old
// numbering (PRD §13.7). Only spaces and tabs are normalised: streamed answers are markdown
// and their line breaks matter.
export function stripCitationMarkers(text: string): string {
  return text
    .replace(CITATION_MARKER_PATTERN, '')
    .replace(/[ \t]+([.,;:!?…])/g, '$1')
    .replace(/[ \t]{2,}/g, ' ')
    .trim()
}

// History sent with a question (RF-25): the last completed turns (question + answer) of the
// conversation, oldest first. A turn is left out when its answer is missing, is the fixed
// no-evidence answer, was interrupted, or was followed by an error (a stream that failed after
// a partial text). Then the oldest whole turns are dropped until the total fits maxChars; when
// the most recent turn alone does not fit, nothing is sent.
export function buildHistory(
  entries: readonly ChatEntry[],
  limits: HistoryLimits,
): ChatHistoryMessage[] {
  const turns: { question: string; answer: string }[] = []
  entries.forEach((entry, index) => {
    if (entry.role !== 'user') return
    const answer = entries[index + 1]
    if (!answer || answer.role !== 'assistant' || answer.noEvidence || answer.interrupted) return
    if (entries[index + 2]?.role === 'error') return
    const question = entry.content.trim()
    const text = stripCitationMarkers(answer.content)
    // The API rejects empty content (history_invalid).
    if (question === '' || text === '') return
    turns.push({ question, answer: text })
  })

  const recent = limits.maxTurns > 0 ? turns.slice(-limits.maxTurns) : []
  let total = recent.reduce((sum, turn) => sum + turn.question.length + turn.answer.length, 0)
  while (recent.length > 0 && total > limits.maxChars) {
    const oldest = recent.shift()
    if (oldest) total -= oldest.question.length + oldest.answer.length
  }
  return recent.flatMap((turn): ChatHistoryMessage[] => [
    { role: 'user', content: turn.question },
    { role: 'assistant', content: turn.answer },
  ])
}

function errorMessage(error: unknown): string {
  // ApiError messages are pt-BR: the API envelope message (provider_error, provider_timeout,
  // document_not_ready...) or a frontend locale text (network error).
  return error instanceof ApiError ? error.message : ptBR.errors.unexpected
}

// Chat session (RF-25, RF-28, RF-29): entries live in memory and are saved in this browser
// after each answer; the recent turns travel as `history` with every question.
export function useChat(
  limits: HistoryLimits = { maxTurns: config.maxHistoryTurns, maxChars: config.maxHistoryChars },
) {
  const storage = useChatStorage()
  // Restored entries are numbered 1..n, so new ids start right after them.
  const entries = ref<ChatEntry[]>(storage.load())
  const generating = ref(false)
  let nextId = entries.value.length + 1
  // Aborts the in-flight streamed answer (Parar, RF-23); null outside a streaming send.
  let controller: AbortController | null = null

  // Show sources off: the answer is streamed (POST /chat/query/stream, RF-22). The
  // assistant entry is born empty right after the user entry and grows with each delta
  // through the reactive proxy taken from the entries array, so the log updates in place.
  async function sendStreamed(
    question: string,
    documentIds: string[],
    history: ChatHistoryMessage[],
  ): Promise<void> {
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
        { question, document_ids: documentIds, show_sources: false, history },
        {
          signal: controller.signal,
          onDelta: (text: string) => {
            entry.content += text
          },
          // The fixed no-evidence answer (RF-14) arrives as a delta; `done` tells it apart.
          onDone: (hasEvidence: boolean) => {
            if (!hasEvidence) entry.noEvidence = true
          },
        },
      )
    } catch (error) {
      // Parar after some text: the partial stays on screen (and in storage) but never goes
      // into the history (RF-25, RF-29).
      if (error instanceof StreamAbortedError && entry.content !== '') entry.interrupted = true
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
    // Built before the new question is added: the question in progress never goes in it.
    const history = buildHistory(entries.value, limits)
    entries.value.push({ id: nextId++, role: 'user', content: question })
    generating.value = true
    try {
      if (showSources) {
        const response = await queryChat({
          question,
          document_ids: documentIds,
          show_sources: true,
          history,
        })
        entries.value.push({
          id: nextId++,
          role: 'assistant',
          content: response.answer,
          sources: response.sources,
          markdown: false,
          ...(response.has_evidence ? {} : { noEvidence: true }),
        })
      } else {
        await sendStreamed(question, documentIds, history)
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
      // Saved only once the answer is complete, failed or stopped: a streaming entry is never
      // stored half-empty.
      storage.save(entries.value)
    }
  }

  // "Nova conversa" (RF-28): clears the messages, hence the history, and the saved
  // conversation. Ignored while an answer is being generated (the button is disabled then).
  function newConversation(): boolean {
    if (generating.value) return false
    entries.value = []
    storage.clear()
    return true
  }

  // Interrupts the in-flight streamed answer (RF-23). A no-op while a JSON answer is being
  // generated or when nothing is in flight.
  function stop(): void {
    controller?.abort()
  }

  return reactive({ entries, generating, send, stop, newConversation })
}
