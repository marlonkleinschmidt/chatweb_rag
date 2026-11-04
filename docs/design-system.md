# Design system

Dois temas, claro e escuro, escolhidos pelo usuário (RF-19). Tokens semânticos ficam no `@theme` de `frontend/src/style.css`, com um valor por tema; **nenhuma cor hexadecimal aparece fora da configuração do tema.** As tabelas abaixo são do tema escuro; regras e tokens do tema claro estão no PRD §9.4.

## Temas

- A classe `dark` no `<html>` ativa o tema escuro; sem ela, vale o claro.
- Na primeira visita, segue `prefers-color-scheme` (sem preferência: escuro). A escolha fica em `localStorage` (chave `theme`).
- Script inline no `index.html` aplica o tema antes de o Vue montar, sem flash.
- Seletor no cabeçalho com ícone e `aria-label` pt-BR. Componentes usam só tokens semânticos, sem `dark:`.
- Os dois temas cumprem o WCAG AA.

## Cores

| Token | Paleta | Hex | Uso | Restrição / contraste medido (WCAG 2.x) |
| --- | --- | --- | --- | --- |
| `canvas` | `app-gray-850` | `#1F2729` | Fundo global | — |
| `surface` | `app-gray-900` | `#121214` | Painéis, cards, header, painel de documentos | Separa melhor os painéis do fundo que `app-gray-800` (1,23:1 contra 1,05:1) |
| `surface-raised` | `app-gray-700` | `#3A3A40` | Inputs, bolha do usuário, modal | — |
| `border` | `app-gray-600` | `#3D3D44` | Bordas e divisores; fundo de hover de `secondary`/`ghost` | Decorativo; bordas de controle usam `control-border` |
| `control-border` | `app-gray-200` | `#A8A8B3` | Borda de campos e do botão `secondary` | ≥ 3:1: 6,46 (canvas), 7,94 (surface), 4,80 (surface-raised) |
| `focus` | `app-purple-400` | `#A78BFA` | Anel de foco | ≥ 3:1: 5,59 (canvas), 6,88 (surface), 4,15 (surface-raised) |
| `text-primary` | `white` | `#FFFFFF` | Texto principal | 15,21 (canvas), 18,71 (surface), 11,30 (surface-raised), 10,77 (border) |
| `text-secondary` | `app-gray-200` | `#A8A8B3` | Texto secundário, metadados, placeholder | 6,46 (canvas), 7,94 (surface), 4,80 (surface-raised) |
| `primary` | `app-purple-500` | `#8257E6` | Fundo do botão primário; seleção e aba ativa | `text-primary` sobre ele: 4,71:1. Como borda sobre `surface`: 3,97:1. Não usar como anel de foco (2,40:1 sobre `surface-raised`) |
| `primary-hover` | `app-purple-600` | `#6B46C1` | Hover do botão primário | `text-primary` sobre ele: 6,42:1 |
| `on-primary` | `white` | `#FFFFFF` | Texto sobre `primary`/`primary-hover` (botão primário) | 4,71 / 6,42 |
| `on-danger` | `app-gray-850` | `#1F2729` | Texto do botão `danger` | 5,45:1 sobre `danger` |
| `accent` | `app-purple-400` | `#A78BFA` | Marcadores `[n]`, índice da fonte, ícone de informação | 6,88 (surface), 5,59 (canvas); não usar como texto sobre `surface-raised` (4,15:1) |
| `success` | `app-green-500` | `#04D361` | Pronto | 9,35 (surface), 7,60 (canvas) |
| `warning` | `app-amber-300` | `#F4B860` | Processando | 10,58 (surface), 8,60 (canvas) |
| `danger` | `app-red-300` | `#F17383` | Falhou, remoção | 6,70 (surface), 5,45 (canvas); botão `danger` com texto `on-danger`: 5,45:1 |

**Paleta `app-*`** (única fonte de hex; os componentes nunca usam `app-*` diretamente): `white` `#FFFFFF`, `black` `#000000`, `transparent`; `app-purple-400` `#A78BFA`, `app-purple-500` `#8257E6`, `app-purple-600` `#6B46C1`, `app-purple-900` `#581C87`; `app-green-500` `#04D361`; `app-gray-50` `#F8F8F8`, `app-gray-100` `#E1E1E6`, `app-gray-200` `#A8A8B3`, `app-gray-300` `#737380`, `app-gray-400` `#52525B`, `app-gray-500` `#414149`, `app-gray-600` `#3D3D44`, `app-gray-700` `#3A3A40`, `app-gray-800` `#29292E`, `app-gray-850` `#1F2729`, `app-gray-900` `#121214`. Fora da paleta do usuário, que não tem amarelo nem vermelho: `app-amber-300` `#F4B860` e `app-red-300` `#F17383` (os valores de `warning` e `danger` do tema anterior, usados no escuro) e `app-green-700` `#047A39`, `app-amber-700` `#8A5A00` e `app-red-700` `#B42335` (variantes do tema claro).

**Botão primário (tarefas 4.8 e 4.9):** fundo sólido `primary` com texto `on-primary` (branco), 4,71:1; no hover, `primary-hover`, 6,42:1. Com `app-gray-50` no lugar do branco, o texto reprovaria (4,44:1). O gradiente da v2.1 foi retirado. `app-gray-300` (antigo `text-muted`) reprova como texto em todos os fundos escuros (3,25 sobre canvas, 4,00 sobre surface, 2,42 sobre surface-raised) e não é usado como token semântico. Confirmar na tarefa 5.2.1.

## Tema claro

**Tema claro (tarefa 4.12)**, valores finais com contrastes medidos (WCAG 2.x; `canvas` #F8F8F8, `surface` #FFFFFF, `surface-raised` #E1E1E6):

| Token | Tema claro | Hex | Contraste medido |
| --- | --- | --- | --- |
| `canvas` | `app-gray-50` | `#F8F8F8` | — |
| `surface` | `white` | `#FFFFFF` | — |
| `surface-raised` | `app-gray-100` | `#E1E1E6` | — |
| `border` | `app-gray-200` | `#A8A8B3` | Decorativo; como fundo de hover, `text-primary` sobre ele dá 7,94:1 |
| `control-border` | `app-gray-300` | `#737380` | ≥ 3:1: 4,40 (canvas), 4,67 (surface), 3,59 (surface-raised) |
| `focus` | `app-purple-600` | `#6B46C1` | ≥ 3:1: 6,04 (canvas), 6,42 (surface), 4,93 (surface-raised) |
| `text-primary` | `app-gray-900` | `#121214` | 17,62 (canvas), 18,71 (surface), 14,36 (surface-raised) |
| `text-secondary` | `app-gray-500` | `#414149` | 9,52 (canvas), 10,11 (surface), 7,76 (surface-raised) |
| `primary` / `primary-hover` | `app-purple-600` / `app-purple-900` | `#6B46C1` / `#581C87` | `on-primary` sobre eles: 6,42 / 10,88; como borda sobre `surface`: 6,42 |
| `on-primary` | `white` | `#FFFFFF` | Texto do botão primário |
| `accent` | `app-purple-600` | `#6B46C1` | 6,42 (surface), 6,04 (canvas), 4,93 (surface-raised) |
| `success` | `app-green-700` | `#047A39` | 5,46 (surface), 5,14 (canvas). `app-green-500` daria 2,00 |
| `warning` | `app-amber-700` | `#8A5A00` | 5,93 (surface), 5,58 (canvas) |
| `danger` | `app-red-700` | `#B42335` | 6,50 (surface), 6,12 (canvas) |
| `on-danger` | `white` | `#FFFFFF` | Texto do botão `danger`: 6,50 (5,62 no hover com `brightness-110`) |

**Painel de documentos (`surface`, tarefa 7.30)**: no claro o painel é `white` e o card `DocumentItem` (`canvas` #F8F8F8) fica levemente mais escuro que ele (1,06:1); no escuro o painel é `app-gray-900` #121214 e o card fica mais claro (1,23:1). Elementos que ficam direto no painel no claro: `text-primary` 18,71 (título), `text-secondary` 10,11 (dica de upload, aviso de envio à OpenAI, estado vazio, contador de seleção), `accent` 6,42 (ícone do aviso, ≥ 3:1 como gráfico), `primary` 6,42 (fundo do botão de upload e borda do card selecionado, ≥ 3:1), `focus` 6,42, `control-border` 4,67 (botão `secondary` "Tentar novamente"). `border` dá 2,36, decorativo: o card se separa do painel pelo fundo `canvas`. Badges de estado e texto de falha ficam dentro do card, sobre `canvas` (valores da tabela acima). O `AlertBanner` mantém fundo `surface` próprio, igual ao do painel, separado pela borda colorida.

`app-green-700`, `app-amber-700` e `app-red-700` são variantes escuras próprias, fora da paleta do usuário, definidas no `@theme` junto de `app-amber-300` e `app-red-300`.

## Tipografia, espaço e forma

- Fonte Inter (arquivo local em `assets/fonts`), fallback `system-ui, sans-serif`.
- Corpo 15 px / line-height 1,6 nas respostas; metadados 13 px; títulos 600–700.
- Espaçamento em múltiplos de 4 px.
- Raio 12 px em cards e painéis; 8 px em botões e campos.

## Layout e breakpoints

| Dispositivo | Largura |
| --- | --- |
| Celular | < 640 px |
| Tablet | 640–1023 px |
| Desktop | ≥ 1024 px |

- Desktop: sidebar de documentos (320 px) + chat.
- Celular: abas "Documentos" e "Chat"; input de pergunta fixo no rodapé sem cobrir a última mensagem.
- Sem rolagem horizontal em 360 px.

## Componentes base

| Componente | Variantes / props | Regras |
| --- | --- | --- |
| `BaseButton` | `primary`, `secondary`, `ghost`, `danger`; `loading`, `disabled`, `iconOnly` | Altura ≥ 40 px; `loading` desabilita e mostra spinner com `aria-busy`; `iconOnly` é quadrado de 40 px, só ícone, com `aria-label` e `title` obrigatórios (spinner substitui o ícone em `loading`) |
| `BaseField` | `input`, `textarea`; `label`, `hint`, `error` | Label sempre visível; erro abaixo, ligado por `aria-describedby` |
| `StatusBadge` | `status` | Texto + ícone + cor (ver [api.md](api.md#estados-do-documento)) |
| `DocumentItem` | `document`, `selected` | Checkbox só para `ready`; botão "Remover" só com ícone de lixeira (`ghost`, `iconOnly`, `aria-label`/`title` "Remover {nome}", tarefa 7.28), sempre com diálogo de confirmação |
| `ConfirmDialog` | `title`, `message`, `confirmLabel` | Foco preso, `Esc` cancela, ação perigosa em `danger` |
| `ChatMessage` | `role`, `content`, `sources` | Usuário à direita em `surface-raised`; assistente à esquerda em `surface`; `[n]` clicável rola até a fonte |
| `SourceCard` | `source`, `removed` | Arquivo, "Página n" (omitida se nula), trecho recolhível; com `removed`, etiqueta "Documento removido" (ícone + texto em `text-secondary`), sem esconder a fonte |
| `AlertBanner` | `info`, `success`, `warning`, `error` | Ícone + texto; `role='alert'` só para erro |

## Acessibilidade

- Contraste mínimo WCAG AA: 4,5:1 para texto; 3:1 para bordas de controles e foco.
- Todo controle alcançável por `Tab`, com anel de foco visível.
- Diálogos prendem o foco e fecham com `Esc`.
- Área do chat com `aria-live='polite'`.
- Estados combinam cor com texto e ícone, nunca só cor.

## Comportamento da interface

- Polling da lista enquanto houver documento `received`/`processing`.
- Lista com nome original, data de envio (fuso local) e estado, mais recentes primeiro.
- Seleção de 1 a `MAX_DOCUMENTS_PER_QUERY` documentos `ready`; os demais não são selecionáveis.
- Envio da pergunta por botão ou `Enter` (`Shift+Enter` quebra linha); botão desabilitado com indicador durante a geração.
- Remoção sempre passa por diálogo de confirmação.
- A UI nunca mostra página ou nome de arquivo que a API não retornou.
- Recarregar a página limpa o chat.
- Estados com texto pt-BR próprio: carregando lista, lista vazia, nenhum documento selecionado, gerando resposta, erro de rede, erro do provedor.
