# Design system

Tema escuro único, orientado à leitura. Tokens semânticos ficam no `tailwind.config`; **nenhuma cor hexadecimal aparece fora da configuração do tema.**

## Cores

| Token | Valor | Uso | Restrição |
| --- | --- | --- | --- |
| `canvas` | `#0B1020` | Fundo global | — |
| `surface` | `#121A2B` | Painéis, sidebar, cards | — |
| `surface-raised` | `#1A2540` | Inputs, menus, modal | Não usar `text-muted` sobre ele |
| `border` | `#293653` | Bordas e divisores | Decorativo; bordas de controle usam `text-muted` |
| `text-primary` | `#F4F7FC` | Texto principal | — |
| `text-secondary` | `#A8B4CC` | Texto secundário | — |
| `text-muted` | `#75829D` | Metadados | Só sobre `canvas`/`surface` |
| `primary` | `#7C6CF2` | Ação principal, anel de foco | Texto branco sobre ele fica abaixo de 4,5:1 |
| `primary-hover` | `#9285FF` | Hover | — |
| `accent` | `#35C8D0` | Destaques, marcadores `[n]` | — |
| `success` | `#42C99A` | Pronto | — |
| `warning` | `#F4B860` | Processando | — |
| `danger` | `#F17383` | Falhou, remoção | — |
| `gradient-brand` | `#6757E8` → `#27B8C7` | Botão primário, detalhes pontuais | Ver nota de contraste |

**Contraste do botão primário:** texto branco sobre o gradiente ou sobre `primary` fica abaixo do AA. A solução (texto `canvas` em peso 600 ou escurecer a ponta ciano) ainda será decidida na Sprint 4.

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
| `BaseButton` | `primary`, `secondary`, `ghost`, `danger`; `loading`, `disabled` | Altura ≥ 40 px; `loading` desabilita e mostra spinner com `aria-busy` |
| `BaseField` | `input`, `textarea`; `label`, `hint`, `error` | Label sempre visível; erro abaixo, ligado por `aria-describedby` |
| `StatusBadge` | `status` | Texto + ícone + cor (ver [api.md](api.md#estados-do-documento)) |
| `DocumentItem` | `document`, `selected` | Checkbox só para `ready`; menu com "Remover" |
| `ConfirmDialog` | `title`, `message`, `confirmLabel` | Foco preso, `Esc` cancela, ação perigosa em `danger` |
| `ChatMessage` | `role`, `content`, `sources` | Usuário à direita em `surface-raised`; assistente à esquerda em `surface`; `[n]` clicável rola até a fonte |
| `SourceCard` | `source` | Arquivo, "Página n" (omitida se nula), trecho recolhível |
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
