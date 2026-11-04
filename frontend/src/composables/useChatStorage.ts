import type { ChatEntry } from '@/composables/useChat'
import type { Source } from '@/types/api'

const STORAGE_KEY = 'chat_history'
const STORAGE_VERSION = 1
// RF-29: only the most recent entries are kept; the oldest ones leave first.
export const MAX_STORED_ENTRIES = 50

// Entries are stored without their id: ids are reassigned on load (1..n), so restored entries
// never collide with the ones created afterwards (useChat continues from n + 1).
type StoredEntry = ChatEntry extends infer Entry
  ? Entry extends unknown
    ? Omit<Entry, 'id'>
    : never
  : never

interface StoredChat {
  version: typeof STORAGE_VERSION
  entries: StoredEntry[]
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function parseSource(value: unknown): Source | null {
  if (!isRecord(value)) return null
  const { index, document_id, filename, page, excerpt } = value
  if (
    typeof index !== 'number' ||
    !Number.isInteger(index) ||
    typeof document_id !== 'string' ||
    typeof filename !== 'string' ||
    !(page === null || (typeof page === 'number' && Number.isInteger(page))) ||
    typeof excerpt !== 'string'
  ) {
    return null
  }
  return { index, document_id, filename, page, excerpt }
}

function optionalFlag(value: unknown): boolean | null {
  if (value === undefined) return false
  return typeof value === 'boolean' ? value : null
}

// Rebuilds one entry with only the known fields; null when its shape is invalid.
function parseEntry(value: unknown, id: number): ChatEntry | null {
  if (!isRecord(value) || typeof value.content !== 'string') return null
  const { role, content } = value
  if (role === 'user' || role === 'error') return { id, role, content }
  if (role !== 'assistant' || typeof value.markdown !== 'boolean') return null
  if (!Array.isArray(value.sources)) return null
  const sources: Source[] = []
  for (const item of value.sources) {
    const source = parseSource(item)
    if (!source) return null
    sources.push(source)
  }
  const noEvidence = optionalFlag(value.noEvidence)
  const interrupted = optionalFlag(value.interrupted)
  if (noEvidence === null || interrupted === null) return null
  return {
    id,
    role,
    content,
    sources,
    markdown: value.markdown,
    // Flags only when set, the same shape useChat creates.
    ...(noEvidence ? { noEvidence: true } : {}),
    ...(interrupted ? { interrupted: true } : {}),
  }
}

function parseStored(raw: string): ChatEntry[] {
  let data: unknown
  try {
    data = JSON.parse(raw)
  } catch {
    return []
  }
  // Unknown version or shape: discarded silently (RF-29).
  if (!isRecord(data) || data.version !== STORAGE_VERSION || !Array.isArray(data.entries)) {
    return []
  }
  const entries: ChatEntry[] = []
  for (const item of data.entries.slice(-MAX_STORED_ENTRIES)) {
    const entry = parseEntry(item, entries.length + 1)
    if (!entry) return []
    entries.push(entry)
  }
  return entries
}

function toStored(entry: ChatEntry): StoredEntry {
  if (entry.role !== 'assistant') return { role: entry.role, content: entry.content }
  return {
    role: entry.role,
    content: entry.content,
    sources: entry.sources,
    markdown: entry.markdown,
    ...(entry.noEvidence ? { noEvidence: true } : {}),
    ...(entry.interrupted ? { interrupted: true } : {}),
  }
}

// Conversation saved in this browser (RF-29, PRD §13.8 decision 8), in the same pattern as
// useTheme (RF-19) and useShowSources (RF-20): localStorage with a silent fallback. A blocked
// or corrupted storage opens an empty chat; the conversation still works for the visit.
export function useChatStorage() {
  function load(): ChatEntry[] {
    try {
      const raw = localStorage.getItem(STORAGE_KEY)
      return raw === null ? [] : parseStored(raw)
    } catch {
      return []
    }
  }

  function save(entries: readonly ChatEntry[]): void {
    const data: StoredChat = {
      version: STORAGE_VERSION,
      entries: entries.slice(-MAX_STORED_ENTRIES).map(toStored),
    }
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(data))
    } catch {
      // Storage blocked or full: the conversation stays only in memory.
    }
  }

  // "Nova conversa" (RF-28) removes the key, not just its entries.
  function clear(): void {
    try {
      localStorage.removeItem(STORAGE_KEY)
    } catch {
      // Storage blocked: nothing was saved.
    }
  }

  return { load, save, clear }
}
