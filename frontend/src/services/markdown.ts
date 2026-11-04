import MarkdownIt from 'markdown-it'

// Safe markdown subset for streamed answers (RF-24, PRD §12.8 decision 10). The model text
// is untrusted (PRD §7.3): `html: false` escapes any raw HTML to plain text, and the link,
// image, autolink and table rules are disabled, so the output contains only inert tags
// (headings, lists, emphasis, code, paragraphs). That is what justifies the app's only
// v-html, in MarkdownText.vue.
const md = new MarkdownIt({
  html: false,
  linkify: false,
  breaks: false,
  typographer: false,
})

md.disable([
  'link',
  'image',
  'autolink',
  'linkify',
  'table',
  // Link reference definitions ([label]: url) belong to the link family: disabled so the
  // line stays visible as literal text instead of being silently consumed.
  'reference',
])

// Renders the accumulated answer text; called again on every delta (PRD §12.4), so
// incomplete markdown syntax appears as literal text until it is closed (PRD §12.11).
export function renderMarkdown(text: string): string {
  return md.render(text)
}
