// Frontend settings from VITE_* variables. Fallbacks are the PRD §3 defaults, kept only here.

function positiveInt(value: string | undefined, fallback: number): number {
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback
}

export const config = {
  pollIntervalMs: positiveInt(import.meta.env.VITE_POLL_INTERVAL_MS, 2000),
  // Must match MAX_DOCUMENTS_PER_QUERY in the backend; the API rejects larger selections.
  maxDocumentsPerQuery: positiveInt(import.meta.env.VITE_MAX_DOCUMENTS_PER_QUERY, 10),
  // Same fixed minimum as the backend (MIN_QUESTION_CHARS); the maximum mirrors MAX_QUESTION_CHARS.
  minQuestionChars: 3,
  maxQuestionChars: positiveInt(import.meta.env.VITE_MAX_QUESTION_CHARS, 2000),
} as const
