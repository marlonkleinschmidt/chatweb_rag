# Agentes

Agentes de IA que formam o time de desenvolvimento do **Assistente RAG para documentos**. Cada um é especialista em uma parte da stack definida no [PRD](../PRD.md) e segue a [documentação do projeto](../docs/README.md).

Os arquivos usam o formato de subagente do Claude Code (frontmatter `name`/`description` + prompt). Para usá-los no Claude Code, copie os arquivos dos agentes (não este README) para `.claude/agents/`.

## Índice

| Agente | Arquivo | Responsabilidade | MCP |
| --- | --- | --- | --- |
| Backend FastAPI | [backend-fastapi.md](backend-fastapi.md) | API, configuração, SQLite, validação de upload, erros, ciclo de vida dos documentos | context7 |
| Engenheiro RAG | [rag-langchain.md](rag-langchain.md) | Ingestão de PDFs, Chroma, recuperação, regra de evidência, prompt | context7 |
| Frontend Vue + Tailwind | [frontend-vue.md](frontend-vue.md) | Interface, design system, composables, integração com a API, acessibilidade | context7 |
| QA / Tester | [qa-playwright.md](qa-playwright.md) | Verificar requisitos e design no sistema rodando; testes automatizados na Sprint 6 | playwright |

## Quando usar cada um

| Situação | Agente |
| --- | --- |
| Criar ou alterar rota, schema Pydantic, `config.py`, `errors.py`, `db.py`, `main.py` | Backend FastAPI |
| Upload, validação de arquivo, estados `received → processing → ready/failed`, remoção, startup | Backend FastAPI |
| Ruff, `requirements.txt`, `.env.example`, Dockerfile (Sprint 6) | Backend FastAPI |
| Extração de páginas, chunking, embeddings, gravação ou busca no Chroma | Engenheiro RAG |
| `rag_service.py`, `prompts.py`, regra "sem evidência", montagem de `sources` | Engenheiro RAG |
| Ajuste de `CHUNK_SIZE`, `RETRIEVAL_K`, `RELEVANCE_THRESHOLD` com base em `docs/eval.md` | Engenheiro RAG |
| Componentes Vue, layout, tokens Tailwind, `locales/pt-BR.ts`, ESLint/Prettier | Frontend Vue + Tailwind |
| `useDocuments`, `useChat`, `services/api.ts`, `types/api.ts`, polling | Frontend Vue + Tailwind |
| Conferir o critério "Verificar" de um requisito ou a DoD de uma sprint | QA / Tester |
| Validar design, responsividade (1440 px e 360 px), teclado e textos em pt-BR | QA / Tester |
| Pytest e Vitest (só na Sprint 6) | QA / Tester |

## Divisão por sprint

| Sprint | Agentes principais |
| --- | --- |
| 1 — Base local | Backend (1.3–1.6, 1.8 Python), Frontend (1.7, 1.8 TS), QA (DoD) |
| 2 — Catálogo e ingestão | Backend (2.1, 2.2, 2.5–2.7), RAG (2.3, 2.4), QA (DoD) |
| 3 — Consulta RAG | RAG (3.1–3.3, 3.5, 3.6), Backend (3.4), QA (DoD) |
| 4 — Design system e interface | Frontend (4.1–4.7), QA (DoD) |
| 5 — Revisão do MVP | QA (5.1–5.3), RAG (5.4), Backend (5.5) |
| 6 — Testes e Docker | QA (6.1–6.3), Backend (6.4, 6.5) |

Tarefas `[humano]` (como a 1.2) não são atribuídas a nenhum agente.

## Regras comuns a todos os agentes

- Seguir o [CLAUDE.md](../CLAUDE.md) e o [fluxo de trabalho](../docs/workflow.md): uma tarefa por vez e só marcar `[X]` quando o critério "Verificar" passar.
- Não criar nada fora do escopo da sprint atual nem arquivos vazios "para o futuro".
- Ao terminar, informar os arquivos alterados, como verificar e qualquer desvio do PRD.
- Quando a tarefa envolver backend e frontend, o contrato da API ([docs/api.md](../docs/api.md)) é a fronteira: nenhum lado muda o contrato sem perguntar antes.
