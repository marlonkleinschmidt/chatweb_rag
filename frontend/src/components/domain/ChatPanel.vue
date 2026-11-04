<script setup lang="ts">
import { computed, nextTick, ref, useId, useTemplateRef, watch } from 'vue'

import ChatMessage from '@/components/domain/ChatMessage.vue'
import AlertBanner from '@/components/ui/AlertBanner.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseField from '@/components/ui/BaseField.vue'
import BaseIcon from '@/components/ui/BaseIcon.vue'
import { useChat } from '@/composables/useChat'
import { useShowSources } from '@/composables/useShowSources'
import type { DocumentsStore } from '@/composables/useDocuments'
import { config } from '@/config'
import { ptBR } from '@/locales/pt-BR'

const props = defineProps<{
  headingId: string
  store: DocumentsStore
}>()

const emit = defineEmits<{
  'go-to-documents': []
}>()

const chat = useChat()
const showSources = useShowSources()

const question = ref('')
const questionError = ref('')
const field = useTemplateRef<InstanceType<typeof BaseField>>('field')
const log = useTemplateRef<HTMLElement>('log')
const showSourcesId = useId()

const selectedCount = computed(() => props.store.selectedIds.length)
const canSend = computed(() => selectedCount.value > 0 && !chat.generating)

watch(question, () => {
  questionError.value = ''
})

// RF-20: the choice is read at send time and travels explicitly in the payload, so toggling
// it never changes entries that already have an answer.
function onToggleShowSources(event: Event): void {
  const target = event.target
  showSources.setShowSources(target instanceof HTMLInputElement ? target.checked : true)
}

async function submit(): Promise<void> {
  if (!canSend.value) return
  const text = question.value.trim()
  if (text.length < config.minQuestionChars || text.length > config.maxQuestionChars) {
    questionError.value = ptBR.chat.questionLength(config.minQuestionChars, config.maxQuestionChars)
    field.value?.focus()
    return
  }
  question.value = ''
  await chat.send(text, [...props.store.selectedIds], showSources.showSources)
  field.value?.focus()
}

// Enter sends, Shift+Enter breaks the line. Ignored while an IME is composing text.
function onKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Enter' || event.shiftKey || event.isComposing || event.keyCode === 229) return
  event.preventDefault()
  void submit()
}

// Scrolls the log (not the page) so the newest entry starts in view; a short entry ends up
// at the bottom, a long answer shows its beginning. The form is outside the log, so it never
// covers a message.
watch(
  () => [chat.entries.length, chat.generating],
  async () => {
    await nextTick()
    const container = log.value
    const last = container?.lastElementChild
    if (!container || !(last instanceof HTMLElement)) return
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches
    container.scrollTo({
      top: last.offsetTop - 16,
      behavior: reduceMotion ? 'auto' : 'smooth',
    })
  },
)
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col">
    <!-- not-sr-only resets padding, so the spacing lives on the wrapper -->
    <div class="shrink-0 lg:px-4 lg:pt-4">
      <h2 :id="headingId" class="sr-only text-lg font-semibold lg:not-sr-only">
        {{ ptBR.chat.heading }}
      </h2>
    </div>

    <!-- Only this area scrolls; the question form below stays in the footer without covering it.
         `relative` makes it the offsetParent used by the auto-scroll. -->
    <div
      ref="log"
      role="log"
      aria-live="polite"
      :aria-label="ptBR.chat.logLabel"
      class="relative flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4"
    >
      <p v-if="chat.entries.length === 0" class="text-sm text-text-secondary">
        {{ ptBR.chat.empty }}
      </p>
      <template v-for="entry in chat.entries" :key="entry.id">
        <AlertBanner v-if="entry.role === 'error'" variant="error">{{ entry.content }}</AlertBanner>
        <ChatMessage
          v-else-if="entry.role === 'assistant'"
          role="assistant"
          :content="entry.content"
          :sources="entry.sources"
          :markdown="entry.markdown"
          :is-removed="store.isRemoved"
        />
        <ChatMessage v-else role="user" :content="entry.content" />
      </template>
      <p v-if="chat.generating" class="flex items-center gap-2 text-sm text-text-secondary">
        <BaseIcon name="spinner" />
        {{ ptBR.chat.generating }}
      </p>
    </div>

    <form class="shrink-0 border-t border-border bg-surface p-4" @submit.prevent="submit">
      <div v-if="selectedCount === 0" class="mb-2 flex flex-wrap items-center gap-2">
        <p class="text-meta text-text-secondary">{{ ptBR.chat.noSelection }}</p>
        <!-- Only below lg: on desktop the documents sidebar is already visible -->
        <BaseButton variant="ghost" class="lg:hidden" @click="emit('go-to-documents')">
          {{ ptBR.chat.goToDocuments }}
        </BaseButton>
      </div>
      <p v-else class="mb-2 text-meta text-text-secondary">
        {{ ptBR.chat.selectedCount(selectedCount) }}
      </p>
      <!-- RF-20: native checkbox (role="switch") styled as a toggle switch; keyboard navigable
           (Tab, Space), affects only the next answer. The input stays in the accessibility tree
           (sr-only) and the visual track/thumb are aria-hidden siblings driven by peer-*. -->
      <div class="mb-2 flex flex-col gap-1">
        <label
          :for="showSourcesId"
          class="flex w-fit cursor-pointer items-center gap-2 text-sm font-semibold text-text-primary"
        >
          <span class="relative inline-flex shrink-0">
            <input
              :id="showSourcesId"
              type="checkbox"
              role="switch"
              :checked="showSources.showSources"
              class="peer sr-only"
              @change="onToggleShowSources"
            />
            <!-- Track: control-border outline when off, solid primary when on (>= 3:1 on surface).
                 Borders keep the shape visible in forced-colors (high contrast) mode. -->
            <span
              aria-hidden="true"
              class="h-5 w-9 rounded-full border-2 border-control-border bg-surface peer-checked:border-primary peer-checked:bg-primary peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-focus"
            />
            <!-- Thumb: slides only without prefers-reduced-motion; colors keep the global fade. -->
            <span
              aria-hidden="true"
              class="absolute top-1 left-1 size-3 rounded-full border border-control-border bg-control-border peer-checked:translate-x-4 peer-checked:border-on-primary peer-checked:bg-on-primary motion-safe:transition-[translate,background-color,border-color] motion-safe:duration-200"
            />
          </span>
          {{ ptBR.chat.showSourcesLabel }}
        </label>
        <p class="text-meta text-text-secondary">{{ ptBR.chat.showSourcesHint }}</p>
      </div>
      <BaseField
        ref="field"
        v-model="question"
        as="textarea"
        :rows="2"
        :maxlength="config.maxQuestionChars"
        :label="ptBR.chat.questionLabel"
        :placeholder="ptBR.chat.questionPlaceholder"
        :hint="ptBR.chat.questionHint"
        :error="questionError"
        @keydown="onKeydown"
      />
      <div class="mt-2 flex items-center justify-end gap-2">
        <!-- RF-23: type="button" (BaseButton default), so it never submits the form. -->
        <BaseButton v-if="chat.generating" @click="chat.stop()">
          {{ ptBR.chat.stop }}
        </BaseButton>
        <BaseButton variant="primary" type="submit" :loading="chat.generating" :disabled="!canSend">
          <!-- While loading, BaseButton shows its own spinner instead. -->
          <BaseIcon v-if="!chat.generating" name="send" />
          {{ chat.generating ? ptBR.chat.generating : ptBR.chat.send }}
        </BaseButton>
      </div>
    </form>
  </div>
</template>
