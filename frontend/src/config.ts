// Frontend settings from VITE_* variables. Fallbacks are the PRD §3 defaults, kept only here.

function positiveInt(value: string | undefined, fallback: number): number {
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback
}

// Like positiveInt, but 0 is valid (it turns the feature off). Empty or invalid values
// fall back to the default.
function nonNegativeInt(value: string | undefined, fallback: number): number {
  if (value === undefined || value.trim() === '') return fallback
  const parsed = Number(value)
  return Number.isInteger(parsed) && parsed >= 0 ? parsed : fallback
}

export const config = {
  pollIntervalMs: positiveInt(import.meta.env.VITE_POLL_INTERVAL_MS, 2000),
  // Must match MAX_DOCUMENTS_PER_QUERY in the backend; the API rejects larger selections.
  maxDocumentsPerQuery: positiveInt(import.meta.env.VITE_MAX_DOCUMENTS_PER_QUERY, 10),
  // Same fixed minimum as the backend (MIN_QUESTION_CHARS); the maximum mirrors MAX_QUESTION_CHARS.
  minQuestionChars: 3,
  maxQuestionChars: positiveInt(import.meta.env.VITE_MAX_QUESTION_CHARS, 2000),
  // Conversation history limits (RF-25), mirrors of MAX_HISTORY_TURNS / MAX_HISTORY_CHARS in
  // the backend, which answers 422 history_invalid above them. 0 sends `history: []`.
  maxHistoryTurns: nonNegativeInt(import.meta.env.VITE_MAX_HISTORY_TURNS, 4),
  maxHistoryChars: nonNegativeInt(import.meta.env.VITE_MAX_HISTORY_CHARS, 4000),
} as const
