# Arquitetura

Frontend Vue 3 (tela única) conversa via HTTP com um backend FastAPI local. O backend guarda o catálogo no SQLite, os arquivos em disco e os vetores no Chroma, e chama a OpenAI para embeddings e respostas.

## Estrutura de diretórios

```text
project/
├── backend/
│   ├── app/
│   │   ├── main.py              # app, CORS, handler de erros, startup
│   │   ├── db.py                # sqlite3 e consultas
│   │   ├── api/                 # routes_documents.py, routes_chat.py
│   │   ├── core/                # config.py, errors.py
│   │   ├── schemas/             # document.py, chat.py, error.py
│   │   └── services/            # document_service.py, rag_service.py, prompts.py
│   ├── requirements.txt
│   ├── ruff.toml
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/          # ui/ (base) e domain/ (documento, chat)
│   │   ├── composables/         # useDocuments.ts, useChat.ts
│   │   ├── services/            # api.ts
│   │   ├── types/               # api.ts (espelha os schemas)
│   │   ├── locales/             # pt-BR.ts (todos os textos da UI)
│   │   ├── App.vue
│   │   └── main.ts
│   └── package.json
├── data/                        # ignorado pelo Git
├── docs/
└── README.md
```

## Responsabilidades

| Módulo | Responsabilidade |
| --- | --- |
| `api/` | Validar HTTP e delegar aos serviços |
| `services/document_service.py` | Ingestão: validação, extração, divisão, embeddings, remoção |
| `services/rag_service.py` | Consulta: recuperação, regra de evidência, chamada ao modelo |
| `services/prompts.py` | Prompts versionados (`ANSWER_PROMPT_V2`) |
| `db.py` | Acesso ao SQLite |
| `core/config.py` | Configuração (Pydantic Settings) |
| `core/errors.py` | Erros com `code` estável |
| `frontend/src/types/api.ts` | Tipos que espelham os schemas do backend |

## Modelo de dados

Só a tabela `documents` existe no SQLite. Chunks vivem apenas no Chroma. Mensagens de chat não são persistidas.

```sql
CREATE TABLE IF NOT EXISTS documents (
    id            TEXT PRIMARY KEY,           -- UUID v4
    filename      TEXT NOT NULL,              -- nome original, só para exibição
    storage_path  TEXT NOT NULL,              -- relativo a DOCUMENTS_DIR
    sha256        TEXT NOT NULL,
    size_bytes    INTEGER NOT NULL,
    status        TEXT NOT NULL CHECK (status IN ('received', 'processing', 'ready', 'failed')),
    error_code    TEXT,
    error_message TEXT,
    page_count    INTEGER,
    chunk_count   INTEGER,
    created_at    TEXT NOT NULL,              -- ISO 8601 UTC
    updated_at    TEXT NOT NULL               -- ISO 8601 UTC
);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents (created_at DESC);
```

Metadados de cada vetor no Chroma: `document_id`, `filename`, `page`, `chunk_index`, `embedding_model`, `created_at`, `updated_at`.

## Armazenamento

| Dado | Local padrão |
| --- | --- |
| PDFs | `data/documents/{document_id}.pdf` |
| Vetores | `data/chroma`, coleção `documents` |
| Catálogo | `data/app.db` |

O nome original do arquivo nunca compõe caminho; vai só para o SQLite.

## Regras de integridade

- **Indexação sequencial:** uma tarefa por vez, via `BackgroundTasks` e um `threading.Lock` no `document_service`.
- **Reinício:** documentos em `received` ou `processing` passam a `failed` no startup, com a mensagem "Processamento interrompido. Remova e envie novamente."
- **Remoção** (ordem fixa): vetores → arquivo → registro. Se um passo falhar, o registro fica com `delete_partial` e um novo `DELETE` repete todos os passos (cada um é idempotente).
- **IDs de vetor determinísticos:** `{document_id}:{chunk_index}`.
- **Troca de modelo de embedding:** vetores de outro `EMBEDDING_MODEL` são incompatíveis. No startup, o backend registra aviso no log; `GET /documents` retorna `embedding_model_changed: true` e a UI orienta: "O modelo de embeddings mudou. Remova e envie os documentos novamente."
- **Backup:** copiar a pasta `data/` inteira com o backend parado.
