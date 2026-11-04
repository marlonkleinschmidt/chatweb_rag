<script setup lang="ts">
import { useId } from 'vue'

import BaseIcon from '@/components/ui/BaseIcon.vue'
import { ptBR } from '@/locales/pt-BR'
import type { Source } from '@/types/api'

withDefaults(
  defineProps<{
    source: Source
    // The document was removed after this answer; the source stays visible, flagged.
    removed?: boolean
  }>(),
  { removed: false },
)

// Excerpt visibility; ChatMessage opens it when the matching [n] is clicked.
const expanded = defineModel<boolean>('expanded', { default: false })

const excerptId = useId()
</script>

<template>
  <!-- tabindex -1: receives focus programmatically when its [n] citation is clicked -->
  <article
    tabindex="-1"
    class="rounded-panel border border-border bg-chat-canvas p-3 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
  >
    <div class="flex items-start gap-2">
      <span class="text-sm font-semibold text-accent" aria-hidden="true">[{{ source.index }}]</span>
      <span class="sr-only">{{ ptBR.sources.label(source.index) }}</span>
      <div class="min-w-0 flex-1">
        <p class="text-sm font-semibold break-words text-text-primary">{{ source.filename }}</p>
        <p v-if="source.page !== null" class="text-meta text-text-secondary">
          {{ ptBR.sources.page(source.page) }}
        </p>
        <p
          v-if="removed"
          class="mt-1 inline-flex items-center gap-1 rounded-full border border-current px-2 py-0.5 text-meta font-medium text-text-secondary"
        >
          <BaseIcon name="error" />
          {{ ptBR.sources.removed }}
        </p>
      </div>
    </div>
    <button
      type="button"
      class="mt-2 inline-flex min-h-10 items-center gap-1 rounded-control px-2 text-sm font-semibold text-text-secondary hover:bg-border hover:text-text-primary focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus"
      :aria-expanded="expanded ? 'true' : 'false'"
      :aria-controls="excerptId"
      @click="expanded = !expanded"
    >
      <BaseIcon
        name="chevron-down"
        class="transition-transform motion-reduce:transition-none"
        :class="{ 'rotate-180': expanded }"
      />
      {{ expanded ? ptBR.sources.hideExcerpt : ptBR.sources.showExcerpt }}
    </button>
    <!-- v-text: no template whitespace leaks into the pre-wrap text -->
    <p
      v-show="expanded"
      :id="excerptId"
      class="mt-2 text-meta whitespace-pre-wrap break-words text-text-secondary"
      v-text="source.excerpt"
    />
  </article>
</template>
