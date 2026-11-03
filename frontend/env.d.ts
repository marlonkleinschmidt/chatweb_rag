/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_BASE_URL?: string
  readonly VITE_POLL_INTERVAL_MS?: string
  readonly VITE_MAX_DOCUMENTS_PER_QUERY?: string
  readonly VITE_MAX_QUESTION_CHARS?: string
}

interface ImportMeta {
  readonly env: ImportMetaEnv
}
