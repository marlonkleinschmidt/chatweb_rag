<script setup lang="ts">
import { computed, nextTick, ref, useTemplateRef, watch } from 'vue'

import ChatMessage from '@/components/domain/ChatMessage.vue'
import AlertBanner from '@/components/ui/AlertBanner.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseField from '@/components/ui/BaseField.vue'
import BaseIcon from '@/components/ui/BaseIcon.vue'
import { useChat } from '@/composables/useChat'
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

const question = ref('')
const questionError = ref('')
const field = useTemplateRef<InstanceType<typeof BaseField>>('field')
const log = useTemplateRef<HTMLElement>('log')

const selectedCount = computed(() => props.store.selectedIds.length)
const canSend = computed(() => selectedCount.value > 0 && !chat.generating)

watch(question, () => {
  questionError.value = ''
})

async function submit(): Promise<void> {
  if (!canSend.value) return
  const text = question.value.trim()
  if (text.length < config.minQuestionChars || text.length > config.maxQuestionChars) {
    questionError.value = ptBR.chat.questionLength(config.minQuestionChars, config.maxQuestionChars)
    field.value?.focus()
    return
  }
  question.value = ''
  await chat.send(text, [...props.store.selectedIds])
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
      <div class="mt-2 flex justify-end">
        <BaseButton variant="primary" type="submit" :loading="chat.generating" :disabled="!canSend">
          {{ chat.generating ? ptBR.chat.generating : ptBR.chat.send }}
        </BaseButton>
      </div>
    </form>
  </div>
</template>
