<script setup lang="ts">
import { onMounted, useId, useTemplateRef, watch } from 'vue'

import BaseButton from '@/components/ui/BaseButton.vue'
import { ptBR } from '@/locales/pt-BR'

// Native <dialog> opened with showModal(): the browser makes the rest of the page inert
// (focus stays inside) and fires `cancel` on Esc. The parent controls `open`.
const props = withDefaults(
  defineProps<{
    open: boolean
    title: string
    message: string
    confirmLabel: string
    cancelLabel?: string
    loading?: boolean
  }>(),
  {
    cancelLabel: ptBR.dialog.cancel,
    loading: false,
  },
)

const emit = defineEmits<{
  confirm: []
  cancel: []
}>()

const titleId = useId()
const messageId = useId()
const dialog = useTemplateRef<HTMLDialogElement>('dialog')

// Element that had focus when the dialog opened; focus goes back to it on close.
let opener: HTMLElement | null = null

function sync(open: boolean): void {
  const el = dialog.value
  if (!el) return
  if (open && !el.open) {
    opener = document.activeElement instanceof HTMLElement ? document.activeElement : null
    el.showModal()
  } else if (!open && el.open) {
    el.close()
  }
}

onMounted(() => sync(props.open))
watch(
  () => props.open,
  (open) => sync(open),
)

function onCancel(event: Event): void {
  // Esc: keep the dialog under the parent's control instead of closing it here.
  event.preventDefault()
  if (!props.loading) emit('cancel')
}

// showModal() lets Tab leave the page for the browser UI; wrap it so focus stays in the dialog.
function onKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Tab' || !dialog.value) return
  const focusable = Array.from(dialog.value.querySelectorAll<HTMLElement>('button:not([disabled])'))
  const first = focusable[0]
  const last = focusable[focusable.length - 1]
  if (!first || !last) {
    event.preventDefault()
    return
  }
  const active = document.activeElement
  const inside = active instanceof Node && dialog.value.contains(active)
  if (event.shiftKey && (active === first || !inside)) {
    event.preventDefault()
    last.focus()
  } else if (!event.shiftKey && (active === last || !inside)) {
    event.preventDefault()
    first.focus()
  }
}

function onClose(): void {
  // The browser may still force-close (e.g. repeated Esc); keep the parent state in sync.
  if (props.open) emit('cancel')
  if (opener?.isConnected) opener.focus()
  opener = null
}
</script>

<template>
  <dialog
    ref="dialog"
    :aria-labelledby="titleId"
    :aria-describedby="messageId"
    class="m-auto w-[calc(100%-2rem)] max-w-md rounded-panel border border-border bg-surface-raised p-6 text-text-primary backdrop:bg-canvas/80"
    @cancel="onCancel"
    @close="onClose"
    @keydown="onKeydown"
  >
    <h2 :id="titleId" class="text-lg font-semibold">{{ title }}</h2>
    <p :id="messageId" class="mt-2 text-sm break-words text-text-secondary">{{ message }}</p>
    <div class="mt-6 flex flex-wrap justify-end gap-3">
      <!-- autofocus: the safe action receives the initial focus -->
      <BaseButton variant="secondary" autofocus :disabled="loading" @click="emit('cancel')">
        {{ cancelLabel }}
      </BaseButton>
      <BaseButton variant="danger" :loading="loading" @click="emit('confirm')">
        {{ confirmLabel }}
      </BaseButton>
    </div>
  </dialog>
</template>
