<script setup lang="ts">
import { computed } from 'vue'

import { closePendingMarkdown, renderMarkdown } from '@/services/markdown'

const props = withDefaults(
  defineProps<{
    text: string
    // Interrupted partial (task 8.16): closes the emphasis/code left open by the cut, only in
    // the rendered output; the stored text and the history stay untouched.
    closePending?: boolean
  }>(),
  { closePending: false },
)

// The computed tracks `text`, so the accumulated answer is re-processed on every delta
// (PRD §12.4); incomplete markdown syntax shows as literal text until it is closed (§12.11).
const html = computed(() =>
  renderMarkdown(props.closePending ? closePendingMarkdown(props.text) : props.text),
)
</script>

<template>
  <!-- The app's only v-html. Safe by construction (PRD §12.8, decision 10): renderMarkdown
       runs markdown-it with html: false (raw HTML is escaped to plain text) and the
       link/image/autolink/table rules disabled, so the output contains only inert tags. -->
  <!-- eslint-disable-next-line vue/no-v-html -->
  <div class="markdown break-words" v-html="html"></div>
</template>

<style scoped>
/*
 * Only semantic theme variables from style.css (AA contrast in both themes, PRD §9.1/§9.4).
 * :deep() is required because v-html content is not part of this component's template.
 */
.markdown {
  color: var(--theme-text-assistant);
}

.markdown :deep(:first-child) {
  margin-top: 0;
}

.markdown :deep(:last-child) {
  margin-bottom: 0;
}

.markdown :deep(p),
.markdown :deep(ul),
.markdown :deep(ol),
.markdown :deep(pre),
.markdown :deep(blockquote) {
  margin: 0 0 0.75em;
}

/* Headings keep the document rhythm: at most one step above the body text, never larger. */
.markdown :deep(h1),
.markdown :deep(h2),
.markdown :deep(h3),
.markdown :deep(h4),
.markdown :deep(h5),
.markdown :deep(h6) {
  margin: 1em 0 0.5em;
  line-height: 1.3;
}

.markdown :deep(h1) {
  font-size: 1.25em;
  font-weight: 700;
}

.markdown :deep(h2) {
  font-size: 1.125em;
  font-weight: 700;
}

.markdown :deep(h3),
.markdown :deep(h4),
.markdown :deep(h5),
.markdown :deep(h6) {
  font-size: 1em;
  font-weight: 600;
}

/* Tailwind's preflight sets `list-style: none` on every list; restore the markers only here
   (task 8.18), so other lists in the app keep their unstyled look. Nested bullet lists switch
   to a hollow marker, as browsers do by default. */
.markdown :deep(ul),
.markdown :deep(ol) {
  padding-left: 1.5em;
}

.markdown :deep(ul) {
  list-style-type: disc;
}

.markdown :deep(ul ul) {
  list-style-type: circle;
}

.markdown :deep(ol) {
  list-style-type: decimal;
}

.markdown :deep(li::marker) {
  color: var(--theme-text-secondary);
}

.markdown :deep(li) {
  margin: 0.25em 0;
}

.markdown :deep(code) {
  background-color: var(--theme-surface-raised);
  border-radius: var(--radius-control);
  font-family: ui-monospace, monospace;
  font-size: 0.875em;
  padding: 0.125em 0.375em;
  overflow-wrap: anywhere;
}

.markdown :deep(pre) {
  background-color: var(--theme-surface-raised);
  border-radius: var(--radius-control);
  padding: 0.75em;
}

/* Code blocks wrap instead of scrolling: no horizontal overflow at 360 px (PRD §12.4). */
.markdown :deep(pre code) {
  background-color: transparent;
  padding: 0;
  white-space: pre-wrap;
}

.markdown :deep(blockquote) {
  border-left: 3px solid var(--theme-border);
  color: var(--theme-text-secondary);
  padding-left: 0.75em;
}

.markdown :deep(hr) {
  border: 0;
  border-top: 1px solid var(--theme-border);
  margin: 1em 0;
}
</style>
