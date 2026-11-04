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
| Documento pequeno em um só trecho | PDF de 1 página com até 4.000 caracteres de texto extraído vira um único chunk, sem o splitter (0 desliga; tarefa 7.33) | `SMALL_DOCUMENT_MAX_CHARS` |
| Chunks recuperados (top-k) | 8 no total, entre todos os documentos selecionados (validado na Sprint 3) | `RETRIEVAL_K` |
| Limiar mínimo de relevância | 0,35 no score normalizado 0–1 (validado na Sprint 3) | `RELEVANCE_THRESHOLD` |
| Cota mínima por documento | 1 trecho por documento selecionado, só com 2 ou mais documentos e dentro de `RETRIEVAL_K`, com o mesmo limiar (0 desliga; tarefa 7.29) | `MIN_CHUNKS_PER_DOCUMENT` |
| Modelo de chat / embeddings | Sem default no código; definir no `.env` | `CHAT_MODEL`, `EMBEDDING_MODEL` |
| Temperatura | 0 | `CHAT_TEMPERATURE` |
| Timeout do provedor | 60 s, 1 nova tentativa em erro transitório | `PROVIDER_TIMEOUT_S` |
| Tamanho da pergunta | 3 a 2.000 caracteres | `MAX_QUESTION_CHARS` |
| Documentos por consulta | 1 a 10 | `MAX_DOCUMENTS_PER_QUERY` |
| Trecho exibido por fonte | até 500 caracteres | `EXCERPT_MAX_CHARS` |
| Histórico de conversa (PRD §13) | Até 4 trocas (pergunta + resposta) e 4.000 caracteres no total; acima disso, `422 history_invalid`. Com `MAX_HISTORY_TURNS=0`, só `history: []` é aceito | `MAX_HISTORY_TURNS`, `MAX_HISTORY_CHARS` |
| Limites do histórico no frontend | Espelham os do backend (mesmos defaults, 4 e 4.000; manter iguais); o frontend corta as trocas mais antigas antes de enviar. `VITE_MAX_HISTORY_TURNS=0` envia sempre `history: []` | `VITE_MAX_HISTORY_TURNS`, `VITE_MAX_HISTORY_CHARS` |
| Reescrita da pergunta com histórico (PRD §13.7) | `true`: uma chamada extra ao `CHAT_MODEL` por pergunta com histórico, com timeout `PROVIDER_TIMEOUT_S` e sem nova tentativa. Com `false`, a recuperação usa a pergunta original, mas o histórico ainda vai ao prompt de resposta | `QUERY_REWRITE_ENABLED` |
| Coleção Chroma | `documents` | `CHROMA_COLLECTION` |
| Diretórios | `data/documents`, `data/chroma`, `data/app.db` | `DOCUMENTS_DIR`, `CHROMA_DIR`, `SQLITE_PATH` |
| CORS | apenas `http://localhost:5173` | `CORS_ORIGINS` |
| Host do backend | `127.0.0.1` (nunca `0.0.0.0` no MVP) | `API_HOST` |

Valores fixos (sem variável):

- Indexação: `202 Accepted` + `BackgroundTasks`, um documento por vez.
- Fuso de exibição: `America/Sao_Paulo`, formato `dd/MM/yyyy HH:mm`.
- Armazenamento de datas: UTC, ISO 8601 com `Z`.
