import { computed, onScopeDispose, reactive, ref } from 'vue'

import { config } from '@/config'
import { ptBR } from '@/locales/pt-BR'
import { ApiError, deleteDocument, listDocuments, uploadDocument } from '@/services/api'
import type { Document } from '@/types/api'

export interface Notice {
  variant: 'success' | 'warning'
  text: string
}

function errorMessage(error: unknown): string {
  // ApiError messages are pt-BR: the API envelope message or a frontend locale text.
  return error instanceof ApiError ? error.message : ptBR.errors.unexpected
}

function isPending(document: Document): boolean {
  return document.status === 'received' || document.status === 'processing'
}

// Document catalog: list, polling, upload, removal and the selection used by the chat.
// Returns a reactive object so it can be passed to the panels as a single prop.
export function useDocuments() {
  const documents = ref<Document[]>([])
  const loaded = ref(false)
  const loading = ref(false)
  const loadError = ref<string | null>(null)
  const embeddingModelChanged = ref(false)

  const uploading = ref(false)
  const uploadError = ref<string | null>(null)
  const uploadNotice = ref<Notice | null>(null)

  const removingId = ref<string | null>(null)
  const removeError = ref<string | null>(null)

  const selectedIds = ref<string[]>([])

  // Documents removed during this session: removed by the user, or gone from the list after a
  // successful load. A failed load never adds anything. The chat uses it to flag old sources.
  const removedIds = ref<Set<string>>(new Set())

  function markRemoved(id: string): void {
    removedIds.value.add(id)
  }

  let pollTimer: ReturnType<typeof setTimeout> | null = null
  let disposed = false

  function stopPolling(): void {
    if (pollTimer !== null) {
      clearTimeout(pollTimer)
      pollTimer = null
    }
  }

  // One timer at most: every load clears the previous one and schedules the next only while
  // some document is still received/processing.
  function schedulePolling(): void {
    stopPolling()
    if (disposed || !documents.value.some(isPending)) return
    pollTimer = setTimeout(() => void load(), config.pollIntervalMs)
  }

  // Keeps only documents that still exist and are ready.
  function pruneSelection(): void {
    const ready = new Set(documents.value.filter((d) => d.status === 'ready').map((d) => d.id))
    const kept = selectedIds.value.filter((id) => ready.has(id))
    if (kept.length !== selectedIds.value.length) selectedIds.value = kept
  }

  async function load(): Promise<void> {
    stopPolling()
    loading.value = true
    try {
      const response = await listDocuments()
      const current = new Set(response.items.map((d) => d.id))
      for (const d of documents.value) if (!current.has(d.id)) markRemoved(d.id)
      documents.value = response.items
      embeddingModelChanged.value = response.embedding_model_changed
      loadError.value = null
      loaded.value = true
      pruneSelection()
      schedulePolling()
    } catch (error) {
      // Polling stops on error; "Tentar novamente" calls load() again.
      loadError.value = errorMessage(error)
    } finally {
      loading.value = false
    }
  }

  function clearMessages(): void {
    uploadError.value = null
    uploadNotice.value = null
    removeError.value = null
  }

  async function upload(file: File): Promise<boolean> {
    clearMessages()
    // Client-side checks (PRD §4.4); size, signature and encryption are checked by the API.
    if (!file.name.toLowerCase().endsWith('.pdf')) {
      uploadError.value = ptBR.upload.notPdf
      return false
    }
    if (file.size === 0) {
      uploadError.value = ptBR.upload.empty
      return false
    }
    uploading.value = true
    try {
      const response = await uploadDocument(file)
      uploadNotice.value = response.warning
        ? { variant: 'warning', text: response.warning }
        : { variant: 'success', text: ptBR.upload.accepted }
      await load()
      return true
    } catch (error) {
      uploadError.value = errorMessage(error)
      return false
    } finally {
      uploading.value = false
    }
  }

  async function remove(id: string): Promise<boolean> {
    clearMessages()
    removingId.value = id
    try {
      await deleteDocument(id)
      markRemoved(id)
      documents.value = documents.value.filter((d) => d.id !== id)
      pruneSelection()
      return true
    } catch (error) {
      // 404: it was already removed, so the list refresh below is enough.
      if (error instanceof ApiError && error.code === 'document_not_found') {
        markRemoved(id)
        await load()
        return true
      }
      removeError.value = errorMessage(error)
      await load()
      return false
    } finally {
      removingId.value = null
    }
  }

  const selectionFull = computed(() => selectedIds.value.length >= config.maxDocumentsPerQuery)

  function isRemoved(id: string): boolean {
    return removedIds.value.has(id)
  }

  function isSelected(id: string): boolean {
    return selectedIds.value.includes(id)
  }

  function setSelected(id: string, selected: boolean): void {
    if (!selected) {
      selectedIds.value = selectedIds.value.filter((item) => item !== id)
      return
    }
    const document = documents.value.find((d) => d.id === id)
    if (!document || document.status !== 'ready' || isSelected(id) || selectionFull.value) return
    selectedIds.value = [...selectedIds.value, id]
  }

  onScopeDispose(() => {
    disposed = true
    stopPolling()
  })

  return reactive({
    documents,
    loaded,
    loading,
    loadError,
    embeddingModelChanged,
    uploading,
    uploadError,
    uploadNotice,
    removingId,
    removeError,
    selectedIds,
    selectionFull,
    maxSelected: config.maxDocumentsPerQuery,
    load,
    upload,
    remove,
    isRemoved,
    isSelected,
    setSelected,
  })
}

export type DocumentsStore = ReturnType<typeof useDocuments>
