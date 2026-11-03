import { reactive, ref } from 'vue'

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'theme'

// Theme choice (RF-19, PRD §9.4). The inline script in index.html applies the first theme
// before the app loads, so the current class on <html> is the source of the initial state.
export function useTheme() {
  const root = document.documentElement
  const theme = ref<Theme>(root.classList.contains('dark') ? 'dark' : 'light')

  function setTheme(value: Theme): void {
    theme.value = value
    root.classList.toggle('dark', value === 'dark')
    try {
      localStorage.setItem(STORAGE_KEY, value)
    } catch {
      // Storage blocked (e.g. private mode): the theme still applies for this visit.
    }
  }

  function toggle(): void {
    setTheme(theme.value === 'dark' ? 'light' : 'dark')
  }

  return reactive({ theme, toggle })
}
