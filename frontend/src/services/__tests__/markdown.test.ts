import { describe, expect, it } from 'vitest'

import { renderMarkdown } from '@/services/markdown'

// MarkdownText.vue is a thin wrapper (a computed + the app's only v-html) and this suite has
// no component-mounting infrastructure: the safe-subset contract (RF-24, §12.9 criteria 11
// and 12) is tested here on the renderMarkdown module the component delegates to.
describe('renderMarkdown (MarkdownText)', () => {
  it('renderiza o subconjunto seguro: títulos, listas, negrito, itálico e código em linha', () => {
    const html = renderMarkdown(
      [
        '## Procedimento de reinicialização',
        '',
        'Desligue o equipamento e **aguarde 30 segundos**; *não* remova o cabo de energia.',
        '',
        '- Desligar o equipamento',
        '- Aguardar 30 segundos',
        '- Ligar novamente',
        '',
        'O comando é `reboot --now`.',
      ].join('\n'),
    )

    expect(html).toContain('<h2>Procedimento de reinicialização</h2>')
    expect(html).toContain('<strong>aguarde 30 segundos</strong>')
    expect(html).toContain('<em>não</em>')
    expect(html).toContain('<li>Desligar o equipamento</li>')
    expect(html).toContain('<code>reboot --now</code>')
  })

  it('código em bloco renderiza cercado por <pre><code>', () => {
    const html = renderMarkdown('```\nreboot --now\n```')

    expect(html).toContain('<pre><code>')
    expect(html).toContain('reboot --now')
    expect(html).toContain('</code></pre>')
  })

  it('HTML cru do modelo vira texto escapado: nada de tags <script> ou <img>', () => {
    const script = renderMarkdown('<script>alert(1)</script>')
    expect(script).not.toContain('<script')
    expect(script).toContain('&lt;script&gt;alert(1)&lt;/script&gt;')

    const img = renderMarkdown('<img src=x onerror=alert(1)>')
    expect(img).not.toContain('<img')
    expect(img).toContain('&lt;img src=x onerror=alert(1)&gt;')
  })

  it('link com javascript:, imagem e URL nu nunca viram <a> ou <img>', () => {
    const link = renderMarkdown('[clique](javascript:alert(1))')
    expect(link).not.toContain('<a')
    expect(link).not.toContain('href')
    expect(link).toContain('[clique](javascript:alert(1))')

    const image = renderMarkdown('![logo](https://example.com/logo.png)')
    expect(image).not.toContain('<img')
    expect(image).toContain('![logo](https://example.com/logo.png)')

    const bare = renderMarkdown('Acesse https://example.com depois.')
    expect(bare).not.toContain('<a')
    expect(bare).toContain('https://example.com')
  })

  it('tabela nunca renderiza como <table>', () => {
    const html = renderMarkdown('| coluna a | coluna b |\n| --- | --- |\n| 1 | 2 |')

    expect(html).not.toContain('<table')
    expect(html).not.toContain('<th')
    expect(html).not.toContain('<td')
  })

  it('markdown parcial durante o streaming renderiza sem quebrar', () => {
    // Unclosed bold: literal text until the closing ** arrives (PRD §12.11).
    const bold = renderMarkdown('**negrito sem fechar')
    expect(bold).toContain('**negrito sem fechar')
    expect(bold).not.toContain('<strong>')

    // Open fence: becomes a code block instead of throwing.
    const fence = renderMarkdown('```py')
    expect(fence).toContain('<pre>')

    // List cut in the middle of an item.
    const list = renderMarkdown('- primeiro passo\n- segundo passo incompl')
    expect(list).toContain('<li>primeiro passo</li>')
    expect(list).toContain('<li>segundo passo incompl</li>')
  })
})
