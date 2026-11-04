## Sprints e Definition of Done

Os Sprints 1–6 formam o MVP e foram concluídos; a Sprint 7 adiciona a funcionalidade pós-MVP da §12 do PRD (v2.2) e a Sprint 8, o contexto de conversa da §13 (v2.3); ambas seguem as mesmas regras: cada sprint só começa quando a anterior cumpre sua Definition of Done (DoD), e tarefas `[humano]` exigem ação de uma pessoa e não podem ser feitas por agente. As user stories da v2.0 (US-01 a US-09) estão cobertas pelos critérios "Verificar" da §4 do PRD e pelas DoD abaixo; as da v2.2 (US-10 a US-13), pela §12.2 do PRD.

### Sprint 1 — Base local

- [x] 1.1 Registrar no README as versões de Python e Node usadas.
- [x] 1.2 **[humano]** Revogar a chave OpenAI exposta e gerar uma nova.
- [x] 1.3 Remover chaves dos scripts do protótipo; ler `OPENAI_API_KEY` do ambiente.
- [x] 1.4 Criar `.gitignore` (`.env`, `data/`, `node_modules/`, `__pycache__/`) e `.env.example` com todas as variáveis da §3.
- [x] 1.5 Criar FastAPI com `/api/v1/health`, `config.py`, CORS e handler global de erros (§5.3).
- [x] 1.6 Criar schemas Pydantic de `Document`, `ChatRequest`, `ChatResponse`, `Source`, `ErrorResponse`.
- [x] 1.7 Inicializar Vue 3 + TS + Vite + Tailwind; criar `services/api.ts` com URL base em `VITE_API_BASE_URL`.
- [x] 1.8 Configurar Ruff, ESLint e Prettier (§7.2).
- [x] 1.9 Documentar no README instalação e execução dos dois processos.

**DoD:** `git grep -i 'sk-'` não encontra chave; `GET /api/v1/health` retorna `ok`; frontend exibe o status do health; lint passa nos dois lados.

### Sprint 2 — Catálogo e ingestão [x]

- [x] 2.1 Criar `db.py` com a tabela da §8.2 e funções `create`, `get`, `list`, `update_status`, `delete`.
- [x] 2.2 Implementar `POST /documents` com validações de RF-02 e retorno `202`.
- [x] 2.3 Implementar indexação em background (§6.1), com lock de execução sequencial.
- [x] 2.4 Implementar RF-08 (PDF sem texto) e mapeamento de falhas para `error_code`.
- [x] 2.5 Marcar `received`/`processing` órfãos como `failed` no startup.
- [x] 2.6 Implementar `GET /documents` e `GET /documents/{id}`.
- [x] 2.7 Implementar `DELETE` com a ordem e idempotência da §8.3 e `409` durante processamento.

**DoD:** com `curl`, um PDF real chega a `ready` com `chunk_count` > 0; um PDF escaneado chega a `failed / pdf_no_text`; um `.txt` renomeado para `.pdf` recebe `422 file_not_pdf`; após `DELETE`, a coleção Chroma não tem vetores daquele ID.

### Sprint 3 — Consulta RAG [x]

- [x] 3.1 Implementar recuperação com filtro e limiar (§6.2, passos 2–4).
- [x] 3.2 Implementar `ANSWER_PROMPT_V1` e saída estruturada (§6.3).
- [x] 3.3 Implementar validação pós-modelo e montagem de `sources` (§6.2, passos 7–8).
- [x] 3.4 Implementar `POST /chat/query` com `409`, `502` e `504`.
- [x] 3.5 Montar o conjunto de avaliação e registrar em `docs/eval.md` (§6.4).
- [x] 3.6 Ajustar `CHUNK_SIZE`, `RETRIEVAL_K` e `RELEVANCE_THRESHOLD` e registrar os valores finais na §3.

**DoD:** no conjunto de avaliação, as 4 perguntas fora do tema retornam a mensagem fixa, a pergunta com instrução maliciosa é ignorada e ao menos 4 das 5 perguntas de página única citam a página certa.

### Sprint 4 — Design system e interface [x]

- [x] 4.1 Configurar tokens, fonte, raios e breakpoints (§9).
- [x] 4.2 Decidir e aplicar a solução de contraste do botão primário (§9.1).
- [x] 4.3 Criar os componentes base da §9.3 e `locales/pt-BR.ts`.
- [x] 4.4 Montar layout desktop (sidebar + chat) e celular (abas).
- [x] 4.5 Integrar upload, polling, lista, remoção com confirmação e estado vazio.
- [x] 4.6 Integrar chat: seleção, envio por botão/`Enter`, citações `[n]` clicáveis e fontes.
- [x] 4.7 Exibir o aviso de envio de dados à OpenAI junto ao upload.
- [x] 4.8 Adotar a nova paleta `app-*` (roxo, verde e cinzas) no `@theme`, remapeando os tokens semânticos da §9.1 (`canvas`, `surface`, `primary`...) para ela, com fundo global `app-gray-850`.
- [x] 4.9 Medir o contraste WCAG AA da nova paleta (texto, botão primário, badges, bordas de controle, anel de foco) e ajustar o que reprovar.
- [x] 4.10 Aplicar a transição de cor global (200 ms em fundo, borda e texto), desligada com `prefers-reduced-motion`.
- [x] 4.11 Atualizar a §9.1 do PRD, `docs/design-system.md` e o README (Decisões) com a nova paleta e os contrastes medidos.
- [x] 4.12 Implementar o tema claro (PRD §9.4): valores claros dos tokens semânticos, classe `dark` no `<html>` e contraste AA medido nos dois temas, registrado na §9.4.
- [x] 4.13 Criar o seletor de tema no cabeçalho (RF-19): padrão do sistema, escolha salva no `localStorage`, sem flash ao carregar e textos em `locales/pt-BR.ts`.
- [x] 4.14 Verificar de novo a DoD com a nova paleta, nos temas claro e escuro, em 1440 px e 360 px.

**DoD:** o fluxo da §4.4 completo funciona em 1440 px e 360 px, só com teclado, nos temas claro e escuro, e nenhuma string em inglês aparece na interface. Os dois temas passam no WCAG AA, e a escolha de tema persiste após recarregar (RF-19).

### Sprint 5 — Revisão do MVP [x]

- [x] 5.1 Percorrer todos os "Verificar" da §4 e registrar o resultado em `docs/checklist-mvp.md`.
- [x] 5.2 Conferir contraste (WCAG AA), foco, labels e ausência de rolagem horizontal.
- [x] 5.3 Conferir logs: nenhum conteúdo de PDF, pergunta, resposta ou chave.
- [x] 5.4 Registrar duração de indexação e de consulta (p50 em 20 execuções) e custo estimado por documento e por consulta.
- [x] 5.5 Documentar no README: backup, retenção, limitações (OCR, volume, multiusuário).

**DoD:** checklist da §4 100% aprovado ou com desvios documentados; medições da 5.4 registradas na §11.2.

### Sprint 6 — Testes e Docker [x]

- [x] 6.1 Pytest: validação de upload, transições de estado, regra de evidência (com retriever e LLM falsos), endpoints de documentos.
- [x] 6.2 Vitest: `useDocuments` e `useChat` com `fetch` simulado.
- [x] 6.3 Converter as perguntas de `docs/eval.md` em teste de regressão opcional (roda só com chave configurada).
- [x] 6.4 Dockerfile do backend sem segredo; build estático do frontend; volume para `data/`.
- [x] 6.5 Documentar execução com e sem Docker.

**DoD:** `pytest` e `npm run test` passam; `docker compose up` sobe a aplicação com os dados persistindo após reinício.

### Sprint 7 — Exibição opcional das fontes (PRD §12) [x]

**Backend**

- [x] 7.1 Campo `show_sources` e código de erro: `show_sources: bool = Field(default=True)` em `ChatRequest` e schema derivado `ChatStreamRequest` com default `False` (`backend/app/schemas/chat.py`); `STREAM_SOURCES_UNSUPPORTED` em `ErrorCode` (`backend/app/core/errors.py`, mensagem pt-BR e status 422 da §5.3); espelhar o campo em `frontend/src/types/api.ts` (`ChatRequest.show_sources: boolean`).
  - Pronto quando: request sem o campo vale `true` no `/chat/query` (cliente existente inalterado) e `false` no `/chat/query/stream`, e o OpenAPI documenta os dois defaults.
- [x] 7.2 Resposta JSON sem marcadores em `backend/app/services/rag_service.py`: `answer_question` e `_assemble_answer` aceitam o modo sem fontes — claims válidos montados sem `[n]` (variante de `_claim_sentence`), parágrafos fixos (partes não encontradas, claims não vinculados) mantidos, `sources: []`; camadas 1 e 2 intactas.
  - Pronto quando: `POST /chat/query` com `show_sources=false` devolve `answer` sem `\[\d+\]` e `sources: []`, e claims sem citação válida continuam descartados.
- [x] 7.3 Prompt sem fontes: `ANSWER_NO_SOURCES_PROMPT_V1` em `backend/app/services/prompts.py` (novo) — regras de grounding e defesa contra prompt injection herdadas do `ANSWER_PROMPT_V2` (regras 1 e 5–8), resposta em texto corrido com formatação markdown simples (títulos curtos, negrito, itálico, listas, código em linha e em bloco; sem tabelas, links, imagens ou HTML) e sem marcadores `[n]`, parágrafo "Não encontrei nos documentos selecionados: …" para partes sem resposta; `ANSWER_PROMPT_V2` inalterado.
  - Pronto quando: prompt versionado em uso e registro no README ("Decisões") com data e motivo.
- [x] 7.4 Filtro de marcadores em streaming em `rag_service.py`: classe `_MarkerStreamFilter` (nova) com `feed(text) -> str` e `flush() -> str`, reusando `MODEL_MARKER_PATTERN`, `WHITESPACE_PATTERN` e `SPACE_BEFORE_PUNCTUATION_PATTERN`; buffer retém o sufixo que pode ser início de marcador; colchete incompleto no `flush` permanece como texto literal; a limpeza de espaços duplos e espaço antes de pontuação é local aos pontos de remoção, preservando quebras de linha e listas do markdown.
  - Pronto quando: a concatenação de todos os `feed` + `flush` equivale ao filtro aplicado ao texto completo, inclusive com `[` num chunk e `3]` no seguinte.
- [x] 7.5 Gerador de stream em `rag_service.py`: `stream_answer(request)` (nova) — validação e recuperação como na §6.2 (camada 1 devolve a resposta fixa como delta único), geração com `ChatOpenAI(...).stream` (sem `with_structured_output`) e o prompt da 7.3, deltas filtrados pela 7.4, um único `done` com `has_evidence`; falhas do provedor durante a geração viram `AppError` tratado pela rota.
  - Pronto quando: o gerador emite deltas concatenáveis e exatamente um `done`; erros de validação/recuperação acontecem antes do primeiro evento.
- [x] 7.6 Endpoint `POST /chat/query/stream` em `backend/app/api/routes_chat.py`: recebe `ChatStreamRequest` (default `show_sources=false`) e rejeita `show_sources=true` explícito com `422 stream_sources_unsupported`; valida e recupera antes de abrir o stream (erros 409/502/504 como envelope JSON com status, §12.6); `StreamingResponse` com `text/event-stream` e `Cache-Control: no-cache`, eventos `delta`/`done`/`error`; desconexão do cliente encerra o gerador e a iteração do modelo (cancelamento real no backend, não só o cliente parando de ler); `query_done` ganha `show_sources`, `stream` e `first_token_ms` (sem conteúdo).
  - Pronto quando: `curl -N` mostra os eventos na ordem e um erro na geração vira evento `error` seguido do fim da conexão.

**Frontend**

- [x] 7.7 `streamChat()` em `frontend/src/services/api.ts`: `fetch` POST com `AbortSignal`; rejeita status/`Content-Type` inesperados como `UNEXPECTED_RESPONSE`; lê `response.body.getReader()` com `TextDecoder` em modo stream, faz parse dos eventos `data:` (buffer até `\n\n`) e chama `onDelta`/`onDone`; envelope `error` vira `ApiError` (antes e durante o stream).
  - Pronto quando: eventos divididos entre chunks de rede e caracteres UTF-8 divididos são montados corretamente.
- [x] 7.8 Novo `frontend/src/composables/useShowSources.ts`: `showSources` (default `true`), persistência em `localStorage` na chave `show_sources` com try/catch, no padrão do `useTheme.ts` (RF-19).
  - Pronto quando: a escolha sobrevive ao recarregamento e storage bloqueado não quebra o app.
- [x] 7.9 Toggle "Exibir fontes" no `frontend/src/components/domain/ChatPanel.vue`: checkbox nativo com label e hint (`locales/pt-BR.ts`: `chat.showSourcesLabel`, `chat.showSourcesHint`) junto ao formulário da pergunta; navegável por `Tab`, contraste AA nos dois temas, sem `dark:` nem `app-*`; todo envio leva `show_sources` explícito.
  - Pronto quando: alternar o toggle muda o formato da próxima resposta e não afeta as anteriores da sessão (RF-20).
- [x] 7.10 Streaming no `frontend/src/composables/useChat.ts`: `send(question, documentIds, showSources)` (default `true`) escolhe `/chat/query` ou `/chat/query/stream`; no modo streaming a entrada de assistente nasce vazia e cresce a cada delta (mesmo `id`); `stop()` via `AbortController` mantém o parcial; erro no meio mantém o parcial e adiciona entrada de erro; botão "Parar" (`locales/pt-BR.ts`: `chat.stop`) com `BaseButton` no `ChatPanel.vue` durante a geração.
  - Pronto quando: os testes atuais do `useChat` passam sem alteração de semântica (caminho com fontes) e os novos cobrem o caminho streaming.

- [x] 7.11 Renderização markdown segura no chat: dependência `markdown-it` (versão fixada no `frontend/package.json`, única nova da sprint, PRD §8.1); novo `frontend/src/components/domain/MarkdownText.vue` com `html: false`, `linkify: false` e regras de link e imagem desativadas — único `v-html` do app, exceção documentada ao "sem v-html" do `ChatMessage` (e ao lint `vue/no-v-html`, se o preset o ativar); `ChatEntry` de assistente ganha `markdown: boolean` (novo) em `useChat.ts`, `true` apenas no modo streaming; `ChatMessage.vue` usa `MarkdownText` quando `markdown` é `true`, re-processando o texto acumulado a cada delta, e mantém o caminho com fontes exatamente como hoje.
  - Pronto quando: o subconjunto da §12.3 renderiza (lista, negrito, código), HTML cru aparece como texto, nenhum link ou imagem é renderizado e respostas com fontes continuam texto puro.

**Testes**

- [x] 7.12 Pytest do filtro (novo `backend/tests/test_marker_filter.py`): `[1]` inteiro; `[` num chunk e `3]` no seguinte; `[1, 2]` e `[1-3]`; espaços duplos e espaço antes de pontuação após a remoção; `[anexo]` preservado; `[` solto no fim mantido; equivalência com o filtro aplicado ao texto completo; remoção de marcador preservando quebras de linha e listas do markdown (limpeza local).
- [x] 7.13 Pytest de endpoints: `/chat/query` sem fontes (fake retriever/LLM no padrão do `test_evidence_rule.py`, camadas 1 e 2); `/chat/query/stream` com fake no ponto de chamada ao modelo — eventos delta/done, omissão de `show_sources` → responde sem fontes, `show_sources=true` explícito → `422 stream_sources_unsupported`, `document_not_ready` → 409 JSON antes do stream, falha na geração → evento `error`, camada 1 → delta único + `done` com `has_evidence=false`.
- [x] 7.14 Vitest: `useShowSources` (default, persistência, storage bloqueado); `useChat` no modo streaming (deltas na mesma entrada, `markdown: true`, `stop`, erro no meio, payload com `show_sources: false` e sem histórico); parser do `streamChat` com helper de resposta SSE no `__tests__/testUtils` (evento dividido entre chunks, UTF-8 dividido); `MarkdownText` (subconjunto renderiza; `<script>`, atributos `on*` e HTML cru viram texto; `[x](javascript:...)` e imagens não renderizam; markdown parcial durante o streaming não quebra o render).
- [x] 7.15 Regressão opcional (com chave): estender `backend/tests/test_regression_eval.py` para rodar as 15 perguntas do `docs/eval.md` também com `show_sources=false` (JSON), comparar `has_evidence` e custo com o modo com fontes e registrar TTFT p50/p90 (`first_token_ms`) em execuções repetidas, para confirmar ou ajustar a meta provisória da §12.4.
- [x] 7.16 Verificação manual com Playwright MCP dos critérios "Verificar" de RF-20 a RF-24 e da §12.9: alternar o toggle nos dois sentidos, recarregar a página, observar o texto crescendo e o markdown renderizando, Parar, navegação por teclado e 360 px nos dois temas.

**Documentação**

- [x] 7.17 Atualizar `docs/api.md` (endpoint novo, `show_sources`, eventos SSE com exemplos — incluindo que `delta.text` é markdown —, `stream_sources_unsupported`), o README ("Decisões": prompt novo, streaming, `markdown-it`, premissas da §12.8) e `docs/README.md` se o índice mudar.

**Ajustes solicitados após a Sprint 7**

- [x] 7.18 Trocar o checkbox "Exibir fontes" por um **toggle switch** (interruptor de alternância) no `ChatPanel.vue`: continuar com `<input type="checkbox">` nativo (Tab e Space funcionam, sem `dark:` nem `app-*`), estilo visual de switch só com tokens semânticos (`primary`, `surface`, `border`, `on-primary`), anel de foco `focus` visível nos dois temas, contraste AA (faixa e bolinha ≥ 3:1 contra o fundo), label e hint (`chat.showSourcesLabel`, `chat.showSourcesHint`) e a lógica de `show_sources` inalterados.
- [x] 7.19 Deixar os **cards de arquivos enviados** com fundo um pouco mais claro que o fundo do painel, nos dois temas: só tokens semânticos (provavelmente `surface-raised` sobre `canvas`), contraste AA do texto preservado, transição de cor global respeitada (200 ms, `prefers-reduced-motion`).
- [x] 7.20 Adicionar **ícone de seta de envio** ao botão "Enviar" do chat (`BaseButton` + `BaseIcon`): ícone novo no `BaseIcon` (SVG inline, `aria-hidden`), antes do rótulo, sem alterar os textos pt-BR nem o comportamento de `loading`/`disabled`.

- [x] 7.21 Cards de documentos mais claros também no **tema claro** (pendência da 7.19): o painel lateral usa `bg-surface`, que no claro é branco (#FFFFFF). Por isso o card em `bg-canvas` fica levemente mais **escuro** (razão 1,06). No escuro, o pedido já é cumprido (razão 1,23). É preciso decidir entre escurecer o fundo do painel no tema claro e criar um token semântico novo (ex.: `surface-card`) no design system (`docs/design-system.md`, PRD §9.1/§9.4), mantendo o contraste AA.
- [x] 7.22 Verificação visual com Playwright MCP das 7.18–7.21: toggle (Tab, Space, clique no label, anel de foco, sem animação com `prefers-reduced-motion`, leitor anuncia `switch`), cards e botão "Enviar" com ícone e com spinner durante a geração, em 1440 px e 360 px, nos dois temas.


**Problemas encontrados na verificação da 7.22**

- [x] 7.23 Texto em inglês na UI: o hint `chat.showSourcesHint` (`frontend/src/locales/pt-BR.ts:80`) diz "a resposta chega em streaming". Trocar por texto em pt-BR, por exemplo "a resposta aparece aos poucos, sem citações", e ajustar os testes que conferem esse texto, se houver.
- [x] 7.24 Numeração das citações: na pergunta "Qual é a placa do veículo?", a única fonte da resposta apareceu como `[4]`, e não `[1]`. Verificar no `rag_service.py` (montagem de `sources` e renumeração dos `[n]`, PRD §6.2 passos 7–8) se isso é intencional (o número é o índice do trecho no prompt) ou defeito. Se for defeito, renumerar `answer` e `sources` em sequência a partir de 1 e cobrir com Pytest.
- [x] 7.25 Nomes de arquivo nos cards de documentos quebram no meio da palavra (ex.: "CRLVE_QIS2867_2 / 026.pdf") por causa do espaço ocupado pelo botão "Remover" (`DocumentItem.vue`). Preferir truncar com reticências e mostrar o nome completo em `title`, ou quebrar só em separadores, sem rolagem horizontal em 360 px.
- [x] 7.26 Outras palavras em inglês achadas na revisão da 7.23 (`locales/pt-BR.ts`): "modelo de embeddings" virou "modelo de indexação" (com `docs/api.md` e PRD §6.1 atualizados) e "Verifique se o backend está em execução" virou "Verifique se ele está em execução". Ficaram nomes de teclas, marcas e `VITE_API_BASE_URL`.

**Problemas encontrados na conferência das 7.23–7.26 no navegador**

- [x] 7.27 Bolha vazia do assistente após erro no streaming: quando `/chat/query/stream` falha antes do primeiro delta (rede, 409/502/504 ou "Parar" imediato), a entrada de assistente criada vazia fica na lista acima do erro, e o leitor de tela anuncia "Assistente:" sem conteúdo. Em `frontend/src/composables/useChat.ts` (criação em ~32-38, `catch` em ~84-91), remover a entrada quando `content === ''` e manter o parcial quando houver texto. Cobrir com Vitest.
- [x] 7.28 Botão "Remover" compacto nos cards de documentos (`DocumentItem.vue:92-101`): em 1440 px ele ocupa 92 px e sobram só 128 px para o nome, então até "CRLVE_QIS2867_2026.pdf" fica truncado. Reduzir o botão (ex.: só ícone de lixeira com `aria-label` "Remover {nome}" e `title`, ou padding menor), mantendo área de toque ≥ 24 px, foco visível e contraste AA.
- [x] 7.29 Recuperação com vários documentos selecionados: numa pergunta mista sobre o CRLV e o manual SM-G97X, todos os trechos recuperados vieram do manual, que é muito maior, e as partes sobre o CRLV saíram como "não encontrei". Avaliar no `rag_service.py` uma cota mínima de trechos por documento selecionado (dentro de `RETRIEVAL_K`, com o mesmo `RELEVANCE_THRESHOLD`), medir com `docs/eval.md` e registrar a decisão no README. Mudança de pipeline: confirmar com o usuário antes de implementar.

**Ajuste solicitado pelo usuário (cards)**

- [x] 7.30 Ajuste solicitado pelo usuário sobre os **cards**: no tema escuro o card deve ficar **levemente mais claro** que o painel e no tema claro **levemente mais escuro**. A 7.21 inverteu o sentido no claro (painel `sidebar` #E1E1E6 com o card `canvas` mais claro que ele): reverter o painel para `bg-surface` e manter o card `bg-canvas` (escuro `#1F2729` sobre `#121214` = mais claro; claro `#F8F8F8` sobre `#FFFFFF` = mais escuro), remover o token `sidebar` do `style.css`, ajustar o comentário do `DocumentItem.vue` e atualizar `docs/design-system.md`; contraste AA preservado (mín. 5,15:1 claro e 5,45:1 escuro nos textos de status).

**Pendências encontradas na execução das 7.27–7.30**

- [x] 7.31 Verificação visual com Playwright MCP das 7.27, 7.28 e 7.30 (o MCP não conectou na sessão em que foram implementadas): sem bolha "Assistente:" vazia após erro antes do primeiro delta e após "Parar" imediato; botão de lixeira com `aria-label`/`title` "Remover {nome}", foco visível, confirmação e spinner, e "CRLVE_QIS2867_2026.pdf" inteiro em 1440 px; card mais claro que o painel no escuro e mais escuro no claro; tudo em 1440 px e 360 px, nos dois temas.
- [x] 7.32 Medir a cota por documento da 7.29 com dados reais: acrescentar ao `docs/eval.md` (e à regressão opcional) ao menos uma pergunta mista com PDFs de tamanhos muito diferentes (ex.: CRLV + manual SM-G97X) e confirmar que as partes sobre o documento pequeno deixam de sair como "não encontrei". Hoje o caso só está coberto por testes com vector store falso.

**Problema encontrado na medição da 7.32**

- [x] 7.33 A cota por documento (7.29) não resolve o caso real: na pergunta mista em que o CRLV não é citado (CM2/CM3 em `docs/eval.md`), a cota traz 1 trecho do CRLV, mas é o trecho só com os rótulos, porque com `CHUNK_SIZE=500` o rótulo "PLACA" (caractere 352) e o valor da placa (caractere 1.167) caem em trechos diferentes. A placa continua saindo como "não encontrei" (0/8). Cota 2–5 troca o "não encontrei" pelo número do chassi (resposta errada com citação), por isso foi rejeitada. Avaliar mudança de extração/chunking para PDFs pequenos ou de formulário (ex.: indexar o documento inteiro como um trecho quando couber em poucos milhares de caracteres, ou parear rótulo e valor na extração), medir com CM1–CM3 (`test_mixed_crlv_manual`, hoje CM2 é `xfail`) sem trocar "não encontrei" por campo errado, e registrar no README. Mudança de pipeline: confirmar com o usuário antes de implementar.

**DoD:** `pytest` e `npm run test` passam (junto com lint, format e `vue-tsc`); com o toggle ligado, comportamento e contrato idênticos aos atuais (texto puro com `[n]` e fontes); com o toggle desligado, a resposta renderizada não contém `\[\d+\]` nem painel de fontes, chega incrementalmente e é renderizada como markdown seguro (HTML cru nunca executa); a preferência persiste após recarregar; TTFT (`first_token_ms`) medido com o conjunto de avaliação e a meta da §12.4 confirmada ou ajustada; `docs/api.md` e README atualizados.

### Sprint 8 — Contexto de conversa (PRD §13) [x]

Objetivo: perguntas de continuação ("e a cor dele?") passam a ser entendidas pelo histórico recente da sessão, sem quebrar a regra de evidência em duas camadas. O backend continua sem estado: o histórico vive no navegador e vai no payload. Fora de escopo: responder sem recuperação, só com o histórico; gravar conversas no servidor (SQLite); várias conversas ou abas sincronizadas.

**PRD e contrato**

- [x] 8.1 Escrever a §13 do PRD (v2.3) e atualizar a nota de versão: objetivo, histórias de usuário (US-14 em diante), requisitos RF-25 em diante, contrato, pipeline, decisões, critérios de aceite, fora de escopo e riscos. Revisar o RF-15 ("payload sem mensagens anteriores"), que passa a valer só quando o histórico estiver vazio ou desligado. Novas variáveis na §3 e em `docs/configuration.md`: `MAX_HISTORY_TURNS` (ex.: 4), `MAX_HISTORY_CHARS` (ex.: 4000) e `QUERY_REWRITE_ENABLED` (padrão `true`). **[humano]** Revisar e aprovar a §13 antes da 8.2, porque ela muda o contrato da API e cria prompts novos.
  - Pronto quando: a §13 está aprovada e os critérios "Verificar" de cada RF estão escritos.
- [x] 8.2 Campo `history` opcional em `ChatRequest` e, por herança, em `ChatStreamRequest` (`backend/app/schemas/chat.py`): lista de `{role: 'user' | 'assistant', content: str}`, padrão `[]`; validação de no máximo `2 × MAX_HISTORY_TURNS` mensagens e `MAX_HISTORY_CHARS` no total, com erro `422 history_invalid` (`ErrorCode` em `backend/app/core/errors.py`, mensagem pt-BR, tabela de `docs/api.md`). Espelhar em `frontend/src/types/api.ts` (`ChatHistoryMessage`, `ChatRequest.history?`).
  - Pronto quando: request sem `history` mantém exatamente o comportamento atual nos dois endpoints, e o OpenAPI documenta o campo e os limites.

**Backend**

- [x] 8.3 Reescrita da pergunta em `backend/app/services/rag_service.py`: `_rewrite_question(question, history) -> str` (nova), com `QUERY_REWRITE_PROMPT_V1` em `prompts.py`. O prompt transforma a pergunta de continuação em pergunta autônoma em pt-BR, usando só o histórico, sem responder e sem acrescentar fatos; o histórico vai entre tags próprias (ex.: `<historico>`), removidas antes do conteúdo, como nos `<trecho>`. Pular a chamada quando `history` está vazio ou `QUERY_REWRITE_ENABLED=false`. Falha ou timeout da reescrita cai para a pergunta original (log com `error_code`, sem conteúdo), sem virar erro para o usuário.
  - Pronto quando: a pergunta reescrita é usada na recuperação (`_retrieve`, inclusive a cota por documento da 7.29), e sem histórico nenhuma chamada extra ao modelo acontece.
- [x] 8.4 Histórico no prompt de resposta: `ANSWER_PROMPT_V3` e `ANSWER_NO_SOURCES_PROMPT_V2` em `prompts.py` (V2 e V1 ficam inalterados, para histórico), com uma seção de histórico tratada como dado, não como instrução, e a regra de que só os `<trecho>` atuais são evidência: o histórico ajuda a entender a pergunta, mas não sustenta afirmação. Respostas anteriores entram sem marcadores `[n]` (reusar `MODEL_MARKER_PATTERN`), para o modelo não citar trechos antigos com numeração errada. As camadas 1 e 2 da regra de evidência continuam iguais: sem trecho acima de `RELEVANCE_THRESHOLD` na pergunta reescrita, volta a resposta fixa sem chamar o modelo de resposta. Registrar os prompts novos no README ("Decisões") com data e motivo.
  - Pronto quando: `/chat/query` (com e sem fontes) e `/chat/query/stream` usam os prompts novos quando há histórico e os atuais quando não há.
- [x] 8.5 Log e métricas: `query_done` ganha `history_turns`, `rewritten` (bool) e `rewrite_ms`, sem o texto da pergunta original, da reescrita ou do histórico.
  - Pronto quando: os logs de uma consulta com histórico mostram só contagens, durações e flags.

**Frontend**

- [x] 8.6 Envio do histórico em `frontend/src/composables/useChat.ts`: `send` monta `history` com as últimas `MAX_HISTORY_TURNS` trocas concluídas da sessão (pergunta + resposta do assistente). Ficam de fora entradas de erro, a resposta fixa de "sem evidência", respostas interrompidas por "Parar" e a pergunta em andamento. Respostas com fontes vão sem os `[n]`. Limite espelhado em `VITE_MAX_HISTORY_TURNS` e `VITE_MAX_HISTORY_CHARS` (`.env.example` do frontend, build args do `docker-compose.yml`), cortando as trocas mais antigas primeiro.
  - Pronto quando: o payload nunca passa dos limites do backend e a primeira pergunta da sessão vai com `history: []`.
- [x] 8.7 Botão "Nova conversa" no `ChatPanel.vue` (`BaseButton`, texto em `locales/pt-BR.ts`, ex.: `chat.newConversation`): limpa as mensagens e o histórico, com confirmação só se houver mensagens; desabilitado durante a geração. Indicação discreta de que a conversa usa as mensagens anteriores (hint em `locales/pt-BR.ts`). Mudar a seleção de documentos não limpa a conversa; o histórico continua valendo só como contexto.
  - Pronto quando: depois de "Nova conversa", a próxima pergunta vai com `history: []`; foco, teclado e contraste AA nos dois temas.
- [x] 8.8 Persistência opcional da conversa no navegador: novo `frontend/src/composables/useChatStorage.ts`, no padrão do `useTheme.ts`/`useShowSources.ts`, com `localStorage` na chave `chat_history`, try/catch e formato versionado (ex.: `{version: 1, entries: [...]}`; versão desconhecida é descartada). Guarda só as entradas exibidas e as fontes, com limite de tamanho, e é limpa por "Nova conversa". Registrar no README (privacidade: as conversas ficam no navegador da máquina) e revisar o README "Retenção" ("O chat não é persistido").
  - Pronto quando: a conversa sobrevive ao recarregar, storage bloqueado ou corrompido não quebra o app e "Nova conversa" apaga a chave.

**Testes**

- [x] 8.9 Pytest (novo `backend/tests/test_chat_history.py`, com fakes no padrão do `test_evidence_rule.py`): sem histórico, nenhuma chamada de reescrita e prompts atuais; com histórico, a pergunta reescrita chega ao `_retrieve`; falha da reescrita cai para a pergunta original; `history_invalid` acima dos limites; marcadores `[n]` removidos das respostas anteriores; tags `<historico>` e `<trecho>` dentro do histórico neutralizadas; camada 1 com a pergunta reescrita sem trecho relevante devolve a resposta fixa; streaming com histórico emite `delta`/`done` como antes.
- [x] 8.10 Vitest: `useChat` monta `history` (limite de trocas e de caracteres, exclusão de erro, "sem evidência" e parcial interrompido, `[n]` removidos, primeira pergunta com `[]`); "Nova conversa" zera o histórico; `useChatStorage` (persistência, versão desconhecida descartada, storage bloqueado, JSON corrompido).
- [x] 8.11 Avaliação com a chave: acrescentar ao `docs/eval.md` e à regressão opcional (`backend/tests/test_regression_eval.py`) um conjunto de conversas de 2–3 turnos. Exemplos: placa do CRLV seguida de "e o ano de fabricação?"; captura de tela no manual seguida de "e para gravar a tela?"; uma continuação fora do tema, que deve dar "não encontrei"; uma continuação com instrução maliciosa no histórico, que deve ser ignorada. Medir a taxa de acerto com e sem reescrita, o custo extra por pergunta e o impacto no TTFT (`first_token_ms`, `rewrite_ms` p50/p90), e confirmar que as 15 perguntas atuais não regridem.
  - Pronto quando: os números estão no `docs/eval.md` e a decisão de manter `QUERY_REWRITE_ENABLED=true` está registrada no README.
- [x] 8.12 Verificação com Playwright MCP dos critérios da §13: conversa de continuação nos dois modos (com e sem fontes), "Nova conversa", recarregar a página com a conversa salva, teclado e leitor de tela, em 1440 px e 360 px, nos dois temas, e no Docker (`docker compose build` + `up -d`).

**Problemas encontrados na verificação da 8.12**

- [x] 8.14 Hint "Nova conversa" sem associação acessível: o `<p>` de `chat.conversationHint` não estava ligado ao botão. Corrigido com `aria-describedby` (`useId`) no `ChatPanel.vue`.
- [x] 8.15 Citação de continuação apontando para trecho que não contém o fato: com só o CRLV selecionado e fontes ligadas, "Qual é a placa do veículo?" seguida de "E o ano de fabricação?" respondeu "…é 2017 [1]", mas o `[1]` era o chunk `:4` ("HYUNDAI/CRETA…"), sem "2017"; o fato está no chunk `:3`, o citado na pergunta anterior (visto 1 vez, com o CRLV indexado em vários chunks, antes da 7.33). Hipótese: o modelo tira o fato do histórico e cita qualquer trecho atual, e a camada 2 só confere se o índice existe. Medir a taxa com os números da 8.11 e avaliar mitigação (ex.: regra mais forte no `ANSWER_PROMPT_V3`, ou não passar a resposta anterior do assistente ao prompt de resposta). Mudança de prompt/pipeline: confirmar com o usuário antes de implementar.
  - **Descartada pelo usuário (4 de novembro de 2026):** a checagem em código (cada número ou código da afirmação precisa aparecer no trecho citado, só com histórico) chegou a ser implementada e foi desfeita antes da medição, por decisão do usuário. Fica como lacuna conhecida, documentada em `docs/rag-pipeline.md` e no turno CV11 da regressão (`known_gap`).
- [x] 8.16 Markdown cru no parcial interrompido (cosmético, herdado da Sprint 7): uma resposta parada por "Parar" no meio de `**negrito**` mostra o `**` aberto como texto. Avaliar se vale fechar a marcação pendente só na renderização do parcial (`MarkdownText.vue`), sem alterar o texto salvo.

**Ajustes de interface solicitados pelo usuário**

- [x] 8.17 Cores do chat, só com tokens semânticos (sem `dark:`, sem `app-*` e sem hex nos componentes, CLAUDE.md):
  - **Texto das respostas da IA no tema escuro em cinza `#E1E1E6`** (`app-gray-100`): hoje o card do assistente (`ChatMessage.vue:63-64`, `bg-surface` com `text-text-primary`) usa branco no escuro. Criar um token semântico novo (ex.: `--theme-text-assistant`, utility `text-text-assistant`) no `style.css`, com `app-gray-100` no escuro e o mesmo valor de `text-primary` no claro, para o tema claro não mudar. Aplicar só ao card do assistente, inclusive ao texto em markdown (`MarkdownText.vue`). A pergunta do usuário, as citações `[n]` (`text-accent`) e o painel de fontes ficam como estão. Contraste esperado: `#E1E1E6` sobre `#121214` ≈ 14:1 (AA).
  - **Fundo da seção Chat mais escuro:** a faixa com o título "Chat", o botão "Nova conversa" e o hint `chat.conversationHint` (`ChatPanel.vue:108-120`), e também a área do log, que hoje não têm fundo próprio e mostram o `canvas` do `body` (claro `#F8F8F8`; escuro `#1F2729`, `app-gray-850`). Escurecer cerca de dois passos da escala, como no exemplo do usuário ("de cor-600 para cor-800"). Antes de implementar, **confirmar com o usuário**:
    - se o fundo mais escuro vale só para a faixa do cabeçalho ou para a seção inteira, até o formulário;
    - os valores nos dois temas. Sugestão: escuro `app-gray-850` → `app-gray-900` (`#121214`); claro `app-gray-50` → `app-gray-100` (`#E1E1E6`).
    - No escuro, `app-gray-900` é o mesmo valor do `surface` (formulário, cards do assistente e painel de documentos). Os cards e o formulário perderiam o contraste com o fundo, então avaliar um token novo (ex.: `chat-canvas`) ou um tom intermediário.
  - Medir o contraste WCAG AA nos dois temas: texto e hint sobre o novo fundo (≥ 4,5:1), borda do botão "Nova conversa" e dos cards (≥ 3:1). Manter a transição de cor global (200 ms, `prefers-reduced-motion`). Atualizar `docs/design-system.md` (tokens e contrastes medidos) e o PRD §9.1/§9.4 se surgir token novo. Verificar com Playwright em 1440 px e 360 px, nos dois temas.

**Problema encontrado na execução da 8.17**

- [x] 8.18 Listas em markdown sem marcadores: o preflight do Tailwind remove o `list-style` de `ul`/`ol`, e o `MarkdownText.vue` não o recoloca, então as listas das respostas sem fontes aparecem sem bolinhas nem números (problema anterior à Sprint 8, achado na 8.17). Restaurar `list-style` (`disc`/`decimal`) e o recuo só dentro do `MarkdownText`, sem afetar outras listas do app, mantendo contraste e leitura por leitor de tela; cobrir com Vitest e conferir em 1440 px e 360 px nos dois temas.

**Documentação**

- [x] 8.13 Atualizar `docs/api.md` (campo `history`, limites, `history_invalid`, exemplos nos dois endpoints), `docs/rag-pipeline.md` (passo de reescrita e regra "histórico não é evidência"), `docs/security.md` (prompt injection pelo histórico, dados no `localStorage`), o README ("Decisões", variáveis novas, "Retenção") e `docs/README.md`, se o índice mudar.

**DoD:** `pytest` e `npm run test` passam (junto com lint, format e `vue-tsc`). Sem histórico, o comportamento e o contrato são idênticos aos da Sprint 7. Uma pergunta de continuação é respondida com base nos trechos recuperados pela pergunta reescrita, e o histórico nunca serve como evidência: a camada 1 e a validação de citações continuam decididas pelo código. Os logs não contêm o texto do histórico nem da reescrita. As medições da 8.11 estão registradas. A conversa persiste após recarregar e "Nova conversa" a apaga. `docs/api.md` e o README estão atualizados.
