<script setup lang="ts">
import { computed, useId } from 'vue'

import BaseButton from '@/components/ui/BaseButton.vue'
import StatusBadge from '@/components/ui/StatusBadge.vue'
import { ptBR } from '@/locales/pt-BR'
import type { Document } from '@/types/api'

// Renders an <li>: the parent must wrap the items in a <ul>.
const props = withDefaults(
  defineProps<{
    document: Document
    // True when the selection limit was reached and this item is not selected (RF-09).
    selectionDisabled?: boolean
    removing?: boolean
  }>(),
  {
    selectionDisabled: false,
    removing: false,
  },
)

const selected = defineModel<boolean>('selected', { default: false })

const emit = defineEmits<{
  remove: [id: string]
}>()

const checkboxId = useId()

const isReady = computed(() => props.document.status === 'ready')
// Documents in received/processing cannot be removed (API answers 409), so no button is shown.
const canRemove = computed(
  () => props.document.status === 'ready' || props.document.status === 'failed',
)

const dateFormatter = new Intl.DateTimeFormat('pt-BR', {
  timeZone: 'America/Sao_Paulo',
  day: '2-digit',
  month: '2-digit',
  year: 'numeric',
  hour: '2-digit',
  minute: '2-digit',
  hourCycle: 'h23',
})

// dd/MM/yyyy HH:mm in America/Sao_Paulo (PRD §3), built from parts to avoid the locale comma.
const sentAt = computed(() => {
  const date = new Date(props.document.created_at)
  if (Number.isNaN(date.getTime())) return ''
  const part = (type: Intl.DateTimeFormatPartTypes): string =>
    dateFormatter.formatToParts(date).find((item) => item.type === type)?.value ?? ''
  return `${part('day')}/${part('month')}/${part('year')} ${part('hour')}:${part('minute')}`
})
</script>

<template>
  <li
    class="flex items-start gap-3 rounded-panel border bg-surface p-3"
    :class="selected ? 'border-primary' : 'border-border'"
  >
    <!-- RF-09: every item has a checkbox, enabled only for ready documents -->
    <input
      :id="checkboxId"
      v-model="selected"
      type="checkbox"
      class="mt-1 size-4 shrink-0 accent-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus disabled:cursor-not-allowed"
      :disabled="!isReady || (selectionDisabled && !selected)"
      :aria-label="ptBR.documents.selectLabel(document.filename)"
    />
    <div class="flex min-w-0 flex-1 flex-col gap-1">
      <label
        :for="checkboxId"
        class="text-sm font-semibold break-words text-text-primary"
        :class="isReady ? 'cursor-pointer' : 'cursor-default'"
      >
        {{ document.filename }}
      </label>
      <p class="text-meta text-text-secondary">
        <time :datetime="document.created_at">{{ ptBR.documents.sentAt(sentAt) }}</time>
      </p>
      <div>
        <StatusBadge :status="document.status" />
      </div>
      <p v-if="document.status === 'failed'" class="text-meta break-words text-danger">
        {{ document.error_message ?? ptBR.errors.unexpected }}
      </p>
    </div>
    <BaseButton
      v-if="canRemove"
      variant="ghost"
      class="shrink-0"
      :loading="removing"
      :aria-label="ptBR.documents.removeLabel(document.filename)"
      @click="emit('remove', document.id)"
    >
      {{ ptBR.documents.remove }}
    </BaseButton>
  </li>
</template>
