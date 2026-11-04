import { reactive, ref } from 'vue'

const STORAGE_KEY = 'show_sources'

function readStoredValue(): boolean {
  try {
    // Absent or invalid values fall back to the default (on); only a stored 'false' is off.
    return localStorage.getItem(STORAGE_KEY) !== 'false'
  } catch {
    // Storage blocked (e.g. private mode): the first visit behaves as "on" (RF-20).
    return true
  }
}

// "Exibir fontes" preference (RF-20, PRD §12.8 decision 7): default on, persisted per
// browser in localStorage with a silent fallback, in the same pattern as useTheme (RF-19).
// It only affects new questions: entries already in the session keep the sources they had.
export function useShowSources() {
  const showSources = ref(readStoredValue())

  function setShowSources(value: boolean): void {
    showSources.value = value
    try {
      localStorage.setItem(STORAGE_KEY, String(value))
    } catch {
      // Storage blocked: the choice still applies to this session.
    }
  }

  return reactive({ showSources, setShowSources })
}
