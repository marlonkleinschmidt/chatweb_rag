# Assistente RAG para documentos

Aplicação web local: envie PDFs, faça perguntas e receba respostas em pt-BR com citações para página e trecho. Especificação completa em [`PRD.md`](PRD.md); resumo por tema em [`docs/`](docs/README.md).

## Versões usadas

| Ferramenta | Versão |
| --- | --- |
| Python | 3.12.0 |
| Node.js | 22.18.0 |
| npm | 11.5.2 |

## Instalação

Pré-requisitos: Python 3.12 (o PRD aceita 3.11 ou 3.12; no Windows use `py -3.12`) e Node.js 22.

### Backend

```bash
cd backend
py -3.12 -m venv .venv                     # Linux/macOS: python3.12 -m venv .venv
.venv/Scripts/python -m pip install -r requirements-dev.txt   # Linux/macOS: .venv/bin/python
cp .env.example .env                       # preencha OPENAI_API_KEY (nunca versione o .env)
```

`requirements.txt` tem só as dependências de execução; `requirements-dev.txt` acrescenta o Ruff.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env
```

## Execução

São dois processos, cada um em um terminal.

```bash
# Terminal 1: backend em http://127.0.0.1:8000
cd backend
.venv/Scripts/python -m uvicorn app.main:app --host 127.0.0.1 --port 8000

# Terminal 2: frontend em http://localhost:5173
cd frontend
npm run dev
```

Verificação rápida: `curl http://127.0.0.1:8000/api/v1/health` retorna `{"status":"ok"}`, e a página em http://localhost:5173 mostra "Servidor: conectado".

## Lint, formatação e tipos

```bash
# backend/
.venv/Scripts/ruff check .
.venv/Scripts/ruff format --check .        # sem --check para formatar

# frontend/
npm run lint
npm run format:check                       # npm run format para formatar
npm run type-check
npm run build
```

## Decisões

Escolhas que não estavam no PRD, ou que o adaptam, registradas conforme o PRD §1.

### Sprint 1

**Ambiente e dependências**

- **Python 3.12.0**, e não o 3.14 instalado como padrão na máquina, porque o PRD §8.1 pede 3.11 ou 3.12.
- **`requirements.txt` só com o que é usado agora** (`fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`). As dependências de RAG, o `python-multipart` e o `pypdf` entram nas sprints que as usam. O Ruff fica em `requirements-dev.txt`.
- **A 1.3 não tinha scripts para limpar**: o repositório não contém scripts do protótipo. A chave é lida só do ambiente (`OPENAI_API_KEY` em `core/config.py`).

**Configuração**

- **`OPENAI_API_KEY`, `CHAT_MODEL` e `EMBEDDING_MODEL` são opcionais na configuração**, com valor `None`, para que o health suba sem chave. Não há modelo padrão no código. A partir da Sprint 3, o `rag_service` deve devolver um erro no envelope quando faltarem.
- **`CORS_ORIGINS` é uma lista JSON no `.env`** (`["http://localhost:5173"]`), o formato padrão do pydantic-settings.
- **Host e porta vão na linha de comando do uvicorn.** `API_HOST` existe na configuração, mas não é lido por ele.
- **Caminhos de dados relativos ao diretório onde o uvicorn roda.** Rodando a partir de `backend/`, os dados ficam em `backend/data/`, e não no `data/` da raiz (§8.4). Os dois são ignorados pelo Git. Para usar a raiz, defina `DOCUMENTS_DIR=../data/documents` (e os demais caminhos) no `.env`.
- **Mínimos fixos** (pergunta com 3 caracteres, consulta com 1 documento) são constantes em `core/config.py`, porque o PRD só dá variável para os máximos.

**API**

- **Códigos de erro além da §5.3**, a confirmar: `invalid_request` (422, outros erros de validação), `not_found` (404, rota inexistente) e `method_not_allowed` (405). Qualquer erro de validação no campo `question` vira `question_invalid`.
- **Erros 500 são tratados por um middleware**, para que a resposta mantenha os cabeçalhos de CORS e o log não mostre o traceback. O log registra só o `error_code`, o tipo da exceção, o método e a rota.

**Frontend**

- **O tema do Tailwind 4 fica no CSS**, no bloco `@theme` de `src/style.css`, sem `tailwind.config`. Esse é o único lugar com cores hexadecimais. A paleta padrão do Tailwind está desligada, e a fonte Inter fica para a Sprint 4.
- **TypeScript fixado em 6.0.3**, porque o typescript-eslint ainda não suporta a versão 7.
- **Porta 5173 obrigatória** (`strictPort`): se estiver ocupada, o Vite falha em vez de trocar para outra porta que o CORS bloquearia.
- **Códigos de erro só do frontend:** `network_error`, `unexpected_response` e `config_missing`, com mensagens em `locales/pt-BR.ts`.
- **`npm audit` mostra um aviso moderado no `minimatch`.** Ele é dependência de desenvolvimento do ESLint e não entra no build. A correção sugerida faria o ESLint voltar para a versão 4, então não foi aplicada.

### Sprint 2

**Catálogo (`db.py`)**

- **Datas com precisão de segundos** (`2026-11-03T15:08:00Z`), como no exemplo da §5.1. A listagem desempata envios do mesmo segundo pelo `rowid`, do mais novo para o mais antigo.
- **Uma conexão SQLite por operação**, sem pool. A tabela e os diretórios de dados são criados no startup (`db.init()`, chamado no `lifespan`).
- **`update_status` só aplica as transições da §5.2** (`received → processing`, `processing → ready`, `received/processing → failed`) e devolve `False` quando a transição não é permitida ou o documento não existe. `error_code` e `error_message` são sobrescritos a cada chamada; `page_count` e `chunk_count` só mudam quando informados.
- **`page_count` fica `null` em `received`.** O upload conta as páginas para validar o limite, mas quem grava o valor é a indexação.

**Upload (`POST /documents`)**

- **Ordem das validações:** tamanho → vazio → extensão → assinatura `%PDF-` → leitura pelo `pypdf` (criptografia e número de páginas). O arquivo é lido até `MAX_UPLOAD_MB` + 1 byte, sem carregar além do limite.
- **A extensão `.pdf` é comparada sem diferenciar maiúsculas** (`.PDF` é aceito).
- **PDF que o `pypdf` não consegue abrir vira `422 file_not_pdf`**, mesmo começando com `%PDF-`.
- **Requisição sem o campo `file` retorna `422 invalid_request`.**
- **O nome exibido é só o nome base do arquivo**: qualquer caminho enviado pelo cliente (`/` ou `\`) é descartado. Em disco, o arquivo é sempre `{document_id}.pdf`, e `storage_path` guarda só esse nome, relativo a `DOCUMENTS_DIR`.
- **Se a gravação do registro falhar, o arquivo já salvo é apagado**, para não deixar PDF órfão.
- **Aviso de duplicado do RF-01, aprovado pelo usuário como mudança no contrato da API (registrado no PRD §5.1).** A resposta do `POST /documents` usa o schema `DocumentUploadResponse`, que estende `Document` com o campo opcional `warning`. Quando já existe um documento com o mesmo SHA-256, o upload é aceito normalmente (novo ID, indexação normal) e `warning` traz "Este arquivo já foi enviado."; nos outros casos vem `null`. As respostas de `GET` não têm o campo. No frontend, o tipo é `DocumentUploadResponse` em `types/api.ts`.

**Indexação em background (`index_document`)**

- **Dependências de RAG fixadas:** `langchain-core==1.7.4`, `langchain-openai==1.7.3`, `langchain-chroma==1.1.0`, `langchain-community==0.4.2` e `langchain-text-splitters==1.1.3`. O `chromadb`, o `openai` e o `langchain-classic` vêm como dependências transitivas e não estão no `requirements.txt`. O `langchain-community` mostra um aviso de que está sendo descontinuado, mas continua sendo a fonte do `PyPDFLoader` exigido pela §6.1.
- **O `openai` não é importado direto.** Para identificar erros do provedor, o código compara o módulo e o nome da classe da exceção (`APITimeoutError` vira `provider_timeout`; qualquer outra exceção do pacote `openai`, `provider_error`).
- **Os embeddings fazem 1 nova tentativa** (`max_retries=1`) com timeout de `PROVIDER_TIMEOUT_S`, como o chat da §6.2. O padrão do `langchain-openai` seria 2.
- **Falta de `OPENAI_API_KEY` ou `EMBEDDING_MODEL` faz o documento terminar em `failed / provider_error`.** O upload continua sendo aceito sem chave.
- **Outras falhas** (PDF ilegível na extração, erro do Chroma, configuração inválida, como `CHUNK_OVERLAP` maior que `CHUNK_SIZE`) viram `failed / internal_error`. O `error_message` gravado é sempre a mensagem pt-BR da §5.3, nunca o texto do provedor.
- **Em qualquer falha, os vetores parciais do documento são apagados** antes de marcar `failed`.
- **O RF-08 compara o texto de cada página sem espaços nas pontas** (`strip`) com o limite de 20 caracteres. Um documento `failed / pdf_no_text` fica com `page_count` e `chunk_count` nulos.
- **`chunk_index` é sequencial no documento inteiro** (0 a n−1), não por página. `created_at` e `updated_at` dos vetores são o momento da indexação.
- **A gravação no Chroma usa `upsert`** (comportamento do `langchain-chroma`) em uma única chamada. Nos limites do MVP (500 páginas) o número de chunks fica abaixo do lote máximo do Chroma.
- **Os logs da aplicação usam um handler próprio no logger `app`**, em nível INFO, configurado no `main.py`. Os logs do uvicorn e de bibliotecas de terceiros não mudam.
- **A telemetria anônima do Chroma está desligada** (`anonymized_telemetry=False` nas configurações do cliente, em `get_vector_store`). No `chromadb` 1.5.9 o envio já não faz nada, mas a opção fica explícita para versões futuras. Por isso o código importa `chromadb.config.Settings`, mesmo com o `chromadb` sendo dependência transitiva (versão definida pelo `langchain-chroma`) e fora do `requirements.txt`.

**Startup**

- **Documentos que ficaram em `received` ou `processing` viram `failed` com `error_code` `processing_interrupted`** e a mensagem da §3: "Processamento interrompido. Remova e envie novamente." O PRD não define um código para esse caso. Os vetores parciais desses documentos também são apagados. Esse código, como o `pdf_no_text`, só aparece no documento e nunca como resposta HTTP.
- **Verificação do modelo de embeddings (§8.3):** no startup, o backend busca no Chroma no máximo 1 vetor com `embedding_model` diferente do `EMBEDDING_MODEL` configurado (filtro `$ne`, só metadados; também pega vetores sem o campo). Se encontrar, registra o aviso `embedding_model_mismatch`. Se `EMBEDDING_MODEL` não estiver definido, a verificação não roda, e uma falha nela só gera log, sem impedir o startup. A mesma verificação roda a cada `GET /documents`, que traz o campo `embedding_model_changed` (aprovado pelo usuário como mudança no contrato da API e registrado no PRD §5.1). O indicador é calculado na hora, então volta a `false` assim que os documentos antigos são removidos. A API devolve só o booleano; o texto "O modelo de embeddings mudou..." fica em `locales/pt-BR.ts` na Sprint 4.

**Consulta e remoção (`GET`/`DELETE /documents`)**

- **`GET /documents` ordena do mais recente para o mais antigo** (`created_at`, com desempate pelo `rowid`).
- **ID que não é UUID válido retorna `404 document_not_found`**, e não `422`, em `GET` e `DELETE /documents/{id}`.
- **`DELETE` de documento em `received` também retorna `409 document_processing`**, como em `processing`. Pelo diagrama da §5.2, só `ready` e `failed` podem ser removidos, e um documento em `received` está na fila de indexação. Como `ready` e `failed` são estados finais, a verificação não concorre com a indexação.
- **Em falha parcial, o registro não é alterado.** A resposta é `500 delete_partial`, e o log registra o passo que falhou (`vectors`, `file` ou `record`). O registro continua com o `status` e o `error_code` que já tinha, para não perder, por exemplo, um `pdf_no_text`. Um novo `DELETE` repete os três passos.
- **`DELETE` de um documento já removido retorna `404`.** A idempotência vale para os passos depois de um `delete_partial`.

### Sprint 3

**Consulta RAG (`rag_service.answer_question`)**

- **Prompt `ANSWER_PROMPT_V1`** (3 de novembro de 2026, versão inicial): texto idêntico ao da §6.3, em `services/prompts.py`. A mensagem do usuário (`Pergunta: {question}`) fica na constante `QUESTION_PROMPT_V1`, no mesmo arquivo.
- **Erros da consulta usam o `AppError` existente**: `409 document_not_ready` (documento inexistente ou fora de `ready`, verificado antes de qualquer chamada à OpenAI), `502 provider_error` e `504 provider_timeout`. A rota só precisa chamar o serviço; o handler global monta o envelope.
- **Falta de `OPENAI_API_KEY`, `CHAT_MODEL` ou `EMBEDDING_MODEL` na consulta vira `502 provider_error`.**
- **Saída estruturada com `method='json_schema'`** (padrão do `langchain-openai` 1.7.3). O schema `AnswerOutput` não tem descrições, para não mandar ao modelo texto além do prompt da §6.3. Resposta que não pode ser lida como o schema (ou recusada pelo modelo) também vira `502 provider_error`.
- **O chat usa timeout `PROVIDER_TIMEOUT_S` e 1 nova tentativa** (`max_retries=1`), como os embeddings.
- **IDs repetidos em `document_ids` são considerados uma vez só.**
- **O score é o do `langchain-chroma` para cosseno** (`1 − distância`), comparado com `>= RELEVANCE_THRESHOLD`.
- **Limpeza dos trechos:** `<trecho` e `</trecho` são removidos sem diferenciar maiúsculas, repetindo até não sobrar nenhum (a remoção pode formar uma nova ocorrência). O nome do arquivo vai no atributo `arquivo` com escape de HTML (`"`, `<`, `>`, `&`). Sem página, `pagina=""`.
- **Camada 2 também devolve a resposta fixa se `answer` vier vazio com `has_evidence: true`.** Os índices de `cited` são deduplicados e ordenados; `sources[].index` é o número do trecho no prompt, o mesmo do marcador `[n]`.
- **`excerpt` é o texto original do chunk** (sem a limpeza das tags), sem espaços nas pontas e cortado nos primeiros `EXCERPT_MAX_CHARS` caracteres, sem reticências.
- **Log da consulta (`query_done`)**: IDs dos documentos, número de chunks acima do limiar, se o modelo foi chamado, `has_evidence` do modelo e o final, número de citações e duração. Nunca a pergunta, os trechos ou a resposta.

**Rota `POST /api/v1/chat/query`**

- **Rota síncrona (`def`)**: `answer_question` bloqueia nas chamadas à OpenAI, então o FastAPI a executa no threadpool, sem travar o event loop.
- **Erros de validação de `document_ids` viram `422 invalid_request`**: lista vazia, mais de `MAX_DOCUMENTS_PER_QUERY` itens ou item que não é UUID. A §5.3 não tem código para esse caso, e a UI já impede essas seleções. Um UUID válido que não existe retorna `409 document_not_ready`, como manda a §5.1.

**Avaliação e calibração (3.5 e 3.6)**

- **`CHUNK_SIZE=500`, `RETRIEVAL_K=8`, `RELEVANCE_THRESHOLD=0.35`** (3 de novembro de 2026), no lugar de 1000 / 4 / 0,30. Foram calibrados com o conjunto de 15 perguntas de [`docs/eval.md`](docs/eval.md), um parâmetro por vez.
  - Chunks de 500 recuperam o trecho exato com score maior.
  - K=8 é o menor valor com folga para a pergunta multi-página M1 (com K=6 ela passa no limite). Leva ao modelo cerca de 4.000 caracteres, o mesmo volume do default original.
  - 0,35 fica no meio do intervalo entre as perguntas sem relação com os documentos (score máximo 0,25) e o trecho relevante de menor score (0,454).
  - `CHUNK_OVERLAP` ficou em 200: não estava no escopo da calibração.
- **PDFs sintéticos na avaliação.** O PRD §6.4 pede PDFs reais, mas o repositório não tem nenhum. Foram gerados três PDFs fictícios em pt-BR (manual de roteador, política de viagens e o PDF com instrução maliciosa), com o gerador e o avaliador fora do repositório. Os valores devem ser revistos com PDFs reais antes de produção.
- **Documentos indexados antes dessa mudança mantêm os chunks de 1000.** O `CHUNK_SIZE` só vale para novas indexações. Para usar o novo valor, remova o documento e envie de novo.
- **Pendências para o usuário (o prompt e a regra de evidência não foram alterados):**
  - Em 56% das respostas da configuração final, o `answer` não traz `[n]`: são as respostas de uma frase só. As fontes continuam corretas em `sources`.
  - As 2 perguntas parcialmente respondíveis recebem a resposta fixa, porque o modelo devolve `has_evidence: false`.
  - Detalhes e opções em [`docs/eval.md`](docs/eval.md), seção "Achados".
