## Sprints e Definition of Done

Os Sprints 1–6 formam o MVP e foram concluídos; a Sprint 7 adiciona a funcionalidade pós-MVP da §12 do PRD (v2.2) e segue as mesmas regras: cada sprint só começa quando a anterior cumpre sua Definition of Done (DoD), e tarefas `[humano]` exigem ação de uma pessoa e não podem ser feitas por agente. As user stories da v2.0 (US-01 a US-09) estão cobertas pelos critérios "Verificar" da §4 do PRD e pelas DoD abaixo; as da v2.2 (US-10 a US-13), pela §12.2 do PRD.

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

### Sprint 7 — Exibição opcional das fontes (PRD §12)

**Backend**

- [ ] 7.1 Campo `show_sources` e código de erro: `show_sources: bool = Field(default=True)` em `ChatRequest` e schema derivado `ChatStreamRequest` com default `False` (`backend/app/schemas/chat.py`); `STREAM_SOURCES_UNSUPPORTED` em `ErrorCode` (`backend/app/core/errors.py`, mensagem pt-BR e status 422 da §5.3); espelhar o campo em `frontend/src/types/api.ts` (`ChatRequest.show_sources: boolean`).
  - Pronto quando: request sem o campo vale `true` no `/chat/query` (cliente existente inalterado) e `false` no `/chat/query/stream`, e o OpenAPI documenta os dois defaults.
- [ ] 7.2 Resposta JSON sem marcadores em `backend/app/services/rag_service.py`: `answer_question` e `_assemble_answer` aceitam o modo sem fontes — claims válidos montados sem `[n]` (variante de `_claim_sentence`), parágrafos fixos (partes não encontradas, claims não vinculados) mantidos, `sources: []`; camadas 1 e 2 intactas.
  - Pronto quando: `POST /chat/query` com `show_sources=false` devolve `answer` sem `\[\d+\]` e `sources: []`, e claims sem citação válida continuam descartados.
- [ ] 7.3 Prompt sem fontes: `ANSWER_NO_SOURCES_PROMPT_V1` em `backend/app/services/prompts.py` (novo) — regras de grounding e defesa contra prompt injection herdadas do `ANSWER_PROMPT_V2` (regras 1 e 5–8), resposta em texto corrido com formatação markdown simples (títulos curtos, negrito, itálico, listas, código em linha e em bloco; sem tabelas, links, imagens ou HTML) e sem marcadores `[n]`, parágrafo "Não encontrei nos documentos selecionados: …" para partes sem resposta; `ANSWER_PROMPT_V2` inalterado.
  - Pronto quando: prompt versionado em uso e registro no README ("Decisões") com data e motivo.
- [ ] 7.4 Filtro de marcadores em streaming em `rag_service.py`: classe `_MarkerStreamFilter` (nova) com `feed(text) -> str` e `flush() -> str`, reusando `MODEL_MARKER_PATTERN`, `WHITESPACE_PATTERN` e `SPACE_BEFORE_PUNCTUATION_PATTERN`; buffer retém o sufixo que pode ser início de marcador; colchete incompleto no `flush` permanece como texto literal; a limpeza de espaços duplos e espaço antes de pontuação é local aos pontos de remoção, preservando quebras de linha e listas do markdown.
  - Pronto quando: a concatenação de todos os `feed` + `flush` equivale ao filtro aplicado ao texto completo, inclusive com `[` num chunk e `3]` no seguinte.
- [ ] 7.5 Gerador de stream em `rag_service.py`: `stream_answer(request)` (nova) — validação e recuperação como na §6.2 (camada 1 devolve a resposta fixa como delta único), geração com `ChatOpenAI(...).stream` (sem `with_structured_output`) e o prompt da 7.3, deltas filtrados pela 7.4, um único `done` com `has_evidence`; falhas do provedor durante a geração viram `AppError` tratado pela rota.
  - Pronto quando: o gerador emite deltas concatenáveis e exatamente um `done`; erros de validação/recuperação acontecem antes do primeiro evento.
- [ ] 7.6 Endpoint `POST /chat/query/stream` em `backend/app/api/routes_chat.py`: recebe `ChatStreamRequest` (default `show_sources=false`) e rejeita `show_sources=true` explícito com `422 stream_sources_unsupported`; valida e recupera antes de abrir o stream (erros 409/502/504 como envelope JSON com status, §12.6); `StreamingResponse` com `text/event-stream` e `Cache-Control: no-cache`, eventos `delta`/`done`/`error`; desconexão do cliente encerra o gerador e a iteração do modelo (cancelamento real no backend, não só o cliente parando de ler); `query_done` ganha `show_sources`, `stream` e `first_token_ms` (sem conteúdo).
  - Pronto quando: `curl -N` mostra os eventos na ordem e um erro na geração vira evento `error` seguido do fim da conexão.

**Frontend**

- [ ] 7.7 `streamChat()` em `frontend/src/services/api.ts`: `fetch` POST com `AbortSignal`; rejeita status/`Content-Type` inesperados como `UNEXPECTED_RESPONSE`; lê `response.body.getReader()` com `TextDecoder` em modo stream, faz parse dos eventos `data:` (buffer até `\n\n`) e chama `onDelta`/`onDone`; envelope `error` vira `ApiError` (antes e durante o stream).
  - Pronto quando: eventos divididos entre chunks de rede e caracteres UTF-8 divididos são montados corretamente.
- [ ] 7.8 Novo `frontend/src/composables/useShowSources.ts`: `showSources` (default `true`), persistência em `localStorage` na chave `show_sources` com try/catch, no padrão do `useTheme.ts` (RF-19).
  - Pronto quando: a escolha sobrevive ao recarregamento e storage bloqueado não quebra o app.
- [ ] 7.9 Toggle "Exibir fontes" no `frontend/src/components/domain/ChatPanel.vue`: checkbox nativo com label e hint (`locales/pt-BR.ts`: `chat.showSourcesLabel`, `chat.showSourcesHint`) junto ao formulário da pergunta; navegável por `Tab`, contraste AA nos dois temas, sem `dark:` nem `app-*`; todo envio leva `show_sources` explícito.
  - Pronto quando: alternar o toggle muda o formato da próxima resposta e não afeta as anteriores da sessão (RF-20).
- [ ] 7.10 Streaming no `frontend/src/composables/useChat.ts`: `send(question, documentIds, showSources)` (default `true`) escolhe `/chat/query` ou `/chat/query/stream`; no modo streaming a entrada de assistente nasce vazia e cresce a cada delta (mesmo `id`); `stop()` via `AbortController` mantém o parcial; erro no meio mantém o parcial e adiciona entrada de erro; botão "Parar" (`locales/pt-BR.ts`: `chat.stop`) com `BaseButton` no `ChatPanel.vue` durante a geração.
  - Pronto quando: os testes atuais do `useChat` passam sem alteração de semântica (caminho com fontes) e os novos cobrem o caminho streaming.

- [ ] 7.11 Renderização markdown segura no chat: dependência `markdown-it` (versão fixada no `frontend/package.json`, única nova da sprint, PRD §8.1); novo `frontend/src/components/domain/MarkdownText.vue` com `html: false`, `linkify: false` e regras de link e imagem desativadas — único `v-html` do app, exceção documentada ao "sem v-html" do `ChatMessage` (e ao lint `vue/no-v-html`, se o preset o ativar); `ChatEntry` de assistente ganha `markdown: boolean` (novo) em `useChat.ts`, `true` apenas no modo streaming; `ChatMessage.vue` usa `MarkdownText` quando `markdown` é `true`, re-processando o texto acumulado a cada delta, e mantém o caminho com fontes exatamente como hoje.
  - Pronto quando: o subconjunto da §12.3 renderiza (lista, negrito, código), HTML cru aparece como texto, nenhum link ou imagem é renderizado e respostas com fontes continuam texto puro.

**Testes**

- [ ] 7.12 Pytest do filtro (novo `backend/tests/test_marker_filter.py`): `[1]` inteiro; `[` num chunk e `3]` no seguinte; `[1, 2]` e `[1-3]`; espaços duplos e espaço antes de pontuação após a remoção; `[anexo]` preservado; `[` solto no fim mantido; equivalência com o filtro aplicado ao texto completo; remoção de marcador preservando quebras de linha e listas do markdown (limpeza local).
- [ ] 7.13 Pytest de endpoints: `/chat/query` sem fontes (fake retriever/LLM no padrão do `test_evidence_rule.py`, camadas 1 e 2); `/chat/query/stream` com fake no ponto de chamada ao modelo — eventos delta/done, omissão de `show_sources` → responde sem fontes, `show_sources=true` explícito → `422 stream_sources_unsupported`, `document_not_ready` → 409 JSON antes do stream, falha na geração → evento `error`, camada 1 → delta único + `done` com `has_evidence=false`.
- [ ] 7.14 Vitest: `useShowSources` (default, persistência, storage bloqueado); `useChat` no modo streaming (deltas na mesma entrada, `markdown: true`, `stop`, erro no meio, payload com `show_sources: false` e sem histórico); parser do `streamChat` com helper de resposta SSE no `__tests__/testUtils` (evento dividido entre chunks, UTF-8 dividido); `MarkdownText` (subconjunto renderiza; `<script>`, atributos `on*` e HTML cru viram texto; `[x](javascript:...)` e imagens não renderizam; markdown parcial durante o streaming não quebra o render).
- [ ] 7.15 Regressão opcional (com chave): estender `backend/tests/test_regression_eval.py` para rodar as 15 perguntas do `docs/eval.md` também com `show_sources=false` (JSON), comparar `has_evidence` e custo com o modo com fontes e registrar TTFT p50/p90 (`first_token_ms`) em execuções repetidas, para confirmar ou ajustar a meta provisória da §12.4.
- [ ] 7.16 Verificação manual com Playwright MCP dos critérios "Verificar" de RF-20 a RF-24 e da §12.9: alternar o toggle nos dois sentidos, recarregar a página, observar o texto crescendo e o markdown renderizando, Parar, navegação por teclado e 360 px nos dois temas.

**Documentação**

- [ ] 7.17 Atualizar `docs/api.md` (endpoint novo, `show_sources`, eventos SSE com exemplos — incluindo que `delta.text` é markdown —, `stream_sources_unsupported`), o README ("Decisões": prompt novo, streaming, `markdown-it`, premissas da §12.8) e `docs/README.md` se o índice mudar.

**DoD:** `pytest` e `npm run test` passam (junto com lint, format e `vue-tsc`); com o toggle ligado, comportamento e contrato idênticos aos atuais (texto puro com `[n]` e fontes); com o toggle desligado, a resposta renderizada não contém `\[\d+\]` nem painel de fontes, chega incrementalmente e é renderizada como markdown seguro (HTML cru nunca executa); a preferência persiste após recarregar; TTFT (`first_token_ms`) medido com o conjunto de avaliação e a meta da §12.4 confirmada ou ajustada; `docs/api.md` e README atualizados.
