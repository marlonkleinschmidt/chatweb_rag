# Configuração

Toda configuração vem do ambiente e é lida por `app/core/config.py`. Mudar um valor não exige alteração de código. Segredos ficam só no `.env` (fora do Git); o `.env.example` traz todas as variáveis com valores fictícios.

Os valores marcados "validado na Sprint 3" foram calibrados com o conjunto de [eval.md](eval.md) (PDFs sintéticos; revisar com PDFs reais antes de produção).

| Decisão | Default | Variável |
| --- | --- | --- |
| Chave da OpenAI | — (obrigatória) | `OPENAI_API_KEY` |
| URL base da API no frontend | — | `VITE_API_BASE_URL` |
| Intervalo de polling da UI | 2 s enquanto houver documento `received`/`processing` | `VITE_POLL_INTERVAL_MS` |
| Tamanho máximo do PDF | 20 MB | `MAX_UPLOAD_MB` |
| Máximo de páginas por PDF | 500 | `MAX_PDF_PAGES` |
| Chunk / overlap | 500 / 200 caracteres (validado na Sprint 3) | `CHUNK_SIZE`, `CHUNK_OVERLAP` |
| Chunks recuperados (top-k) | 8 no total, entre todos os documentos selecionados (validado na Sprint 3) | `RETRIEVAL_K` |
| Limiar mínimo de relevância | 0,35 no score normalizado 0–1 (validado na Sprint 3) | `RELEVANCE_THRESHOLD` |
| Modelo de chat / embeddings | Sem default no código; definir no `.env` | `CHAT_MODEL`, `EMBEDDING_MODEL` |
| Temperatura | 0 | `CHAT_TEMPERATURE` |
| Timeout do provedor | 60 s, 1 nova tentativa em erro transitório | `PROVIDER_TIMEOUT_S` |
| Tamanho da pergunta | 3 a 2.000 caracteres | `MAX_QUESTION_CHARS` |
| Documentos por consulta | 1 a 10 | `MAX_DOCUMENTS_PER_QUERY` |
| Trecho exibido por fonte | até 500 caracteres | `EXCERPT_MAX_CHARS` |
| Coleção Chroma | `documents` | `CHROMA_COLLECTION` |
| Diretórios | `data/documents`, `data/chroma`, `data/app.db` | `DOCUMENTS_DIR`, `CHROMA_DIR`, `SQLITE_PATH` |
| CORS | apenas `http://localhost:5173` | `CORS_ORIGINS` |
| Host do backend | `127.0.0.1` (nunca `0.0.0.0` no MVP) | `API_HOST` |

Valores fixos (sem variável):

- Indexação: `202 Accepted` + `BackgroundTasks`, um documento por vez.
- Fuso de exibição: `America/Sao_Paulo`, formato `dd/MM/yyyy HH:mm`.
- Armazenamento de datas: UTC, ISO 8601 com `Z`.
