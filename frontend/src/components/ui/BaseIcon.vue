<script setup lang="ts">
// Decorative stroke icon (always aria-hidden). The meaning must come from nearby text.
export type IconName =
  'alert' | 'check' | 'chevron-down' | 'clock' | 'error' | 'info' | 'moon' | 'spinner' | 'sun'

defineProps<{
  name: IconName
}>()

const paths: Record<IconName, string[]> = {
  alert: [
    'M12 8v5m0 3.5v.5',
    'M10.3 3.9 2.4 18a2 2 0 0 0 1.7 3h15.8a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z',
  ],
  check: ['m5 12 5 5 9-10'],
  'chevron-down': ['m6 9 6 6 6-6'],
  clock: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z', 'M12 7v5l3 2'],
  error: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z', 'm9 9 6 6m0-6-6 6'],
  info: ['M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18Z', 'M12 11v5m0-8.5v.5'],
  moon: ['M20 14.5A8 8 0 0 1 9.5 4a8 8 0 1 0 10.5 10.5Z'],
  spinner: ['M12 3a9 9 0 1 0 9 9'],
  sun: [
    'M12 16a4 4 0 1 0 0-8 4 4 0 0 0 0 8Z',
    'M12 2v2m0 16v2M4.9 4.9l1.4 1.4m11.4 11.4 1.4 1.4M2 12h2m16 0h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4',
  ],
}
</script>

<template>
  <svg
    class="size-4 shrink-0"
    :class="{ 'animate-spin motion-reduce:animate-none': name === 'spinner' }"
    viewBox="0 0 24 24"
    fill="none"
    stroke="currentColor"
    stroke-width="2"
    stroke-linecap="round"
    stroke-linejoin="round"
    aria-hidden="true"
    focusable="false"
  >
    <path v-for="d in paths[name]" :key="d" :d="d" />
  </svg>
</template>
