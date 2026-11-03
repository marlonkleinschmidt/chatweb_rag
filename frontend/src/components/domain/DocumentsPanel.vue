<script setup lang="ts">
import { computed, nextTick, ref, useId, useTemplateRef } from 'vue'

import DocumentItem from '@/components/domain/DocumentItem.vue'
import AlertBanner from '@/components/ui/AlertBanner.vue'
import BaseButton from '@/components/ui/BaseButton.vue'
import BaseIcon from '@/components/ui/BaseIcon.vue'
import ConfirmDialog from '@/components/ui/ConfirmDialog.vue'
import type { DocumentsStore } from '@/composables/useDocuments'
import { ptBR } from '@/locales/pt-BR'
import type { Document } from '@/types/api'

const props = defineProps<{
  headingId: string
  store: DocumentsStore
}>()

const uploadButtonId = useId()
const uploadHintId = useId()
const openaiNoticeId = useId()
const fileInput = useTemplateRef<HTMLInputElement>('fileInput')

function chooseFile(): void {
  fileInput.value?.click()
}

async function onFileChange(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  // Reset so the same file can be chosen again (e.g. after a failure).
  input.value = ''
  if (!file) return
  await props.store.upload(file)
  // While loading, the button is disabled and focus falls to <body>; give it back
  // (success or error), unless the user has moved focus somewhere else meanwhile.
  await nextTick()
  if (window.document.activeElement === window.document.body) {
    window.document.getElementById(uploadButtonId)?.focus()
  }
}

const pendingRemoval = ref<Document | null>(null)

const hasReady = computed(() => props.store.documents.some((d) => d.status === 'ready'))

async function confirmRemoval(): Promise<void> {
  const document = pendingRemoval.value
  if (!document) return
  const removed = await props.store.remove(document.id)
  pendingRemoval.value = null
  if (removed) {
    // The "Remover" button that opened the dialog no longer exists: focus the upload button.
    await nextTick()
    requestAnimationFrame(() => window.document.getElementById(uploadButtonId)?.focus())
  }
}
</script>

<template>
  <div class="flex min-h-0 flex-1 flex-col">
    <!-- On mobile/tablet the tab already names the panel, so the heading is screen-reader only -->
    <!-- not-sr-only resets padding, so the spacing lives on the wrapper -->
    <div class="shrink-0 lg:px-4 lg:pt-4">
      <h2 :id="headingId" class="sr-only text-lg font-semibold lg:not-sr-only">
        {{ ptBR.documents.heading }}
      </h2>
    </div>

    <div class="flex min-h-0 flex-1 flex-col gap-4 overflow-y-auto p-4">
      <!-- Upload: a visible button opens the hidden file input, so it works with the keyboard -->
      <div class="flex flex-col gap-2">
        <input
          ref="fileInput"
          type="file"
          accept=".pdf,application/pdf"
          class="hidden"
          tabindex="-1"
          aria-hidden="true"
          @change="onFileChange"
        />
        <BaseButton
          :id="uploadButtonId"
          variant="primary"
          :loading="store.uploading"
          :aria-describedby="`${uploadHintId} ${openaiNoticeId}`"
          @click="chooseFile"
        >
          {{ store.uploading ? ptBR.upload.uploading : ptBR.upload.label }}
        </BaseButton>
        <p :id="uploadHintId" class="text-meta text-text-secondary">{{ ptBR.upload.hint }}</p>
        <!-- PRD §7.3: always next to the upload button (empty state and list), read with it -->
        <p :id="openaiNoticeId" class="flex items-start gap-1 text-meta text-text-secondary">
          <BaseIcon name="info" class="mt-0.5 text-accent" />
          <span>{{ ptBR.upload.openaiNotice }}</span>
        </p>
        <AlertBanner v-if="store.uploadError" variant="error">{{ store.uploadError }}</AlertBanner>
        <AlertBanner v-if="store.uploadNotice" :variant="store.uploadNotice.variant">
          {{ store.uploadNotice.text }}
        </AlertBanner>
      </div>

      <AlertBanner v-if="store.embeddingModelChanged" variant="warning">
        {{ ptBR.documents.embeddingModelChanged }}
      </AlertBanner>
      <AlertBanner v-if="store.removeError" variant="error">{{ store.removeError }}</AlertBanner>

      <div v-if="store.loadError" class="flex flex-col gap-2">
        <AlertBanner variant="error">{{ store.loadError }}</AlertBanner>
        <BaseButton class="self-start" :loading="store.loading" @click="store.load()">
          {{ ptBR.health.retry }}
        </BaseButton>
      </div>

      <p
        v-if="!store.loaded && store.loading"
        role="status"
        class="flex items-center gap-2 text-sm text-text-secondary"
      >
        <BaseIcon name="spinner" />
        {{ ptBR.documents.loading }}
      </p>
      <p
        v-else-if="store.loaded && store.documents.length === 0"
        class="text-sm text-text-secondary"
      >
        {{ ptBR.documents.empty }}
      </p>

      <template v-if="store.documents.length > 0">
        <p v-if="hasReady" class="text-meta text-text-secondary" aria-live="polite">
          {{ ptBR.documents.selectionCount(store.selectedIds.length, store.maxSelected) }}
          <template v-if="store.selectionFull">
            {{ ptBR.documents.selectionLimit(store.maxSelected) }}
          </template>
        </p>
        <ul :aria-label="ptBR.documents.listLabel" class="flex flex-col gap-2">
          <DocumentItem
            v-for="document in store.documents"
            :key="document.id"
            :document="document"
            :selected="store.isSelected(document.id)"
            :selection-disabled="store.selectionFull"
            :removing="store.removingId === document.id"
            @update:selected="(value: boolean) => store.setSelected(document.id, value)"
            @remove="pendingRemoval = document"
          />
        </ul>
      </template>
    </div>

    <ConfirmDialog
      :open="pendingRemoval !== null"
      :title="ptBR.removeDialog.title"
      :message="pendingRemoval ? ptBR.removeDialog.message(pendingRemoval.filename) : ''"
      :confirm-label="ptBR.removeDialog.confirm"
      :loading="store.removingId !== null"
      @cancel="pendingRemoval = null"
      @confirm="confirmRemoval"
    />
  </div>
</template>
