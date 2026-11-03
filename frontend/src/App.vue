<script setup lang="ts">
import { onMounted, ref } from 'vue'

import { ptBR } from '@/locales/pt-BR'
import { getHealth } from '@/services/api'

type HealthState = 'checking' | 'connected' | 'unavailable'

const healthState = ref<HealthState>('checking')

async function checkHealth(): Promise<void> {
  healthState.value = 'checking'
  try {
    const health = await getHealth()
    healthState.value = health.status === 'ok' ? 'connected' : 'unavailable'
  } catch {
    healthState.value = 'unavailable'
  }
}

onMounted(checkHealth)
</script>

<template>
  <main class="mx-auto flex min-h-screen max-w-3xl flex-col gap-6 px-4 py-8">
    <h1 class="text-2xl font-bold">{{ ptBR.app.title }}</h1>

    <div class="flex flex-wrap items-center gap-3 rounded-xl border border-border bg-surface p-4">
      <!-- Live region holds only the status text; the retry button stays outside it -->
      <div role="status" aria-live="polite">
        <!-- Each state combines color, icon and text -->
        <span v-if="healthState === 'checking'" class="flex items-center gap-2 text-text-secondary">
          <svg
            class="size-4 animate-spin"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            aria-hidden="true"
          >
            <path d="M12 3a9 9 0 1 0 9 9" stroke-linecap="round" />
          </svg>
          {{ ptBR.health.checking }}
        </span>
        <span v-else-if="healthState === 'connected'" class="flex items-center gap-2 text-success">
          <svg
            class="size-4"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            aria-hidden="true"
          >
            <path d="m5 12 5 5 9-10" stroke-linecap="round" stroke-linejoin="round" />
          </svg>
          {{ ptBR.health.connected }}
        </span>
        <span v-else class="flex items-center gap-2 text-danger">
          <svg
            class="size-4"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            stroke-width="2"
            aria-hidden="true"
          >
            <path
              d="M12 8v5m0 3.5v.5M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"
              stroke-linecap="round"
              stroke-linejoin="round"
            />
          </svg>
          {{ ptBR.health.unavailable }}
        </span>
      </div>

      <button
        v-if="healthState === 'unavailable'"
        type="button"
        class="ml-auto min-h-10 rounded-lg border border-text-muted px-4 text-sm font-semibold text-text-primary hover:bg-surface-raised focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-primary"
        @click="checkHealth"
      >
        {{ ptBR.health.retry }}
      </button>
    </div>
  </main>
</template>
