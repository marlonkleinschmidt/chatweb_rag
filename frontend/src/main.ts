import { createApp } from 'vue'

import App from './App.vue'
import './style.css'

createApp(App).mount('#app')

// Turns on the global color transition only after the first paint (see style.css).
requestAnimationFrame(() =>
  requestAnimationFrame(() => document.documentElement.classList.add('color-transitions')),
)
