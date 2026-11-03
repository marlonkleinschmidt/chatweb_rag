<script setup lang="ts">
import { computed, useId, useTemplateRef } from 'vue'

import BaseIcon from '@/components/ui/BaseIcon.vue'

// Extra attributes (placeholder, maxlength, required, @keydown...) go to the control, not the wrapper.
defineOptions({ inheritAttrs: false })

const props = withDefaults(
  defineProps<{
    as?: 'input' | 'textarea'
    label: string
    hint?: string
    error?: string
    rows?: number
  }>(),
  {
    as: 'input',
    hint: '',
    error: '',
    rows: 3,
  },
)

const model = defineModel<string>({ default: '' })

const controlId = useId()
const hintId = `${controlId}-hint`
const errorId = `${controlId}-error`

const describedBy = computed(() => {
  const ids = [props.hint ? hintId : '', props.error ? errorId : ''].filter(Boolean)
  return ids.length > 0 ? ids.join(' ') : undefined
})

const controlClasses =
  'w-full rounded-control border bg-surface-raised px-3 py-2 text-body text-text-primary placeholder:text-text-secondary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus disabled:cursor-not-allowed disabled:opacity-60'

const control = useTemplateRef<HTMLInputElement | HTMLTextAreaElement>('control')

function focus(): void {
  control.value?.focus()
}

defineExpose({ focus })
</script>

<template>
  <div class="flex flex-col gap-1">
    <label :for="controlId" class="text-sm font-semibold text-text-primary">{{ label }}</label>
    <textarea
      v-if="as === 'textarea'"
      :id="controlId"
      ref="control"
      v-model="model"
      v-bind="$attrs"
      :rows="rows"
      :aria-describedby="describedBy"
      :aria-invalid="error ? 'true' : undefined"
      :class="[controlClasses, error ? 'border-danger' : 'border-control-border', 'resize-y']"
    />
    <input
      v-else
      :id="controlId"
      ref="control"
      v-model="model"
      v-bind="$attrs"
      :aria-describedby="describedBy"
      :aria-invalid="error ? 'true' : undefined"
      :class="[controlClasses, error ? 'border-danger' : 'border-control-border']"
    />
    <p v-if="hint" :id="hintId" class="text-meta text-text-secondary">{{ hint }}</p>
    <p v-if="error" :id="errorId" class="flex items-start gap-1 text-meta text-danger">
      <BaseIcon name="error" class="mt-0.5" />
      <span>{{ error }}</span>
    </p>
  </div>
</template>
