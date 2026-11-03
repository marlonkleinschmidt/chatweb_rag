<script setup lang="ts">
import { computed, nextTick, ref, useId } from 'vue'

import SourceCard from '@/components/domain/SourceCard.vue'
import { ptBR } from '@/locales/pt-BR'
import type { Source } from '@/types/api'

const props = withDefaults(
  defineProps<{
    role: 'user' | 'assistant'
    content: string
    sources?: Source[]
    // Tells whether a source's document was removed after the answer (flag shown on the card).
    isRemoved?: (documentId: string) => boolean
  }>(),
  { sources: () => [], isRemoved: () => false },
)

type Segment = { kind: 'text'; text: string } | { kind: 'cite'; index: number }

// Splits the answer into plain text and [n] markers. A marker only becomes a button when
// the API returned a source with that index; otherwise it stays as text. No v-html.
const segments = computed<Segment[]>(() => {
  if (props.role === 'user') return [{ kind: 'text', text: props.content }]
  const known = new Set(props.sources.map((source) => source.index))
  const result: Segment[] = []
  let last = 0
  for (const match of props.content.matchAll(/\[(\d+)\]/g)) {
    const index = Number(match[1])
    if (!known.has(index)) continue
    if (match.index > last)
      result.push({ kind: 'text', text: props.content.slice(last, match.index) })
    result.push({ kind: 'cite', index })
    last = match.index + match[0].length
  }
  if (last < props.content.length) result.push({ kind: 'text', text: props.content.slice(last) })
  return result
})

const baseId = useId()
const sourceId = (index: number): string => `${baseId}-source-${index}`

const expanded = ref<Record<number, boolean>>({})

async function goToSource(index: number): Promise<void> {
  expanded.value[index] = true
  await nextTick()
  const card = document.getElementById(sourceId(index))
  if (!card) return
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
  card.scrollIntoView({ behavior: reduceMotion ? 'auto' : 'smooth', block: 'nearest' })
  card.focus({ preventScroll: true })
}
</script>

<template>
  <div class="flex" :class="role === 'user' ? 'justify-end' : 'justify-start'">
    <div
      class="max-w-[85%] min-w-0 rounded-panel p-3 text-body text-text-primary"
      :class="role === 'user' ? 'bg-surface-raised' : 'border border-border bg-surface'"
    >
      <span class="sr-only">{{
        role === 'user' ? ptBR.chat.userLabel : ptBR.chat.assistantLabel
      }}</span>
      <p class="whitespace-pre-wrap break-words">
        <template v-for="(segment, i) in segments" :key="i">
          <span v-if="segment.kind === 'text'" v-text="segment.text" />
          <button
            v-else
            type="button"
            class="font-semibold text-accent hover:underline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-focus"
            :aria-label="ptBR.chat.citeLabel(segment.index)"
            @click="goToSource(segment.index)"
            v-text="`[${segment.index}]`"
          />
        </template>
      </p>

      <div v-if="role === 'assistant' && sources.length > 0" class="mt-3">
        <p class="text-meta font-semibold text-text-secondary">{{ ptBR.chat.sources }}</p>
        <ul class="mt-2 flex flex-col gap-2">
          <li v-for="source in sources" :key="source.index">
            <SourceCard
              :id="sourceId(source.index)"
              :source="source"
              :removed="isRemoved(source.document_id)"
              :expanded="expanded[source.index] ?? false"
              @update:expanded="(value: boolean) => (expanded[source.index] = value)"
            />
          </li>
        </ul>
      </div>
    </div>
  </div>
</template>
