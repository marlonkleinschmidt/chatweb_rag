<script setup lang="ts">
import BaseIcon, { type IconName } from '@/components/ui/BaseIcon.vue'

export type AlertVariant = 'info' | 'success' | 'warning' | 'error'

withDefaults(
  defineProps<{
    variant?: AlertVariant
  }>(),
  { variant: 'info' },
)

const styles: Record<AlertVariant, { icon: IconName; color: string }> = {
  info: { icon: 'info', color: 'border-accent text-accent' },
  success: { icon: 'check', color: 'border-success text-success' },
  warning: { icon: 'alert', color: 'border-warning text-warning' },
  error: { icon: 'error', color: 'border-danger text-danger' },
}
</script>

<template>
  <!-- role='alert' only for errors (PRD §9.3); the other variants are polite status messages -->
  <div
    :role="variant === 'error' ? 'alert' : 'status'"
    class="flex items-start gap-2 rounded-panel border border-l-4 bg-surface px-3 py-2"
    :class="styles[variant].color"
  >
    <BaseIcon :name="styles[variant].icon" class="mt-0.5" />
    <div class="min-w-0 text-sm break-words text-text-primary">
      <slot />
    </div>
  </div>
</template>
