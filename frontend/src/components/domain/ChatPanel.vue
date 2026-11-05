<script setup lang="ts">
import { computed, nextTick, ref, useId, useTemplateRef, watch } from 'vue'

import ChatMessage from '@/components/domain/ChatMessage.vue'
import AlertBanner from '@/components/ui/AlertBanner.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseField from '@/components/ui/BaseField.vue'
import BaseIcon from '@/components/ui/BaseIcon.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
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
const conversationHintId = useId()
// The hint renders in the action row (outside BaseField), so this id is passed to the field
// through aria-describedby to keep the accessible link required by PRD §9.
const questionHintId = useId()

const selectedCount = computed(() => props.store.selectedIds.length)
// Send needs a ready document selected and a non-empty question; nothing is sent while an answer
// is being generated (the send button becomes "Parar" then).
const canSend = computed(
  () => selectedCount.value > 0 && !chat.generating && question.value.trim().length > 0,
)

// RF-28: confirmation only when there is something to lose. Changing the document selection
// never clears the conversation (PRD §13.8 decision 9).
const confirmingNewConversation = ref(false)

function onNewConversation(): void {
  if (chat.entries.length > 0) {
    confirmingNewConversation.value = true
    return
  }
  chat.newConversation()
}

function confirmNewConversation(): void {
  chat.newConversation()
  confirmingNewConversation.value = false
}

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
  <!-- bg-chat-canvas (task 8.17): darker background for the header and the log; the composer
       cards carry `composer-card` and the question textarea carries `composer-input`. -->
  <div class="flex min-h-0 flex-1 flex-col bg-chat-canvas">
    <!-- not-sr-only resets padding, so the spacing lives on the wrapper. Below lg the heading is
         visually hidden and the button sits alone on the right. -->
    <div class="flex shrink-0 flex-wrap items-center gap-x-4 gap-y-1 px-4 pt-4">
      <h2 :id="headingId" class="sr-only text-sm font-semibold lg:not-sr-only">
        {{ ptBR.chat.heading }}
      </h2>
      <BaseButton
        class="ml-auto"
        :disabled="chat.generating"
        :aria-describedby="conversationHintId"
        @click="onNewConversation"
      >
        {{ ptBR.chat.newConversation }}
      </BaseButton>
      <p :id="conversationHintId" class="w-full text-meta text-text-secondary">
        {{ ptBR.chat.conversationHint }}
      </p>
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
      <div
        v-if="chat.entries.length === 0"
        class="flex flex-col items-center gap-2 text-sm text-text-secondary"
      >
        <BaseIcon name="info" class="text-accent" />
        <p>{{ ptBR.chat.empty }}</p>
      </div>
      <template v-for="entry in chat.entries" :key="entry.id">
        <AlertBanner v-if="entry.role === 'error'" variant="error">{{ entry.content }}</AlertBanner>
        <ChatMessage
          v-else-if="entry.role === 'assistant'"
          role="assistant"
          :content="entry.content"
          :sources="entry.sources"
          :markdown="entry.markdown"
          :interrupted="entry.interrupted"
          :is-removed="store.isRemoved"
        />
        <ChatMessage v-else role="user" :content="entry.content" />
      </template>
      <p v-if="chat.generating" class="flex items-center gap-2 text-sm text-text-secondary">
        <BaseIcon name="spinner" />
        {{ ptBR.chat.generating }}
      </p>
    </div>

    <!-- Layout da área de pergunta: dois cards -->
    <!-- Layout da área de pergunta: dois cards. Transparent wrapper: the cards carry the
         elevation (light = white cards on the gray chat canvas; dark = #303030 on surface). -->
    <div class="w-full shrink-0 rounded-3xl border border-border bg-transparent p-3">
      <div class="flex flex-col lg:flex-row gap-4">
        <!-- Card 1 (aside): selecionar se exibe a fonte de dados (à esquerda) -->
        <aside
          class="shrink-0 lg:w-[25%] rounded-2xl border border-border bg-composer-card p-4 flex flex-col gap-2"
        >
          <div v-if="selectedCount === 0" class="flex items-start gap-2">
            <p class="text-meta text-text-secondary">{{ ptBR.chat.noSelection }}</p>
            <!-- Only below lg: on desktop the documents sidebar is already visible -->
            <BaseButton variant="ghost" class="lg:hidden" @click="emit('go-to-documents')">
              {{ ptBR.chat.goToDocuments }}
            </BaseButton>
          </div>
          <p v-else class="text-meta text-text-secondary">
            {{ ptBR.chat.selectedCount(selectedCount) }}
          </p>
          <!-- RF-20: native checkbox (role="switch") styled as a toggle switch; keyboard navigable
               (Tab, Space), affects only the next answer. The input stays in the accessibility tree
               (sr-only) and the visual track/thumb are aria-hidden siblings driven by peer-*. -->
          <div class="flex flex-col gap-1">
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
        </aside>

        <!-- Card 2: send the question — full-width input, hint on the left, send button on the right -->
        <form
          class="flex-1 min-w-0 rounded-2xl border border-border bg-composer-card p-3 flex flex-col gap-3"
          @submit.prevent="submit"
        >
          <BaseField
            ref="field"
            v-model="question"
            as="textarea"
            :rows="2"
            :max-rows="6"
            :maxlength="config.maxQuestionChars"
            :label="ptBR.chat.questionLabel"
            :label-hidden="true"
            :placeholder="ptBR.chat.questionPlaceholder"
            :error="questionError"
            :aria-describedby="questionHintId"
            control-class="bg-composer-input"
            class="w-full min-h-12 border-none px-3 py-2 text-body text-text-primary placeholder:text-text-secondary focus:ring-0 focus:border-none focus:outline-none disabled:cursor-not-allowed disabled:opacity-60"
            @keydown="onKeydown"
          />
          <!-- Hint on the left, actions on the right (same row), like the composer reference. -->
          <div class="flex items-center justify-between gap-3">
            <span :id="questionHintId" class="text-meta text-text-secondary">{{
              ptBR.chat.questionHint
            }}</span>
            <div class="flex items-center gap-2">
              <!-- RF-23: type="button" (BaseButton default), so it never submits the form. -->
              <BaseButton v-if="chat.generating" @click="chat.stop()">
                {{ ptBR.chat.stop }}
              </BaseButton>
              <BaseButton
                variant="primary"
                type="submit"
                :loading="chat.generating"
                :disabled="!canSend"
              >
                <!-- While loading, BaseButton shows its own spinner instead. -->
                <BaseIcon v-if="!chat.generating" name="send" />
                {{ chat.generating ? ptBR.chat.generating : ptBR.chat.send }}
              </BaseButton>
            </div>
          </div>
        </form>
      </div>
    </div>

    <ConfirmDialog
      :open="confirmingNewConversation"
      :title="ptBR.newConversationDialog.title"
      :message="ptBR.newConversationDialog.message"
      :confirm-label="ptBR.newConversationDialog.confirm"
      @cancel="confirmingNewConversation = false"
      @confirm="confirmNewConversation"
    />
  </div>
</template>
