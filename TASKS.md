## Sprints e Definition of Done

Seis sprints em sequência; cada uma só começa quando a anterior cumpre sua Definition of Done (DoD). Tarefas `[humano]` exigem ação de uma pessoa e não podem ser feitas por agente. As user stories da v2.0 (US-01 a US-09) estão cobertas pelos critérios "Verificar" da §4 e pelas DoD abaixo.

### Sprint 1 — Base local

- [x] 1.1 Registrar no README as versões de Python e Node usadas.
- [x] 1.2 Revogar a chave OpenAI exposta e gerar uma nova.
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

### Sprint 4 — Design system e interface

- [ ] 4.1 Configurar tokens, fonte, raios e breakpoints (§9).
- [ ] 4.2 Decidir e aplicar a solução de contraste do botão primário (§9.1).
- [ ] 4.3 Criar os componentes base da §9.3 e `locales/pt-BR.ts`.
- [ ] 4.4 Montar layout desktop (sidebar + chat) e celular (abas).
- [ ] 4.5 Integrar upload, polling, lista, remoção com confirmação e estado vazio.
- [ ] 4.6 Integrar chat: seleção, envio por botão/`Enter`, citações `[n]` clicáveis e fontes.
- [ ] 4.7 Exibir o aviso de envio de dados à OpenAI junto ao upload.

**DoD:** o fluxo da §4.4 completo funciona em 1440 px e 360 px, só com teclado, e nenhuma string em inglês aparece na interface.

### Sprint 5 — Revisão do MVP

- [ ] 5.1 Percorrer todos os "Verificar" da §4 e registrar o resultado em `docs/checklist-mvp.md`.
- [ ] 5.2 Conferir contraste (WCAG AA), foco, labels e ausência de rolagem horizontal.
- [ ] 5.3 Conferir logs: nenhum conteúdo de PDF, pergunta, resposta ou chave.
- [ ] 5.4 Registrar duração de indexação e de consulta (p50 em 20 execuções) e custo estimado por documento e por consulta.
- [ ] 5.5 Documentar no README: backup, retenção, limitações (OCR, volume, multiusuário).

**DoD:** checklist da §4 100% aprovado ou com desvios documentados; medições da 5.4 registradas na §11.2.

### Sprint 6 — Testes e Docker

- [ ] 6.1 Pytest: validação de upload, transições de estado, regra de evidência (com retriever e LLM falsos), endpoints de documentos.
- [ ] 6.2 Vitest: `useDocuments` e `useChat` com `fetch` simulado.
- [ ] 6.3 Converter as perguntas de `docs/eval.md` em teste de regressão opcional (roda só com chave configurada).
- [ ] 6.4 Dockerfile do backend sem segredo; build estático do frontend; volume para `data/`.
- [ ] 6.5 Documentar execução com e sem Docker.

**DoD:** `pytest` e `npm run test` passam; `docker compose up` sobe a aplicação com os dados persistindo após reinício.
