<script setup lang="ts">
import { nextTick, onBeforeUnmount, onMounted, ref, useId } from 'vue'

import ChatPanel from '@/components/domain/ChatPanel.vue'
import DocumentsPanel from '@/components/domain/DocumentsPanel.vue'
import HealthStatus from '@/components/domain/HealthStatus.vue'
import ThemeToggle from '@/components/domain/ThemeToggle.vue'
import { useDocuments } from '@/composables/useDocuments'
import { ptBR } from '@/locales/pt-BR'

// Shared by both panels: the chat reads the document selection from here.
const documentsStore = useDocuments()
onMounted(() => void documentsStore.load())

type Tab = 'documents' | 'chat'

const tabs: Tab[] = ['documents', 'chat']
const activeTab = ref<Tab>('documents')

const ids = {
  documents: { tab: useId(), panel: useId(), heading: useId() },
  chat: { tab: useId(), panel: useId(), heading: useId() },
}

// Desktop (lg, >= 1024px) shows both panels side by side; below it, the tabs are used.
// CSS decides what is visible; this flag only switches the ARIA roles of the panels.
const desktopQuery = window.matchMedia('(min-width: 64rem)')
const isDesktop = ref(desktopQuery.matches)
function onMediaChange(event: MediaQueryListEvent): void {
  isDesktop.value = event.matches
}
desktopQuery.addEventListener('change', onMediaChange)
onBeforeUnmount(() => desktopQuery.removeEventListener('change', onMediaChange))

// WAI-ARIA tabs pattern with automatic activation: arrows, Home and End move and select.
async function onTabKeydown(event: KeyboardEvent): Promise<void> {
  const current = tabs.indexOf(activeTab.value)
  let next: number
  if (event.key === 'ArrowRight') next = (current + 1) % tabs.length
  else if (event.key === 'ArrowLeft') next = (current - 1 + tabs.length) % tabs.length
  else if (event.key === 'Home') next = 0
  else if (event.key === 'End') next = tabs.length - 1
  else return
  event.preventDefault()
  const tab = tabs[next]
  if (!tab) return
  activeTab.value = tab
  await nextTick()
  document.getElementById(ids[tab].tab)?.focus()
}

// Mobile/tablet: the chat's "Ir para Documentos" switches tab and moves focus to it.
async function goToDocuments(): Promise<void> {
  activeTab.value = 'documents'
  await nextTick()
  document.getElementById(ids.documents.tab)?.focus()
}

function panelAttrs(tab: Tab): Record<string, string | undefined> {
  return isDesktop.value
    ? { role: undefined, 'aria-labelledby': ids[tab].heading }
    : { role: 'tabpanel', 'aria-labelledby': ids[tab].tab }
}
</script>

<template>
  <div class="flex h-dvh flex-col overflow-hidden">
    <header
      class="flex shrink-0 flex-wrap items-center justify-between gap-x-4 gap-y-1 border-b border-border bg-surface px-4 py-3"
    >
      <h1 class="flex items-center gap-2 text-xl font-semibold">
        <!-- Same drawing as public/favicon.svg, inlined so it follows the app theme -->
        <svg
          class="size-5 shrink-0"
          viewBox="0 0 512 512"
          fill="currentColor"
          aria-hidden="true"
          focusable="false"
        >
          <path
            d="M240 382H384A84 84 0 0 0 468 298V126A84 84 0 0 0 384 42H128A84 84 0 0 0 44 126V298A84 84 0 0 0 128 382V440L240 382Z"
            fill="none"
            stroke="currentColor"
            stroke-width="44"
            stroke-linejoin="round"
          />
          <circle cx="160" cy="210" r="32" />
          <circle cx="256" cy="210" r="32" />
          <circle cx="352" cy="210" r="32" />
        </svg>
        {{ ptBR.app.title }}
      </h1>
      <div class="flex items-center gap-2">
        <HealthStatus />
        <ThemeToggle />
      </div>
    </header>

    <!-- Tabs only below lg (mobile and tablet) -->
    <div
      role="tablist"
      :aria-label="ptBR.tabs.label"
      class="flex shrink-0 border-b border-border bg-surface lg:hidden"
    >
      <button
        v-for="tab in tabs"
        :id="ids[tab].tab"
        :key="tab"
        type="button"
        role="tab"
        :aria-selected="activeTab === tab ? 'true' : 'false'"
        :aria-controls="ids[tab].panel"
        :tabindex="activeTab === tab ? 0 : -1"
        class="min-h-12 flex-1 border-b-2 px-4 text-sm font-semibold focus-visible:outline-2 focus-visible:-outline-offset-2 focus-visible:outline-focus"
        :class="
          activeTab === tab
            ? 'border-primary text-text-primary'
            : 'border-transparent text-text-secondary hover:text-text-primary'
        "
        @click="activeTab = tab"
        @keydown="onTabKeydown"
      >
        {{ ptBR.tabs[tab] }}
      </button>
    </div>

    <main class="flex min-h-0 flex-1 flex-col lg:flex-row">
      <section
        :id="ids.documents.panel"
        v-bind="panelAttrs('documents')"
        class="min-h-0 flex-1 flex-col bg-surface lg:flex lg:w-sidebar lg:flex-none lg:border-r lg:border-border"
        :class="activeTab === 'documents' ? 'flex' : 'hidden'"
      >
        <DocumentsPanel :heading-id="ids.documents.heading" :store="documentsStore" />
      </section>
      <section
        :id="ids.chat.panel"
        v-bind="panelAttrs('chat')"
        class="min-h-0 min-w-0 flex-1 flex-col lg:flex"
        :class="activeTab === 'chat' ? 'flex' : 'hidden'"
      >
        <ChatPanel
          :heading-id="ids.chat.heading"
          :store="documentsStore"
          @go-to-documents="goToDocuments"
        />
      </section>
    </main>
  </div>
</template>
