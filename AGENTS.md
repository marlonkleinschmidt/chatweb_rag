# AGENTS.md

Instruções para agentes de código (OpenCode) neste repositório.

## Estado atual

- **Sprints 1–6 do PRD §10 concluídas** (MVP completo: backend FastAPI, frontend Vue 3, testes e Docker). Testes: `pytest` (backend, 45 unitários) e `npm run test` (frontend, 27); regressão opcional e paga com `pytest -m regression` (só com chave no `.env`). Docker: `docker compose up -d` (ver README).
- Fontes de verdade, em ordem: `PRD.md` (v2.1) → `README.md` seção **"Decisões"** (registra a implementação real e todo desvio do PRD) → `docs/` (resumo por tema). Em conflito dentro do PRD: §1 → §3 → §4–§7 → demais.
- O `CLAUDE.md` está desatualizado na seção "Estado do projeto" (diz que não há código). Este arquivo reflete o estado real.
- `TASKS.md` espelha o §10 do PRD: ao concluir uma tarefa, marque `[X]` nos **dois**.

## Como trabalhar

- Uma tarefa do PRD §10 por vez, na ordem. Marque `[X]` só quando o critério "Verificar" passar.
- Só dependências do PRD §8.1, fixadas com `==` no `requirements.txt` (só diretas; `chromadb` e `openai` são transitivas e ficam de fora). Precisa de outra? Pare e justifique antes.
- Ambiguidade **barata** de desfazer: opção mais simples + registro em `README.md` ("Decisões"). **Cara** (formato persistido, contrato de API, dependência nova): pare e pergunte.
- Ao terminar: informe arquivos alterados, como verificar manualmente e qualquer desvio.
- Tarefas `[humano]` não são de agente.

## Comandos

Backend (Python 3.12 — na máquina há 3.14 como default, use `py -3.12`):

```bash
cd backend
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # Linux/macOS: .venv/bin/python
cp .env.example .env                     # preencha OPENAI_API_KEY

.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
.venv/Scripts/ruff check .
.venv/Scripts/ruff format --check .      # sem --check para formatar
.venv/Scripts/python -m pytest           # 45 unitários (offline, custo zero)
.venv/Scripts/python -m pytest -m regression   # 15 perguntas do docs/eval.md contra a OpenAI real (custo ≈ US$ 0,001; skip sem chave)
```

Frontend:

```bash
cd frontend
npm install && cp .env.example .env
npm run dev          # porta 5173 com strictPort: se ocupada, falha (não troque a porta; o CORS só aceita 5173)
npm run test         # vitest (27 testes de useDocuments/useChat)
npm run lint
npm run format:check # npm run format para formatar
npm run type-check   # vue-tsc
npm run build
```

Verificação rápida: `curl http://127.0.0.1:8000/api/v1/health` → `{"status":"ok"}`; a página em http://localhost:5173 mostra "Servidor: conectado". O servidor Playwright MCP (configurado no `opencode.json`) é a ferramenta para os critérios "Verificar" de UI e acessibilidade.

## Regras que não são óbvias

- **Idioma:** código, identificadores, nomes de arquivo e comentários em **inglês**; todo texto visível ao usuário (incluindo `message` de erro da API e `aria-label`) em **pt-BR**.
- **Aspas simples** em Python e TS/JS. Ruff: `line-length = 88`, regras `E,F,I,B`. Prettier: `semi: false`, `printWidth: 100`. Sem `any` no TS.
- **Erros da API** sempre no envelope `{"error": {"code", "message"}}` (`code` estável em inglês; `message` pt-BR segura). Nunca exponha stack trace, caminho de arquivo, mensagem crua do provedor ou `storage_path`.
- **Tipos do LangChain nunca atravessam o contrato HTTP** — converta para os schemas Pydantic (espelhados em `frontend/src/types/api.ts`).
- **Logs** só com IDs, contagens, `duration_ms` e `error_code` — nunca conteúdo de PDF, pergunta, resposta ou chave. Pergunta e texto vão sempre no corpo da requisição, nunca em query string.
- **Páginas do `pypdf` são base 0** — grave e exiba sempre base 1. Datas: grava em UTC (ISO 8601 com `Z`), exibe em `America/Sao_Paulo` (`dd/MM/yyyy HH:mm`).
- **Nada de hex fora do `@theme`** em `frontend/src/style.css` (Tailwind 4, sem `tailwind.config`). Componentes usam só tokens semânticos (`canvas`, `surface`, `primary`...) — nunca `dark:` nem `app-*` nos templates. O tema é a classe `dark` no `<html>`, aplicada por um script inline no `index.html` (sem flash).
- **Configuração:** todo valor vem de `app/core/config.py` (Pydantic Settings) — nada de valor mágico no código. `CHAT_MODEL` e `EMBEDDING_MODEL` não têm default; o health sobe sem chave.
- **Nunca defina `OPENAI_LOG` nem `LANGSMITH_TRACING`** — `debug`/`true` vazam perguntas e trechos para logs/LangSmith.

## Arquitetura em uma página

- **Backend** (`backend/app/`): `api/` só valida HTTP e delega. Toda a lógica em **dois serviços apenas**: `services/document_service.py` (ingestão/remoção) e `services/rag_service.py` (consulta). `db.py` acessa SQLite com `sqlite3` puro e SQL escrito à mão. Frontend: `composables/` (`useDocuments`, `useChat`, `useTheme`), `services/api.ts` com `fetch`, todos os textos da UI em `locales/pt-BR.ts` (objeto simples, sem i18n).
- **Estados do documento:** `received → processing → ready/failed`. Órfãos de `received`/`processing` no startup viram `failed / processing_interrupted`. Indexação sequencial (`threading.Lock`), um PDF por vez, via `BackgroundTasks` com retorno `202`.
- **Remoção** na ordem vetores → arquivo → registro, passos idempotentes; falha parcial vira `delete_partial` e um novo `DELETE` repete tudo. IDs de vetor no Chroma: `{document_id}:{chunk_index}`.
- **Evidência em duas camadas, decidida em código:** camada 1 (nenhum chunk ≥ `RELEVANCE_THRESHOLD` → resposta fixa sem chamar o LLM) e camada 2 (descarta `claim` com `cited` vazio/inválido). O código, não o modelo, escreve os marcadores `[n]` (`_assemble_answer` no `rag_service`).
- **Prompt:** constante versionada `ANSWER_PROMPT_V2` em `services/prompts.py`. Qualquer mudança = nova versão + registro no README com data e motivo. `prompts.py` guarda só a versão em uso.
- **Backend só em `127.0.0.1`**, CORS só de `http://localhost:5173`. Não exponha na rede/internet.

## Pontos de atenção do ambiente

- **Caminhos de dados (`DOCUMENTS_DIR`, `CHROMA_DIR`, `SQLITE_PATH`) são relativos ao diretório onde o uvicorn roda** — rodando a partir de `backend/`, os dados ficam em `backend/data/` (não no `data/` da raiz). Ambos são ignorados pelo Git.
- **No Docker, os dados ficam no volume `rag-assistant-data`** (`docker-compose.yml`), independente do `backend/data` local — os dois modos não compartilham dados. `backend/.env` é obrigatório para `docker compose up` (segredo via `env_file`, nunca na imagem).
- **Testes backend:** o `conftest.py` isola dados em `tmp_path` e mascara a chave da OpenAI — o `pytest` padrão nunca chama a API (a regressão fica fora via `addopts` no `backend/pytest.ini`); `pytest -m regression` roda as 15 perguntas do `docs/eval.md` com a chave real. Novo teste que insira vetores deve usar a classe `Embeddings` falsa (o `add_texts` do langchain-chroma, sem embedding function, baixaria o modelo ONNX de 79 MB).
- `CORS_ORIGINS` é uma **lista JSON** no `.env` (formato do pydantic-settings).
- `VITE_MAX_DOCUMENTS_PER_QUERY` e `VITE_MAX_QUESTION_CHARS` (frontend) **espelham** os valores do backend e precisam ser iguais.
- Mudar `EMBEDDING_MODEL`, `CHUNK_SIZE` ou `CHUNK_OVERLAP` **não reindexa** o que já existe: vetores antigos ficam com o formato antigo (aviso `embedding_model_changed`); para aplicar, remova e reenvie o documento.
- Backup = copiar `backend/data/` inteiro **com o backend parado** (catálogo, vetores e arquivos se referem uns aos outros).

## Agentes especializados

`agents/*.md` define subagentes (formato Claude Code, em `.claude/agents/`): backend-fastapi, rag-langchain, frontend-vue, qa-playwright. O `agents/README.md` diz quando usar cada um; `docs/api.md` é a fronteira backend/frontend — nenhum lado muda o contrato sem perguntar.

## Referências

- `PRD.md` §3 (defaults e variáveis), §5 (contratos da API), §6.3 (prompt), §10 (tarefas/DoD).
- `docs/README.md`: índice por tema (api, configuration, rag-pipeline, design-system, security, eval).
