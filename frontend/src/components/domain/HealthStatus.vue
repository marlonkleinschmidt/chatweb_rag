<script setup lang="ts">
import { onMounted, ref } from 'vue'

import BaseButton from '@/components/ui/BaseButton.vue'
import BaseIcon from '@/components/ui/BaseIcon.vue'
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
  <div class="flex flex-wrap items-center gap-2 text-meta">
    <!-- Live region holds only the status text; the retry button stays outside it -->
    <div role="status" aria-live="polite">
      <!-- Each state combines color, icon and text -->
      <span v-if="healthState === 'checking'" class="flex items-center gap-1 text-text-secondary">
        <BaseIcon name="spinner" />
        {{ ptBR.health.checking }}
      </span>
      <span v-else-if="healthState === 'connected'" class="flex items-center gap-1 text-success">
        <BaseIcon name="check" />
        {{ ptBR.health.connected }}
      </span>
      <span v-else class="flex items-center gap-1 text-danger">
        <BaseIcon name="alert" />
        {{ ptBR.health.unavailable }}
      </span>
    </div>
    <BaseButton v-if="healthState === 'unavailable'" variant="ghost" @click="checkHealth">
      {{ ptBR.health.retry }}
    </BaseButton>
  </div>
</template>
