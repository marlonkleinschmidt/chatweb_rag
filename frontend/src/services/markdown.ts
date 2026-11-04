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

const PAIRED_DELIMITERS = ['**', '__', '~~', '*', '_']

const isSpace = (char: string | undefined): boolean => char === undefined || /\s/.test(char)
const isWordChar = (char: string | undefined): boolean =>
  char !== undefined && /[\p{L}\p{N}]/u.test(char)

// Interrupted partial (task 8.16): an answer stopped by Parar can end inside `**bold`, `*italic`,
// `~~strike~~` or `inline code`, which markdown-it shows as literal text. Returns the text with
// the pending delimiters of the LAST line closed, innermost first, for rendering only (the
// stored text and the history never change). Emphasis cannot span blocks, and the cut is
// always at the end, so earlier lines are already final. An open ``` fence is left alone:
// markdown-it already renders it as a code block up to the end.
export function closePendingMarkdown(text: string): string {
  const fences = text.split('\n').filter((line) => /^\s*(```|~~~)/.test(line)).length
  if (fences % 2 === 1) return text

  const trimmed = text.replace(/\s+$/, '')
  const lineStart = trimmed.lastIndexOf('\n') + 1
  // List bullets (`* item`, `- item`) and quote/heading markers are not emphasis.
  const content = trimmed
    .slice(lineStart)
    .replace(/^\s*(?:[-*+]\s+|\d+[.)]\s+|>\s*|#{1,6}\s+)*/, '')

  const stack: string[] = []
  let codeTicks = ''
  let i = 0
  while (i < content.length) {
    // Escaped character (`\*`): never a delimiter.
    if (content[i] === '\\') {
      i += 2
      continue
    }
    if (content[i] === '`') {
      let run = '`'
      while (content[i + run.length] === '`') run += '`'
      if (!codeTicks) codeTicks = run
      else if (codeTicks === run) codeTicks = ''
      i += run.length
      continue
    }
    if (codeTicks) {
      i += 1
      continue
    }
    const delimiter = PAIRED_DELIMITERS.find((candidate) => content.startsWith(candidate, i))
    if (!delimiter) {
      i += 1
      continue
    }
    const before = content[i - 1]
    const after = content[i + delimiter.length]
    // Same flanking idea as CommonMark: opens before non-space, closes after non-space;
    // `_` never acts inside a word (snake_case).
    const intraword = delimiter.startsWith('_') && isWordChar(before) && isWordChar(after)
    const canClose = !isSpace(before) && !intraword
    const canOpen = !isSpace(after) && !intraword
    const open = stack.lastIndexOf(delimiter)
    if (open !== -1 && canClose) stack.splice(open)
    else if (canOpen) stack.push(delimiter)
    i += delimiter.length
  }

  const closers = codeTicks + [...stack].reverse().join('')
  return closers ? trimmed + closers : text
}
