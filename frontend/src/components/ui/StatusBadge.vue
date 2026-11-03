<script setup lang="ts">
import BaseIcon, { type IconName } from '@/components/ui/BaseIcon.vue'
import { ptBR } from '@/locales/pt-BR'
import type { DocumentStatus } from '@/types/api'

defineProps<{
  status: DocumentStatus
}>()

// Label, color and icon from PRD §5.2: state is never shown by color alone.
const styles: Record<DocumentStatus, { icon: IconName; color: string }> = {
  received: { icon: 'clock', color: 'text-text-secondary' },
  processing: { icon: 'spinner', color: 'text-warning' },
  ready: { icon: 'check', color: 'text-success' },
  failed: { icon: 'alert', color: 'text-danger' },
}
</script>

<template>
  <span
    class="inline-flex items-center gap-1 rounded-full border border-current px-2 py-0.5 text-meta font-medium whitespace-nowrap"
    :class="styles[status].color"
  >
    <BaseIcon :name="styles[status].icon" />
    {{ ptBR.status[status] }}
  </span>
</template>
