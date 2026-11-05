<script setup lang="ts">
import { computed, useAttrs, useId, useTemplateRef, watch } from 'vue'

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
    // Auto-grow ceiling in lines for textareas (0 = no ceiling). The field starts at `rows`
    // and then grows with its content up to this limit.
    maxRows?: number
    labelHidden?: boolean
    // Extra classes merged into the control itself. When set, the default `bg-transparent` is
    // omitted so the two background utilities never compete in the generated CSS and the
    // control background comes deterministically from this prop.
    controlClass?: string
  }>(),
  {
    as: 'input',
    hint: '',
    error: '',
    rows: 3,
    maxRows: 0,
    labelHidden: false,
    controlClass: '',
  },
)

const model = defineModel<string>({ default: '' })

const controlId = useId()
const hintId = `${controlId}-hint`
const errorId = `${controlId}-error`

const attrs = useAttrs()

// The parent may point at content rendered outside the field (the chat hint lives in the action
// row), so the control keeps the external id and appends the internal hint/error ids, in that
// order. This binding comes after `v-bind="$attrs"` in the template, so it replaces the raw
// attribute instead of duplicating it.
const describedBy = computed(() => {
  const external = typeof attrs['aria-describedby'] === 'string' ? attrs['aria-describedby'] : ''
  const ids = [external, props.hint ? hintId : '', props.error ? errorId : ''].filter(Boolean)
  return ids.length > 0 ? ids.join(' ') : undefined
})

const controlClasses = computed(() =>
  [
    'min-h-12 w-full resize-none rounded-control border border-transparent px-3 py-2 text-body text-text-primary placeholder:text-text-secondary focus:border-focus focus:outline-none focus:ring-1 focus:ring-focus disabled:cursor-not-allowed disabled:opacity-60',
    props.controlClass ? '' : 'bg-transparent',
  ]
    .filter(Boolean)
    .join(' '),
)

const control = useTemplateRef<HTMLInputElement | HTMLTextAreaElement>('control')

function focus(): void {
  control.value?.focus()
}

defineExpose({ focus })

// Auto-grow: a textarea sizes to its content (the chat question field grows with the text) and
// stops at `maxRows` lines, clipping internally; the control classes keep the `min-h-12` floor.
// Inputs keep their fixed height, so they are skipped.
watch(
  () => model.value,
  () => {
    const element = control.value
    if (!element || props.as !== 'textarea') return
    element.style.height = 'auto'
    let height = element.scrollHeight
    if (props.maxRows > 0) {
      const lineHeight = parseFloat(window.getComputedStyle(element).lineHeight)
      height = Math.min(height, props.maxRows * lineHeight)
    }
    element.style.height = `${height}px`
  },
)
</script>

<template>
  <div class="flex flex-col gap-1">
    <label
      :for="controlId"
      :class="props.labelHidden ? 'sr-only' : 'text-sm font-semibold text-text-primary'"
      >{{ label }}</label
    >
    <textarea
      v-if="as === 'textarea'"
      :id="controlId"
      ref="control"
      v-model="model"
      v-bind="$attrs"
      :rows="rows"
      :aria-describedby="describedBy"
      :aria-invalid="error ? 'true' : undefined"
      :class="[controlClasses, props.controlClass, error ? 'border-danger' : 'border-control-border', 'resize-none']"
    />
    <input
      v-else
      :id="controlId"
      ref="control"
      v-model="model"
      v-bind="$attrs"
      :aria-describedby="describedBy"
      :aria-invalid="error ? 'true' : undefined"
      :class="[controlClasses, props.controlClass, error ? 'border-danger' : 'border-control-border']"
    />
    <p v-if="hint" :id="hintId" class="text-meta text-text-secondary">{{ hint }}</p>
    <p v-if="error" :id="errorId" class="flex items-start gap-1 text-meta text-danger">
      <BaseIcon name="error" class="mt-0.5" />
      <span>{{ error }}</span>
    </p>
  </div>
</template>
