<script setup lang="ts">
import { computed } from 'vue'

import BaseIcon from '@/components/ui/BaseIcon.vue'

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger'

const props = withDefaults(
  defineProps<{
    variant?: ButtonVariant
    type?: 'button' | 'submit'
    loading?: boolean
    disabled?: boolean
  }>(),
  {
    variant: 'secondary',
    type: 'button',
    loading: false,
    disabled: false,
  },
)

// Colors are semantic tokens; measured contrast is in PRD §9.1 (README > Decisões > Sprint 4, 4.9).
const variantClasses: Record<ButtonVariant, string> = {
  primary: 'border border-transparent bg-primary text-on-primary enabled:hover:bg-primary-hover',
  secondary: 'border border-control-border text-text-primary enabled:hover:bg-border',
  ghost:
    'border border-transparent text-text-secondary enabled:hover:bg-border enabled:hover:text-text-primary',
  danger: 'border border-transparent bg-danger text-on-danger enabled:hover:brightness-110',
}

const isDisabled = computed(() => props.disabled || props.loading)
</script>

<template>
  <button
    :type="type"
    :disabled="isDisabled"
    :aria-busy="loading ? 'true' : undefined"
    class="inline-flex min-h-10 items-center justify-center gap-2 rounded-control px-4 text-sm font-semibold focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus disabled:cursor-not-allowed disabled:opacity-60"
    :class="variantClasses[variant]"
  >
    <BaseIcon v-if="loading" name="spinner" />
    <slot />
  </button>
</template>
