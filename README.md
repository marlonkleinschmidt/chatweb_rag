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

### Sem Docker

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

### Com Docker

Pré-requisitos: Docker (com Compose) e o `backend/.env` preenchido — ele é **obrigatório** (`docker compose up` falha sem ele): a chave e os modelos entram por `env_file`, nunca na imagem.

```bash
docker compose build
docker compose up -d     # backend em 127.0.0.1:8000; frontend em http://localhost:5173
docker compose down      # para e remove os containers; os dados persistem
docker compose down -v   # idem e apaga também o volume de dados
```

- **Portas só em `127.0.0.1`** (loopback), como no modo sem Docker. Dentro do container o uvicorn escuta em `0.0.0.0` (exigência do Docker para a porta publicada funcionar); a exposição ao host continua local.
- O frontend roda como **build estático servido pelo nginx**. A URL da API (`VITE_API_BASE_URL=http://localhost:8000/api/v1`) e os limites espelhados (`VITE_MAX_DOCUMENTS_PER_QUERY`, `VITE_MAX_QUESTION_CHARS`) são definidos como build args no `docker-compose.yml` e precisam continuar iguais aos do backend.
- Os dados ficam no **volume nomeado `rag-assistant-data`** (montado em `/app/data`), independente do `backend/data` usado no modo sem Docker: os dois modos têm dados separados, e o Docker nunca lê nem altera os dados locais.
- `restart: unless-stopped` nos dois serviços; o backend tem healthcheck na rota `/api/v1/health`.

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

## Testes

```bash
# backend/ (76 testes unitários: upload, estados, regra de evidência, endpoints, filtro de streaming)
.venv/Scripts/python -m pytest

# backend/ (regressão opcional: as 15 perguntas de docs/eval.md contra a OpenAI real, também
# sem fontes e em streaming; skip automático sem OPENAI_API_KEY/CHAT_MODEL/EMBEDDING_MODEL no .env;
# custo ≈ US$ 0,02 por execução)
.venv/Scripts/python -m pytest -m regression

# frontend/ (50 testes: useDocuments, useChat, useShowSources, streamChat e markdown)
npm run test
```

O `pytest` padrão nunca chama a OpenAI: os testes de regressão ficam desmarcados por padrão (`addopts` no `backend/pytest.ini`) e usam retriever, LLM e embeddings falsos. Os testes isolam os dados em diretórios temporários e não tocam em `backend/data`.

## Operação e limitações

### Backup

- **O que copiar:** o diretório de dados efetivo. Os caminhos são relativos ao diretório onde o uvicorn roda (ver "Decisões", Sprint 1). Com o comando de "Execução", ficam em `backend/data/`:
  - `app.db`: catálogo SQLite (tabela `documents`);
  - `chroma/`: vetores e metadados dos chunks;
  - `documents/`: os PDFs, salvos como `{document_id}.pdf`.

  Se `SQLITE_PATH`, `CHROMA_DIR` ou `DOCUMENTS_DIR` estiverem definidos no `.env`, copie esses caminhos.
- **Os três juntos e com o backend parado.** Catálogo, vetores e arquivos se referem uns aos outros pelo `document_id`. Uma cópia parcial, ou feita durante uma indexação ou remoção, deixa os três inconsistentes (PRD §8.3).
- **Exemplo**, com o backend parado e a partir da raiz do repositório:

  ```bash
  cp -r backend/data backup-data                     # PowerShell: Copy-Item -Recurse backend\data backup-data
  ```

- **Restaurar:** com o backend parado, apague `backend/data/` e copie o backup inteiro no lugar dele, sem misturar com os dados atuais. Ao subir, o backend marca como `failed` (`processing_interrupted`) os documentos que ficaram em `received` ou `processing` quando ele foi parado.
- **Com Docker**, os dados ficam no volume `rag-assistant-data` (não em `backend/data/`), e a mesma regra vale: tudo junto e com o backend parado. Backup e restauração leem/escrevem o volume diretamente:

  ```bash
  docker compose stop backend
  # Backup (no PowerShell, ${PWD} é o diretório atual):
  docker run --rm -v rag-assistant-data:/data -v ${PWD}:/backup alpine tar czf /backup/backup-data.tar.gz -C /data .
  # Restaurar:
  docker run --rm -v rag-assistant-data:/data -v ${PWD}:/backup alpine sh -c 'cd /data && tar xzf /backup/backup-data.tar.gz'
  docker compose up -d
  ```
- **O `.env` não faz parte do backup de dados.** Ele guarda a `OPENAI_API_KEY`; guarde-o à parte, como segredo. Restaure com o mesmo `EMBEDDING_MODEL` usado na indexação; com outro modelo, a UI pede para reenviar os documentos.

### Retenção

- **Documentos ficam até serem removidos manualmente** (PRD §11.3, item 5). Não há expiração automática.
- **A remoção apaga tudo do documento**, na ordem vetores → arquivo → registro. Se um passo falhar, o documento fica com `delete_partial`, e um novo "Remover" repete os três passos.
- **O chat não é persistido.** As mensagens ficam só na memória do navegador e somem ao recarregar a página.
- **OpenAI:** o texto dos chunks (na indexação) e os trechos e a pergunta (na consulta) são enviados à API da OpenAI. O que ela guarda, e por quanto tempo, segue a política de dados da OpenAI para a API, que deve ser consultada antes do uso com documentos reais (PRD §11.3, item 4). Remover um documento aqui não apaga nada do lado da OpenAI.
- **Trocar `EMBEDDING_MODEL` exige reindexar:** os vetores antigos ficam incompatíveis. Remova e envie os documentos de novo (a UI mostra o aviso enquanto houver vetor de outro modelo). Mudanças em `CHUNK_SIZE`, `CHUNK_OVERLAP` ou `SMALL_DOCUMENT_MAX_CHARS` também só valem para documentos enviados depois. Em especial, um PDF de 1 página indexado antes de 4 de novembro de 2026 (tarefa 7.33, ex.: o CRLV) continua dividido em vários trechos até ser removido e enviado de novo.

### Limitações

- **Sem OCR.** PDFs digitalizados, sem texto extraível, terminam em `failed / pdf_no_text`. Só PDF é aceito.
- **Limites por arquivo:** `MAX_UPLOAD_MB` (20 MB) e `MAX_PDF_PAGES` (500 páginas). PDFs criptografados são recusados.
- **Indexação sequencial:** um documento por vez. Os outros esperam em `received`.
- **Volume previsto:** 1 usuário e até cerca de 100 PDFs (PRD §11.3, item 2). Volumes maiores não foram medidos.
- **Sem autenticação e sem multiusuário.** O backend escuta só em `127.0.0.1` e aceita CORS só de `http://localhost:5173`. Não exponha a aplicação na rede ou na internet (PRD §2.2).
- **Uma pergunta por vez, sem histórico:** cada pergunta é respondida sozinha, sem contexto das anteriores, sobre até `MAX_DOCUMENTS_PER_QUERY` (10) documentos.
- **Parâmetros calibrados com PDFs sintéticos:** `CHUNK_SIZE`, `RETRIEVAL_K` e `RELEVANCE_THRESHOLD` vieram da avaliação de [`docs/eval.md`](docs/eval.md) e devem ser revistos com PDFs reais.
- **Citações e respostas parciais:** o modelo devolve a resposta como afirmações curtas, cada uma com os seus trechos, e o backend escreve o `[n]` junto de cada afirmação. Afirmação sem trecho válido é omitida, com o aviso "Parte da resposta foi omitida porque não foi possível vinculá-la às fontes.". Pergunta respondível só em parte recebe a parte coberta e o parágrafo "Não encontrei nos documentos selecionados: …" ("Correções pós-Sprint 5"). A separação em partes e a lista do que faltou vêm do modelo, e só foram avaliadas com PDFs sintéticos.
- **Dados enviados à OpenAI:** o conteúdo dos PDFs e as perguntas saem da máquina (aviso junto ao upload, PRD §7.3).
- **Mantenha `OPENAI_LOG` e `LANGSMITH_TRACING` desligados com dados reais.** `OPENAI_LOG=debug` faz o SDK da OpenAI registrar no log as perguntas e os trechos enviados, e `LANGSMITH_TRACING=true` envia esse conteúdo ao LangSmith. Só ative algum dos dois depois de uma decisão explícita sobre essa exposição.

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
- **Camada 2 também devolve a resposta fixa se `answer` vier vazio com `has_evidence: true`.** Os índices de `cited` são deduplicados e ordenados. *(Alterado na 7.24, 3 de novembro de 2026: antes, `sources[].index` era o número do trecho no prompt, e uma fonte única podia aparecer como `[4]`. Agora os trechos citados são renumerados de 1 a m na ordem da primeira aparição no `answer`; um trecho citado duas vezes mantém o mesmo número. `sources[].index` continua igual ao marcador `[n]`, e `sources` vem nessa ordem. Nenhum campo do contrato mudou; o frontend casa `[n]` com `sources[].index` e não precisou de ajuste.)*
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

### Sprint 4

**Tokens e fonte (4.1)**

- **Fonte Inter 4.1 local**: só o arquivo variável sem itálico (`InterVariable.woff2`, pesos 100–900), baixado do release oficial `rsms/inter` v4.1, com a licença OFL ao lado, em `src/assets/fonts/LICENSE.txt`. O `@font-face` fica em `src/style.css`, com `font-display: swap`. O itálico não foi incluído: se for usado, o navegador o simula.
- **Raios semânticos**: `rounded-panel` (12 px, cards e painéis) e `rounded-control` (8 px, botões e campos). A escala padrão de raios do Tailwind foi desligada; `rounded-full` continua disponível, porque não depende do tema. As duas classes `rounded-*` que o `App.vue` já tinha foram trocadas pelas novas.
- **Só dois breakpoints**: `sm` (≥ 640 px, tablet) e `lg` (≥ 1024 px, desktop). Sem prefixo vale para o celular. Os outros (`md`, `xl`, `2xl`) foram desligados.
- **Tamanhos de texto**: `text-body` (15 px, line-height 1,6) e `text-meta` (13 px, line-height 1,5, que o PRD não define). A escala padrão (`text-sm`, `text-2xl`...) continua disponível para títulos e controles.
- **`w-sidebar`** (320 px) como token de largura (`--spacing-sidebar`).
- *(Substituída na 4.8: paleta `app-*` e botão primário sólido.)* **`gradient-brand` era a utility `bg-gradient-brand`**, da esquerda para a direita, montada com as cores `brand-start` e `brand-end` do `@theme`.

**Contraste do botão primário (4.2)** — *substituída pelas decisões da 4.8 e da 4.9 (abaixo). Mantida como histórico.*

- **Texto `text-primary` e ponta ciano escurecida para `#11767F`** (era `#27B8C7`). Gradiente final: `#6757E8` → `#11767F`. A ponta roxa não mudou. Razões medidas com a fórmula WCAG 2.x:
  - `text-primary` sobre `#6757E8`: 4,76:1. Sobre `#11767F`: 4,99:1.
  - O pior ponto do gradiente (101 amostras, interpolação sRGB e Oklab) fica em 4,76:1, na ponta roxa.
  - As opções reprovadas: `text-primary` sobre `#27B8C7` dava 2,23:1, e texto `canvas` sobre `#6757E8` dava 3,70:1. O valor sugerido antes, `#15808A`, dá 4,36:1 com `text-primary` (só passa com branco puro, 4,68:1), por isso não foi usado.
- **Hover com tokens próprios**: `brand-start-hover` (`#5646D6`) e `brand-end-hover` (`#0F6B74`), na utility `bg-gradient-brand-hover` (uso: `hover:bg-gradient-brand-hover`). O hover escurece o gradiente, então o contraste sobe: mínimo de 5,79:1.
- **O botão primário não usa `primary` sólido como fundo**: `text-primary` sobre `#7C6CF2` dá 3,70:1. `primary` continua sendo a cor do anel de foco: 4,76:1 sobre `canvas` e 4,37:1 sobre `surface` (o mínimo é 3:1).
- **`accent` (`#35C8D0`) não mudou**. Ele é usado como cor de destaque sobre fundos escuros, e não como fundo de texto.
- O PRD §9.1 e o `docs/design-system.md` foram atualizados com essa decisão. A confirmação no navegador fica para a tarefa 5.2.1.

**Componentes base (4.3)**

- **Pastas:** `components/ui/` tem `BaseButton`, `BaseField`, `StatusBadge`, `ConfirmDialog`, `AlertBanner` e `BaseIcon`; `components/domain/` tem `DocumentItem`, `ChatMessage` e `SourceCard`. Todos são apresentacionais, só com props, `v-model` e eventos.
- **`BaseIcon` foi extraído** porque os mesmos SVGs (spinner, alerta, check) se repetiam em 3 ou mais lugares (§9.3). Os ícones são sempre `aria-hidden`; o significado vem do texto ao lado. O spinner para de girar com `prefers-reduced-motion`.
- **`BaseButton`:**
  - `secondary` é o padrão.
  - *(Substituída na 4.8: paleta `app-*` e botão primário sólido.)* `primary` usava o gradiente da 4.2 com `bg-origin-border`. Agora usa `bg-primary` e `hover:bg-primary-hover`.
  - `danger` tem fundo `danger` e texto `canvas` em peso 600 (6,78:1 na paleta antiga; 5,45:1 na atual); no hover, `brightness-110`, o que aumenta o contraste.
  - `secondary` e `ghost` usam `hover:bg-border`, que continua visível dentro do diálogo (`surface-raised`). `text-primary` sobre `border` dá 11,20:1.
  - *(Substituída na 4.9.)* A borda do `secondary` era `text-muted`. Agora é `control-border`: 4,80:1 sobre `surface-raised` (o mínimo para borda é 3:1).
  - Altura mínima de 40 px (`min-h-10`). `loading` desabilita o botão, mostra o spinner e põe `aria-busy`.
- **`BaseField`:** `as='input' | 'textarea'`, com `v-model` (`defineModel`). Os atributos extras (`placeholder`, `maxlength`, `@keydown`...) vão para o controle (`inheritAttrs: false`). Os IDs vêm do `useId`. `aria-describedby` liga a dica e o erro, e o erro também põe `aria-invalid`. O componente expõe `focus()`. O placeholder usa `text-secondary`. A borda do campo é `control-border` desde a 4.9.
- *(Substituída na 4.9 e na 4.10: o token `text-muted` foi removido.)* **`text-muted` reprovava por pouco sobre `surface`:** mede 4,499:1, abaixo de 4,5:1. Por isso os metadados (data, dica, página) usam `text-secondary`. `text-muted` continua passando sobre `canvas` (4,90:1) e serve como cor de borda de controle. O token não foi alterado. A restrição "texto `text-muted` só sobre `canvas`" foi registrada em `docs/design-system.md`. O PRD §9.1 ainda diz "`canvas`/`surface`", e a decisão final fica com o usuário.
- **`ConfirmDialog` usa o `<dialog>` nativo com `showModal()`:**
  - A página fica inerte, e o Tab circula entre os botões do diálogo, sem sair para a interface do navegador.
  - `Esc` emite `cancel` (fica bloqueado durante `loading`), e o pai controla a prop `open`.
  - O foco inicial vai para "Cancelar" (a ação segura). Ao fechar, o foco volta para quem abriu, se esse elemento ainda existir.
  - Se o navegador forçar o fechamento (Esc repetido), o componente emite `cancel` para manter o pai sincronizado.
- **`AlertBanner`:** `role='alert'` só na variante `error`; as outras usam `role='status'`. O texto vai no slot.
- **`DocumentItem`:**
  - **Checkbox:** todo documento tem checkbox, habilitado só para `ready`. O RF-09 (§4) pede "checkbox desabilitado", e a §9.3 diz "só para `ready`"; pela ordem de prioridade, vale a §4.
  - **Limite de seleção:** a prop `selectionDisabled` desabilita os itens não selecionados quando o limite `MAX_DOCUMENTS_PER_QUERY` é atingido.
  - **Remover:** é um botão `ghost` simples, sem menu, com `aria-label` "Remover {arquivo}". Só aparece para `ready` e `failed`, porque a API devolve `409` para `received` e `processing`. A prop `removing` mostra o estado de carregamento.
  - **Data:** `dd/MM/yyyy HH:mm` em `America/Sao_Paulo`, montada com `Intl.DateTimeFormat.formatToParts`, já que o `pt-BR` põe uma vírgula entre data e hora.
  - **Falha:** em `failed`, mostra o `error_message` da API, ou a mensagem genérica se ele vier nulo.
  - O componente renderiza um `<li>`, então o pai deve usar um `<ul>`.
- **`ChatMessage`:**
  - **Citações:** a resposta é dividida em texto e marcadores `[n]`, sem `v-html`. Só vira botão (cor `accent`) o `[n]` que existe em `sources`; os outros ficam como texto.
  - **Fontes:** o componente renderiza os `SourceCard` da própria mensagem. Clicar em `[n]` abre o trecho, rola até o card (sem animação com `prefers-reduced-motion`) e põe o foco nele (`tabindex='-1'`).
  - **Leitor de tela:** cada mensagem tem um prefixo oculto, "Você:" ou "Assistente:".
- **`SourceCard`:** o trecho começa recolhido, com um botão "Mostrar trecho"/"Ocultar trecho" que usa `aria-expanded` e `aria-controls`. "Página n" não aparece quando `page` é `null`. O controle de aberto/fechado é `v-model:expanded`.
- **Textos com valores** (`Enviado em {data}`, `Página {n}`...) são funções no `locales/pt-BR.ts`. Os textos que a 4.4–4.7 vão usar (abas, estados do RF-16, aviso da OpenAI, aviso de troca do modelo de embeddings, validação do upload) já estão lá.
- **`App.vue`** passou a usar `BaseIcon` e `BaseButton` no indicador de saúde, sem mudar o layout.

**Layout (4.4)**

- **O tablet (640–1023 px) usa as abas, como o celular.** Com a sidebar de 320 px, sobrariam 320 px para o chat em 640 px. Com um só breakpoint de layout (`lg`, 1024 px), não há uma terceira versão para manter. O breakpoint `sm` fica disponível para ajustes menores.
- **Estrutura:**
  - `App.vue` monta o header (título + `HealthStatus`), a barra de abas (só abaixo de `lg`) e os dois painéis.
  - Os painéis ficam em `components/domain/DocumentsPanel.vue` e `ChatPanel.vue`, que a 4.5 e a 4.6 vão preencher. Por enquanto, mostram o estado vazio do locale e o formulário da pergunta com o botão "Enviar" desabilitado.
  - O indicador de saúde virou `components/domain/HealthStatus.vue`, discreto no header, com o botão "Tentar novamente" em `ghost`.
- **Altura e rolagem:**
  - A raiz usa `h-dvh` com `overflow-hidden`, e cada nível flex usa `min-h-0`.
  - Rolam só a lista de documentos e a área de mensagens.
  - O formulário da pergunta é o último item do painel de chat, sem `position: fixed`. Por isso fica no rodapé sem cobrir a última mensagem.
- **Abas (padrão WAI-ARIA, ativação automática):**
  - `role` `tablist`/`tab`/`tabpanel`, com `aria-selected`, `aria-controls` e `tabindex` móvel (só a aba ativa entra no Tab).
  - `←`/`→` alternam as abas (com volta ao início); `Home`/`End` vão para a primeira e a última.
  - O painel inativo fica com `display: none`. Ele não é desmontado, então o texto digitado e a rolagem se mantêm ao trocar de aba.
- **Papéis ARIA por largura:** no desktop, os painéis são `<section>` ligadas ao próprio `h2`, sem `role='tabpanel'`, porque as abas não existem ali. Abaixo de `lg`, viram `tabpanel` ligados à aba. O CSS decide o que aparece, e um `matchMedia('(min-width: 64rem)')` no `App.vue` só troca os atributos ARIA. Fica no `App.vue` porque ainda não há composables.
- **Títulos dos painéis:** os `h2` ("Documentos" e "Chat") só aparecem no desktop. No celular e no tablet ficam `sr-only`, porque a aba já dá nome ao painel.
- **Área de mensagens:** `role='log'`, `aria-live='polite'` e `aria-label` "Conversa".

**Documentos na interface (4.5)**

- **Nova variável `VITE_MAX_DOCUMENTS_PER_QUERY`** (padrão 10), em `frontend/.env.example` e `env.d.ts`. Ela espelha o `MAX_DOCUMENTS_PER_QUERY` do backend, e os dois valores precisam ser iguais. Se forem diferentes, a API recusa a seleção maior com `422 invalid_request`.
- **`src/config.ts`** lê as variáveis `VITE_*` numéricas. Os valores de reserva (2000 ms e 10) são os padrões da §3 e só aparecem nesse arquivo.
- **`services/api.ts`:**
  - `listDocuments`, `uploadDocument` e `deleteDocument`. O `getDocument` não foi criado, porque a lista já traz tudo.
  - Uma resposta `204` não tem corpo e não é mais tratada como erro.
  - O upload manda `FormData` com o campo `file`, sem definir `Content-Type` (o navegador põe o `boundary`).
- **`composables/useDocuments.ts`** devolve um objeto `reactive`. O `App.vue` o cria e passa como uma única prop (`store`) ao `DocumentsPanel`; a 4.6 vai ler a seleção do mesmo objeto.
- **Polling com `setTimeout` encadeado, e não `setInterval`.** Cada `load()` cancela o timer anterior e só agenda o próximo enquanto houver documento em `received` ou `processing`. Assim há no máximo um timer, e as chamadas nunca se sobrepõem. O timer é limpo no `onScopeDispose`. Se uma chamada falhar, o polling para, e o botão "Tentar novamente" chama `load()` de novo.
- **A ordem da lista é a da API** (mais recentes primeiro, com desempate pelo `rowid`), sem nova ordenação no cliente.
- **Validação do upload no cliente:**
  - Só a extensão `.pdf` (sem diferenciar maiúsculas) e o arquivo vazio, com os mesmos textos dos códigos `file_not_pdf` e `file_empty`.
  - O tamanho, a assinatura e a criptografia ficam para a API, porque o frontend não conhece `MAX_UPLOAD_MB`.
  - Depois de um upload aceito, aparece "Arquivo enviado. O processamento começou." ou o `warning` de arquivo duplicado.
- **Botão de upload:** "Enviar PDF" é um `BaseButton` que abre um `<input type=file>` oculto. O campo é limpo depois de cada escolha, para que o mesmo arquivo possa ser enviado de novo.
- **Foco depois do upload** (correção pedida pelo QA na DoD da Sprint 4): durante o envio, o botão fica `disabled`, e o foco cai no `<body>`. Quando o envio termina, com sucesso ou erro, o foco volta para "Enviar PDF", a menos que o usuário já o tenha levado para outro lugar. O `BaseButton` continua usando `disabled` durante o `loading`, e isso impede o duplo envio.
- **Mensagens de erro:** as da API (422, 413, 409, 500) aparecem no `AlertBanner` com a `message` do envelope. O erro de rede usa o texto do locale. Os avisos somem na próxima ação de upload ou de remoção.
- **Remoção:**
  - Sempre passa pelo `ConfirmDialog`.
  - Se der certo, o documento sai da lista e da seleção, e o foco vai para "Enviar PDF", porque o botão que abriu o diálogo deixou de existir.
  - Se falhar, a mensagem aparece, a lista é recarregada e o foco volta para o "Remover" do documento.
  - Um `404` conta como sucesso: o documento já tinha sido removido.
- **Seleção:**
  - Fica em `selectedIds`, só com documentos `ready`, até `VITE_MAX_DOCUMENTS_PER_QUERY`.
  - A cada atualização da lista, saem da seleção os documentos que deixaram de existir ou de estar `ready`.
  - O contador "n de 10 selecionados" aparece quando existe algum documento `ready`.
- **Estado vazio:** o texto do locale aparece logo abaixo do botão "Enviar PDF", que é a ação de upload do fluxo da §4.4.

**Chat na interface (4.6)**

- **Nova variável `VITE_MAX_QUESTION_CHARS`** (padrão 2000), em `frontend/.env.example` e `env.d.ts`. Ela espelha o `MAX_QUESTION_CHARS` do backend, e os dois valores precisam ser iguais. O mínimo de 3 caracteres é fixo, como no backend (`MIN_QUESTION_CHARS`), e fica em `src/config.ts`.
- **`services/api.ts`:** `queryChat` (`POST /chat/query`) envia só `{question, document_ids}`.
- **`composables/useChat.ts`:**
  - Guarda as mensagens só em memória; recarregar a página limpa o chat.
  - Cada pergunta é enviada sozinha, sem o histórico.
  - Durante a geração, um novo envio é ignorado.
  - Os erros entram na própria conversa como `AlertBanner` de erro, logo depois da pergunta, que continua visível.
  - O texto do erro é a `message` do envelope (`provider_error`, `provider_timeout`, `document_not_ready`...) ou o texto do locale para erro de rede.
  - É usado só pelo `ChatPanel`, que fica montado mesmo com a aba oculta. Por isso a conversa se mantém ao trocar de aba.
- **Envio:**
  - Pelo botão ou por `Enter`. `Shift+Enter` quebra a linha, e o `Enter` é ignorado durante a composição de texto por IME (`isComposing` ou `keyCode` 229).
  - A pergunta é enviada sem espaços nas pontas, e o campo é limpo no envio. O foco volta ao campo quando chega a resposta.
  - O campo tem `maxlength` igual ao máximo. Uma pergunta fora de 3 a máximo caracteres mostra no `BaseField` o mesmo texto do código `question_invalid`.
  - O botão fica desabilitado sem seleção ou durante a geração, quando mostra o spinner e o texto "Gerando resposta...". A conversa também mostra "Gerando resposta...".
- **Sem seleção:** o rodapé diz "Selecione ao menos um documento pronto...". Abaixo de `lg`, há o botão "Ir para Documentos", que troca de aba e põe o foco na aba "Documentos". Com seleção, o rodapé mostra "Perguntando sobre n documentos."
- **Rolagem automática:** só a área de mensagens rola, sem mexer na página. A cada nova mensagem ou indicador, o início dela fica visível: uma resposta longa aparece do começo, e uma curta fica no fim. A rolagem é suave, exceto com `prefers-reduced-motion`.
- **Resposta sem evidência:** mostra o `answer` da API sem a seção "Fontes", porque `sources` vem vazio.
- **Pendência (prompt, fora do escopo do frontend):** no teste ponta a ponta, as respostas reais vieram sem nenhum marcador `[n]`, embora com `sources` corretas. É o mesmo achado da Sprint 3. Por isso as citações clicáveis foram testadas com uma resposta simulada. As fontes aparecem mesmo sem marcador. *(Resolvida em "Correções pós-Sprint 4": o backend acrescenta os marcadores quando o modelo não os coloca.)*

**Aviso da OpenAI (4.7)**

- **Onde aparece:** o aviso da §7.3 ("Os documentos enviados são processados pela OpenAI para gerar respostas.") fica sempre logo abaixo da dica do botão "Enviar PDF", no estado vazio e com a lista.
- **Leitor de tela:** o botão aponta, por `aria-describedby`, para a dica e para o aviso. O leitor de tela lê o aviso junto com o botão.
- **Visual:** ícone de informação em `accent` e texto em `text-secondary`, que mede 8,33:1 sobre `surface`. Não usa `text-muted`.
- **Sem `AlertBanner`:** é um texto fixo, não uma mudança de estado. Um `role='status'` só faria o leitor de tela anunciar o aviso ao carregar a página.

**Nova paleta `app-*` (4.8)**

- **Pedido do usuário:** a paleta `app-*` (roxos, verde e cinzas) entrou no `@theme` de `src/style.css`, com `white`, `black` e `transparent`. É o único lugar com hex. Os tokens semânticos apontam para ela com `var(--color-app-…)`, e os componentes continuam usando só os nomes semânticos.
- **Mapeamento do tema escuro:**
  - `canvas`: `gray-850`; `surface`: `gray-900` (separa melhor os painéis do fundo que `gray-800`).
  - `surface-raised`: `gray-700`; `border`: `gray-600`.
  - `text-primary`: `white`; `text-secondary`: `gray-200`.
  - `primary`: `purple-500`; `primary-hover`: `purple-600`; `accent`: `purple-400`; `success`: `green-500`.
  - A tabela completa, com os contrastes medidos, está no PRD §9.1.
- **`warning` e `danger` ficaram fora da paleta do usuário**, que não tem amarelo nem vermelho. Os valores anteriores viraram os tokens `app-amber-300` (`#F4B860`) e `app-red-300` (`#F17383`), para manter os hex num lugar só.
- **Botão primário sólido**: `bg-primary` com texto branco (4,71:1) e `hover:bg-primary-hover` (6,42:1). Os tokens `brand-*` e as utilities `bg-gradient-brand` e `bg-gradient-brand-hover` foram removidos.
- **A fonte Inter continua local.** O `@import` do Google Fonts do CSS de referência não foi usado, porque o PRD §9.2 pede o arquivo local e o app não deve fazer requisição externa. O nome da variável continua `--font-sans` (Tailwind 4), e não `--font-family-sans` (Tailwind 3).
- **`@custom-variant dark` ficou para a 4.12**, porque só passa a ter uso com o tema claro (§9.4).

**Contraste da nova paleta, tema escuro (4.9)**

- **Duas combinações reprovavam** e foram corrigidas trocando o token usado no contexto, sem cor nova:
  - **Bordas de controle**: com `text-muted` (`gray-300`), davam 2,42:1 sobre `surface-raised`. Agora usam o novo token `control-border` (`gray-200`): 6,46 sobre `canvas`, 7,94 sobre `surface` e 4,80 sobre `surface-raised`.
  - **Anel de foco**: com `primary`, dava 2,40:1 sobre `surface-raised`. Agora usa o novo token `focus` (`purple-400`): 5,59, 6,88 e 4,15. `primary` continua no fundo do botão e na seleção (3,97:1 como borda sobre `surface`).
- **As demais combinações passam** (tabela no PRD §9.1). `accent` não deve ser usado como texto sobre `surface-raised` (4,15:1).
- **Classes trocadas:** `border-text-muted` virou `border-control-border`, e `outline-primary` virou `outline-focus`. Isso facilita a 4.12, que só precisa dar um valor claro a cada token.

**Transição e limpeza (4.10)**

- **Transição de cor global** de 200 ms (`background-color`, `border-color`, `color`), definida em `@layer base` para `*`, `::before` e `::after`. Fica desligada com `prefers-reduced-motion: reduce`. Por estar na camada base, as utilities dos componentes têm prioridade (por exemplo, `transition-transform` na seta do `SourceCard`), e a regra não afeta animações (spinner), `outline` nem `transform`.
- **O `BaseButton` perdeu o `transition-colors`**, que a regra global já cobre. Assim, o modo sem animação também vale para os botões.
- **`text-muted` removido**: depois da 4.9, nenhum componente usava esse token, e `gray-300` reprova como texto em todos os fundos escuros.

**Tema claro (4.12)**

- **Mecanismo:**
  - A classe `dark` no `<html>` ativa o tema escuro. A variante é `@custom-variant dark (&:where(.dark, .dark *))`, mas nenhum componente usa `dark:`.
  - Seguindo a documentação do Tailwind 4 para variáveis dinâmicas, os tokens semânticos ficam num `@theme inline` que aponta para variáveis `--theme-*`. Elas são definidas em `@layer base`: em `:root` (claro, com `color-scheme: light`) e em `:root.dark` (escuro, com `color-scheme: dark`).
  - Com `inline`, cada utility usa `var(--theme-*)` e resolve o valor do tema ativo.
- **A paleta foi para um `@theme static`.** Os valores dos temas referenciam a paleta só por `var()`, fora das utilities, e o `static` garante que todas as variáveis `--color-app-*` saiam no CSS. Os tokens de layout (fonte, texto, raio, breakpoint, sidebar) ficam num `@theme` comum.
- **Tokens novos `on-primary` e `on-danger`** (texto sobre fundo colorido):
  - O botão primário usava `text-primary`, que no claro é quase preto. O `danger` usava `canvas`, que no claro é quase branco sobre vermelho escuro.
  - `on-primary` é branco nos dois temas. `on-danger` é `gray-850` no escuro (5,45:1) e branco no claro (6,50:1).
  - O `BaseButton` passou a usar `text-on-primary` e `text-on-danger`.
- **Variantes do tema claro fora da paleta:** `app-green-700` `#047A39`, `app-amber-700` `#8A5A00` e `app-red-700` `#B42335`, todas com ≥ 5,1:1 sobre `surface` e `canvas`. `app-green-500` daria 2,00:1 sobre branco.
- **Valores do claro e contrastes medidos:** estão na tabela do PRD §9.4. Ajustes em relação à proposta inicial: `control-border` (`gray-300`, 3,59:1 sobre `surface-raised`) e `focus` (`purple-600`), que a proposta não tinha; `text-muted` foi retirado.
- *(Substituída na 4.13.)* **Padrão provisório:** `class="dark"` fixo no `<html>` do `index.html`, para a aparência não mudar até a 4.13. Agora quem aplica a classe é o script inline.
- **Conferido no Playwright** nos dois temas, em 1440 px e 360 px, com a classe trocada por `document.documentElement.classList`: lista com os quatro estados, diálogo, chat com fontes e `[n]`, e foco. `color-scheme` acompanha o tema, e não há rolagem horizontal.

**Seletor de tema (4.13)**

- **Script inline no `<head>` do `index.html`**, antes do CSS e do app:
  - Lê `localStorage.theme` dentro de `try/catch`. Sem valor válido (`'light'` ou `'dark'`), usa o claro se o sistema preferir claro e, nos outros casos (preferência escura ou nenhuma), o escuro.
  - Aplica a classe `dark` no `<html>`. O `class="dark"` fixo foi removido.
  - O ESLint não analisa HTML, o Prettier formatou o script sem reclamar, e o projeto não tem CSP. Por isso nada precisou de ajuste.
- **`composables/useTheme.ts`:** o estado inicial vem da classe que o script já aplicou, para haver uma única fonte. `toggle()` troca a classe e salva a escolha em `localStorage` (`try/catch`; se o armazenamento falhar, o tema vale só nesta visita). Não há recarga, e o chat se mantém.
- **O app não acompanha mudanças do sistema durante o uso** (opção mais simples, permitida pela §9.4). A preferência do sistema só vale na abertura, enquanto não houver escolha salva.
- **Botão `ThemeToggle`** (`components/domain/`), ao lado do `HealthStatus` no header:
  - É um `BaseButton` `ghost` (altura de 40 px, anel de foco `focus`).
  - Mostra o ícone do tema que será ativado: sol no escuro, lua no claro. Os ícones `sun` e `moon` foram acrescentados ao `BaseIcon`.
  - O `aria-label` e o `title` dizem "Ativar tema claro" ou "Ativar tema escuro", com os textos em `locales/pt-BR.ts`.
- **Sem `<meta name="theme-color">`:** a tag não existia e não foi criada.
- **Conferido no Playwright** em 1440 px e 360 px:
  - Com `localStorage` vazio, o sistema claro abre o tema claro e o escuro abre o escuro.
  - A troca pelo teclado (`Tab` + `Enter`) salva a escolha e mantém o chat, e o `aria-label` passa a indicar o outro tema.
  - Ao recarregar, a escolha salva vale mesmo com o sistema na preferência oposta.
  - **Sem flash:** a classe já está no `<html>` antes de o `#app` existir no DOM.
  - O header cabe em 360 px sem rolagem horizontal.

### Correções pós-Sprint 4

**Fontes de documento removido (frontend)**

- **O `useDocuments` guarda `removedIds`**, os documentos removidos durante a sessão. Um documento entra nessa lista em dois casos:
  - foi removido pelo usuário (inclusive com `404`, quando já tinha sido removido);
  - sumiu da lista depois de um carregamento bem-sucedido.

  Um carregamento que falha (rede, erro da API) não marca nada.
- **Repasse ao card:** o `ChatPanel` passa `isRemoved` ao `ChatMessage`, que passa `removed` ao `SourceCard`.
- **O que aparece:** a fonte continua visível, porque a resposta foi dada com ela, e ganha a etiqueta "Documento removido" (ícone + texto, em `locales/pt-BR.ts`). O `[n]` continua levando até ela.
- **Contraste:** a etiqueta usa `text-secondary` sobre o fundo `canvas` do card: 9,52:1 no claro e 6,46:1 no escuro.

**Sem esmaecimento na abertura**

- **O problema:** a transição de cor global de 200 ms animava também a primeira pintura, e o `body` aparecia semitransparente logo depois do carregamento.
- **A correção:** a transição só vale com a classe `color-transitions` no `<html>`, que o `main.ts` acrescenta depois de dois `requestAnimationFrame`, ou seja, depois da primeira pintura. A troca de tema pelo botão continua animada.
- **`prefers-reduced-motion`:** a regra agora fica dentro de `@media (prefers-reduced-motion: no-preference)`, e não há mais uma regra de `reduce` para anular. Com `reduce`, não há transição nenhuma.

**Marcadores `[n]` acrescentados pelo código (RF-12)** *(Superada em "Correções pós-Sprint 5": `_with_citation_markers` foi removida, e os marcadores agora acompanham cada afirmação.)*

- **O problema:** cerca de 56% das respostas com evidência (sobretudo as de uma frase) vinham sem `[n]` no `answer`, embora `cited` e `sources` estivessem corretos (`docs/eval.md`, "Respostas sem marcador `[n]`"). Sem marcador, a UI não tinha o que tornar clicável.
- **A correção (decisão do usuário):** depois da camada 2 e só com evidência, se o `answer` não tiver nenhum `[n]` de um índice presente em `cited`, o `rag_service` acrescenta os marcadores de `cited` (mesma ordem e deduplicação de `sources`) colados ao fim, antes da pontuação final: "…é de 23 dBm." vira "…é de 23 dBm [1].". Um `[n]` com índice fora de `cited` não conta como marcador, porque a UI não o tornaria clicável.
- **Sem mudança** no `ANSWER_PROMPT_V1` nem no contrato da API. A resposta fixa não muda. O log registra só a contagem de marcadores acrescentados.

### Sprint 5

**Checklist do MVP (5.1 e 5.2)**

- **Resultado em [`docs/checklist-mvp.md`](docs/checklist-mvp.md).** Os 28 itens da §4 (RF-01 a RF-19 e o fluxo da §4.4) passaram: 26 sem ressalvas e 2 com desvio documentado. Não houve reprovação.
- **Desvio D1 (RF-02), resolvido no PRD:** um arquivo acima de `MAX_UPLOAD_MB` recebe `413 file_too_large`, como definem a §5.1 e a §5.3. O RF-02 foi alinhado (decisão do usuário): `413` para tamanho e `422` para os erros de validação do conteúdo.
- **Desvio D2 (RF-12):** quando o modelo omite os `[n]`, o backend os acrescenta juntos no fim da resposta (por exemplo, `[1][2]`), e não um por afirmação. *(Resolvido em "Correções pós-Sprint 5": um marcador por afirmação.)*
- **Acessibilidade (5.2): 19 itens aprovados, nenhum reprovado**, nos dois temas, em 1440, 1024/1023, 800 e 360 px. Os estados difíceis de produzir (badges, erros, resposta longa) foram simulados no Playwright. Quatro razões ficam perto do limite (4,71 no botão primário escuro, 4,80, 3,59 e 4,15): qualquer mudança nesses tokens exige nova medição. O botão "Enviar" desabilitado (2,71 / 3,39) está fora do critério WCAG 1.4.3.
- **Continua pendente (Sprint 3):** perguntas que só podem ser respondidas em parte ainda recebem a resposta fixa de falta de evidência. *(Resolvido em "Correções pós-Sprint 5": a parte coberta é respondida e a parte faltante é indicada.)*

**Logs (5.3)**

- **Logs conferidos sem conteúdo.** Os logs da aplicação registram só IDs, contagens, `duration_ms`, `error_code` e o nome da classe da exceção, nunca a mensagem dela. Num teste com PDF, pergunta e chave marcadoras, nenhum desses textos apareceu no stdout nem no stderr, inclusive com chave inválida.
- **Logs de terceiros ficam no padrão (WARNING).** `httpx`, `openai`, `chromadb` e `langchain_*` não ganham handler nem nível próprio, então URLs do httpx e payloads do openai não são impressos. Só o access log do uvicorn fica em INFO, com método, caminho e status.
- **Não definir `OPENAI_LOG` nem `LANGSMITH_TRACING`.** `OPENAI_LOG=debug` faz o SDK registrar a pergunta e os trechos, e `LANGSMITH_TRACING=true` envia o conteúdo ao LangSmith. A configuração do projeto não lê nenhuma das duas. Decisão do usuário: elas ficam desligadas em qualquer ambiente com dados reais, salvo decisão explícita sobre a exposição desses conteúdos.
- **Nada de conteúdo em query string.** O access log do uvicorn imprime o caminho com a query string, por isso pergunta e texto vão sempre no corpo da requisição.

**Medições (5.4)**

- **Latência:** p50 em 20 execuções, com um PDF sintético de 10 páginas. Indexação: 1,15 s (0,115 s por página). Consulta com evidência: 1,47 s. Consulta sem evidência (não chama o LLM): 0,41 s. Detalhes no PRD §11.2. **Referência preliminar** (decisão do usuário): o PDF é sintético e os tempos incluem a chamada à OpenAI. As metas da §11.2 são provisórias até serem validadas com documentos e condições mais representativas.
- **Custo estimado** com os preços públicos da OpenAI de 3 de novembro de 2026: cerca de US$ 0,00001 por página indexada e US$ 0,00026 por consulta com evidência (US$ 0,26 por 1.000), sem contar o cache. Consultas barradas na camada 1 custam só o embedding da pergunta.
- **Tokens de embedding contados com `tiktoken`**, porque o LangChain não expõe o uso da API de embeddings. Os tokens do chat vêm do `usage_metadata` do `langchain-openai`.
- **Script de medição fora do repositório, com dados temporários**, como o da avaliação da Sprint 3. Ele nunca toca em `backend/data` nem no `.env`, e o código da aplicação não mudou.

### Correções pós-Sprint 5

**Prompt `ANSWER_PROMPT_V2`: citação por afirmação e resposta parcial (RF-12, RF-14)**

- **Prompt `ANSWER_PROMPT_V2`** (3 de novembro de 2026). Texto idêntico ao da PRD §6.3, em `services/prompts.py`. A mensagem do usuário (`QUESTION_PROMPT_V1`) não mudou.
- **Motivo (decisão do usuário):** duas mudanças.
  - **Desvio D2:** o fallback de "Correções pós-Sprint 4" juntava os marcadores de `cited` no fim da resposta e podia sugerir que uma fonte sustentava uma afirmação à qual não estava ligada. Cada citação agora fica junto da sua afirmação. Afirmação sem citação confiável é omitida, com aviso.
  - **Resposta parcial (pendência da Sprint 3):** com o V1, o modelo devolvia `has_evidence: false` nas perguntas parcialmente respondíveis. Agora a parte com evidência é respondida, e as partes que não foram encontradas são indicadas. A resposta fixa fica para quando nenhuma parte puder ser respondida.
- **O `ANSWER_PROMPT_V1` foi removido de `prompts.py`**, porque nenhum código o usa. O texto dele fica no histórico do Git (`prompts.py` e PRD §6.3 até o commit `d578066`). `prompts.py` guarda só a versão em uso.
- **Saída estruturada interna:** `AnswerOutput = {claims: [{text, cited}], missing, has_evidence}`, sem descrições, como antes. `has_evidence` é o último campo, para o modelo escrever as afirmações antes de decidir. Com `has_evidence` primeiro, um rascunho do V2 ainda recusava o P2 (ver [`docs/eval.md`](docs/eval.md)). O schema não sai do `rag_service`, e o `ChatResponse` (`answer`, `has_evidence`, `sources`) não mudou.
- **O código monta o `answer`** (`_assemble_answer`):
  - **Limpeza:** remove de `text` e de `missing` qualquer `<trecho`/`</trecho` e qualquer marcador do modelo (`[3]`, `[1, 2]`, `[1-3]`) e normaliza os espaços. Só o código escreve marcadores.
  - **Afirmação válida:** tem texto, `cited` não vazio e todos os índices entre 1 e n. Uma afirmação com algum índice inexistente é descartada inteira, não só o índice, porque a citação dela não é confiável. Afirmação com texto vazio é ignorada, sem contar como descartada.
  - **Marcadores:** cada afirmação válida recebe os seus marcadores, deduplicados e em ordem crescente, antes da pontuação final: "…é de 23 dBm." vira "…é de 23 dBm [3].". Vírgula, ponto e vírgula ou dois-pontos no fim são trocados por ponto; sem pontuação final, entra um ponto. As afirmações são unidas por espaço, num parágrafo.
  - **Partes não encontradas:** se `missing` tiver itens e houver afirmação válida, entra um novo parágrafo (`\n\n`) com "Não encontrei nos documentos selecionados: " + os itens separados por "; " + ".". O texto do item fica como o modelo escreveu (sem mudar maiúsculas, para não estragar nomes próprios e siglas).
  - **Afirmação omitida:** se alguma afirmação foi descartada, entra o parágrafo "Parte da resposta foi omitida porque não foi possível vinculá-la às fontes.".
- **Camada 2:** resposta fixa do RF-14 se `has_evidence` for falso ou se nenhuma afirmação for válida, mesmo que `missing` tenha itens. `sources` é a união dos índices das afirmações válidas.
- **Textos fixos** em constantes no topo do `rag_service.py`: `NO_EVIDENCE_ANSWER`, `MISSING_PARTS_PREFIX`, `MISSING_PARTS_SEPARATOR`, `UNLINKED_CLAIMS_NOTICE` e `PARAGRAPH_SEPARATOR`.
- **Log `query_done`:** ganhou `valid_claims`, `dropped_claims` e `missing_parts` (só contagens). O log `citation_markers_added` deixou de existir.
- **Frontend sem mudança:** o `ChatMessage.vue` já transforma em botão qualquer `[n]` de `sources`, em qualquer posição do texto, e o `whitespace-pre-wrap` mostra os parágrafos.
- **Avaliação:** 15/15 em três execuções seguidas, com a mesma configuração (`CHUNK_SIZE=500`, `RETRIEVAL_K=8`, `RELEVANCE_THRESHOLD=0.35`). As 2 parciais passaram a responder a parte coberta e a indicar a faltante, e todo `[n]` foi conferido contra o trecho da sua afirmação. Detalhes em [`docs/eval.md`](docs/eval.md), "Rodada com `ANSWER_PROMPT_V2`".

### Sprint 6

**Testes (6.1–6.3)**

- **Dependências de teste fora da §8.1, só em `requirements-dev.txt`:** `pytest==9.2.0`, `httpx==0.28.1` (exigência do `TestClient`; já era transitiva, virou pin direta) e `reportlab==5.1.0`, que gera os 3 PDFs sintéticos da avaliação dentro do próprio teste (os originais ficavam fora do repositório; sem ela, a 6.3 não teria corpus). Nenhuma entra no `requirements.txt` nem na imagem Docker.
- **Isolamento sem `importlib.reload`:** o `conftest.py` define env vars antes de importar qualquer módulo de `app` (o `settings` é singleton criado no import) e cada teste reponta os caminhos de dados para `tmp_path`; chave e modelos são mascarados com valores falsos, para que nenhum teste unitário chegue à OpenAI. A indexação em background é neutralizada no fixture (um teste confirma o agendamento real). `backend/data` permanece intocado.
- **Inserção de vetores nos testes:** o `add_texts` do `langchain-chroma` ignora embeddings explícitos e, sem embedding function, o chromadb baixaria o modelo default ONNX (79 MB). O helper de teste usa uma classe `Embeddings` falsa e faz upsert com vetores prontos — 100% offline.
- **A regressão da 6.3 é opt-in:** marker `regression` com `addopts = -m "not regression"` no `backend/pytest.ini`. O `pytest` padrão roda só os 45 unitários (custo zero); `pytest -m regression` roda as 15 perguntas com a chave real lida diretamente do `.env` (skip automático se faltar chave ou modelos, que nunca são impressos) e a configuração calibrada forçada no fixture (500/200/8/0,35, temperatura 0), espelhando o avaliador original. Placar 15/15, igual à referência do `ANSWER_PROMPT_V2`.
- **Frontend (6.2):** Vitest 5.1.0 (versão exata). Testes em `src/composables/__tests__/` exercitam o `services/api.ts` real com `fetch` simulado (`vi.stubGlobal`), cobrindo polling encadeado com fake timers, seleção/limite, `removedIds`, payload sem histórico (RF-15) e erros. O `.env.test` versionado fornece `VITE_API_BASE_URL` no modo test.
- **`npm audit`** reporta vulnerabilidades moderate pré-existentes na cadeia de dev do ESLint; nenhuma introduzida pelo Vitest, e o `npm audit fix` traria breaking changes — mantido como está.
- **Achado cosmético (não corrigido, decisão pendente):** o regex de limpeza de `<trecho>` no `rag_service` (`r'</?trecho'`) remove a abertura da tag mas deixa o `>` e atributos residuais no texto exibido. A defesa contra prompt injection (o texto nunca abre/fecha um bloco de contexto) continua válida; o comportamento atual está documentado em `test_evidence_rule.py`.

**Docker (6.4 e 6.5)**

- **Volume nomeado `rag-assistant-data`** montado em `/app/data`, e não bind mount: o `backend/data` local pode ter dados reais que o Docker não deve montar nem alterar; os dois modos de execução ficam com dados independentes. Nome explícito para backup/restauração não dependerem do nome do projeto.
- **Dentro do container o uvicorn escuta em `0.0.0.0`** (exigência do Docker para a porta publicada funcionar); a exposição ao host continua só loopback (`127.0.0.1:8000:8000` e `127.0.0.1:5173:80`), como manda o PRD.
- **Sem proxy nginx para a API:** o `api.ts` exige `VITE_API_BASE_URL` não vazio (senão `config_missing`), então o bundle aponta para `http://localhost:8000/api/v1` via build arg; o browser usa `http://localhost:5173`, origem aceita pelo `CORS_ORIGINS` padrão. `VITE_MAX_DOCUMENTS_PER_QUERY` e `VITE_MAX_QUESTION_CHARS` são build args no compose e precisam continuar iguais aos do backend.
- **`backend/.env` obrigatório para `docker compose up`** (falha rápida intencional via `env_file`); nenhum segredo entra na imagem. O `CMD` do Dockerfile usa aspas duplas (exec form JSON) — única exceção à regra de aspas simples, justificada no próprio arquivo.

### Sprint 7

**Prompt sem fontes (7.3)**

- **`ANSWER_NO_SOURCES_PROMPT_V1`** (3 de novembro de 2026, PRD v2.2 §12.7): novo prompt para o modo sem fontes. Motivo: no streaming o modelo escreve prosa contínua em vez de claims estruturados — o prompt herdou do `ANSWER_PROMPT_V2` as regras de grounding (1), contradições (5), idioma (6), fidelidade a números e termos (7) e defesa contra prompt injection (8, tags `<trecho>`), e trocou a saída estruturada por texto corrido com markdown simples (títulos curtos, negrito, itálico, listas, código em linha e em bloco; sem tabelas, links, imagens ou HTML), frases curtas, sem marcadores `[n]`, e parágrafo final "Não encontrei nos documentos selecionados: …" para as partes sem resposta. O `ANSWER_PROMPT_V2` permanece inalterado no caminho com fontes. `prompts.py` agora guarda as duas versões em uso.

**Streaming e contrato (7.1–7.7, §12.8)**

- **Dois endpoints em vez de um com flag de formato** (§12.8, decisões 1–3): `/chat/query` (JSON) mantém `show_sources` com default `true` — omissão equivale ao comportamento anterior, clientes existentes não mudam — e `/chat/query/stream` (SSE) usa o schema derivado `ChatStreamRequest` com default `false`, porque a rota sempre responde sem fontes. `show_sources=true` explícito no stream vira `422 stream_sources_unsupported`: pedir citações a uma rota que não as gera é contrato impossível e falha explícito, não silencioso. Alternativa rejeitada: um único endpoint que muda de `Content-Type` conforme a flag — ambigüaria o contrato do OpenAPI.
- **Erros em dois planos** (§12.8, decisão 8): tudo o que dá para detectar antes do primeiro evento (validação, `409 document_not_ready`, `502`/`504` da recuperação) volta como envelope JSON com o status correto, porque o stream ainda não começou; falha do provedor **durante** a geração vira evento `error` seguido do fim da conexão (o `200` já foi enviado) e o texto parcial permanece no cliente.
- **Cancelamento real no backend** (§12.8, decisão 9): `AbortController` no frontend fecha a conexão e o Starlette cancela o gerador, encerrando a iteração do `.stream` do modelo — não basta o cliente parar de ler. Sem o botão "Parar", o usuário ficaria preso a um stream longo, pior que no modo atual.
- **`first_token_ms` no log `query_done`** (§12.4): junto de `show_sources` e `stream`, sempre sem conteúdo — só a duração até o primeiro delta, o que permite medir o TTFT com o conjunto de avaliação (7.15).

**Markdown no modo sem fontes (7.11, §12.8 decisão 10)**

- **`markdown-it==15.0.3` é a única dependência nova da sprint** (frontend, pinada no `package.json`; `@types/markdown-it==14.2.0` só em devDependencies). No streaming o modelo escreve prosa contínua, onde listas, negrito e código ajudam a leitura; o modo com fontes mantém texto puro porque é o "comportamento atual" exigido pela funcionalidade e claims atômicos (uma frase, um fato) não ganham com formatação.
- **`MarkdownText.vue` é o único `v-html` do app:** `html: false` escapa todo HTML escrito pelo modelo (defesa em profundidade contra prompt injection vinda dos PDFs), `linkify: false` e as regras de link e imagem desativadas eliminam a superfície de URL — a saída contém só tags inertes. O texto do modelo é tratado como não confiável (§7.3). Alternativas rejeitadas: DOMPurify (redundante nesse subconjunto fechado) e parser próprio (propenso a erro).
- **Re-render incremental:** o texto acumulado é re-processado pelo markdown-it a cada delta; sintaxe parcial (ex.: `**` sem fechar) aparece como texto até ser fechada — transitório e aceitável. O caminho com fontes continua usando o renderizador de texto puro de sempre, sem markdown.

**Medições do TTFT (7.15)**

- **Meta da §12.4 confirmada com o conjunto de avaliação** (3 de novembro de 2026): `pytest -m regression` executado duas vezes por completo (cada uma: 15 perguntas com fontes + 15 sem fontes JSON + 2 rodadas de streaming, 30 amostras de `first_token_ms`; ~US$ 0,02 por execução). Resultado: **p50 968–985 ms e p90 1.218–1.281 ms** (n=30 por execução), bem dentro da meta p50 ≤ 2 s e p90 ≤ 4 s — que passa de provisória a definitiva (§11.2 e §12.4). Só com chamada ao modelo (26 amostras): p50 985–1.000 ms, p90 1.250–1.281 ms; camada 1 sem chamada ao LLM (4 amostras): p50 ≈ 390 ms.
- **Qualidade entre os modos:** `has_evidence` coincidiu em **15/15** perguntas entre o JSON com fontes e o JSON sem fontes nas duas execuções — mesmo pipeline estruturado, mesma decisão de evidência (§12.7, caminho 1). Duração média por modo: com fontes 1,37–1,60 s, sem fontes (JSON) 1,37–1,43 s, streaming total 1,26–1,36 s — o modo oculto não piorou o tempo total.
- **Custo por consulta não mudou de patamar:** o serviço não expõe tokens por chamada, então a comparação de custo usa a duração por modo como proxy (mesma recuperação e mesmo modelo nos dois modos; o prompt em prosa do streaming é de tamanho parecido ao estruturado). O detalhamento de tokens continua o da §11.2 (tarefa 5.4).

**Premissas da §12.8 que a implementação assume**

- Transporte só SSE: `StreamingResponse` (Starlette) no backend e `fetch` + `ReadableStream` no frontend; sem dependência nova de transporte (§8.1), sem WebSocket e sem `EventSource` (não suporta POST).
- No modo streaming a **camada 2 da regra de evidência não existe** (§12.11): não há citações a validar, o grounding fica com o prompt e a camada 1 (limiar decidido em código). O caminho JSON com `show_sources=false` mantém as duas camadas intactas.
- O modelo é instruído a não escrever `[n]`, mas o código não confia: `_MarkerStreamFilter` remove marcadores a cada delta com buffer entre chunks e `flush()` final, com limpeza de espaços **local** aos pontos de remoção (para não colapsar listas e quebras de linha do markdown).
- Preferência da UI só no `localStorage` (chave `show_sources`, try/catch no padrão do tema RF-19): não há perfil de usuário no MVP (§2.2), backend/perfil seria custo sem benefício.
- Markdown só no modo sem fontes; links, imagens, tabelas e HTML cru ficam fora de escopo (§12.10), pelo subconjunto fechado do renderizador.

### Ajustes pós-Sprint 7

- **Cota mínima de trechos por documento (7.29, 4 de novembro de 2026):** com 2 ou mais documentos selecionados, cada documento tem uma busca própria (filtro `{"document_id": id}`), além da busca global, e reserva até `MIN_CHUNKS_PER_DOCUMENT` trechos (padrão 1) dentro de `RETRIEVAL_K`, com o mesmo `RELEVANCE_THRESHOLD`. As vagas que sobram vêm do ranking global, sem duplicatas, e o contexto continua ordenado por score. Motivo: numa pergunta mista sobre o CRLV e o manual SM-G97X, os 8 trechos vieram do manual (muito maior), e as partes sobre o CRLV saíram como "não encontrei". Com 1 documento, só a busca global roda, idêntica à de antes; `MIN_CHUNKS_PER_DOCUMENT=0` desliga a cota. A camada 1 não muda: trecho abaixo do limiar nunca entra pela cota. Se as reservas passarem de `RETRIEVAL_K` (ex.: 10 documentos com K=8), entra primeiro o melhor trecho de cada documento, por score. As buscas rodam em paralelo (`ThreadPoolExecutor`), porque cada uma gera o embedding da pergunta de novo; em série, a primeira medição deu TTFT p50 de 1.952 ms. Medição: `pytest -m regression` (3 documentos selecionados em todas as perguntas) passou 32/32 com a cota e sem ela; TTFT p50/p90 de 1.062/1.452 ms com a cota, contra 952/1.172 ms sem ela, e duração média com fontes de 1,53 s contra 1,32 s. O conjunto de `docs/eval.md` não tem o caso que motivou a mudança (os fatos ficam em documentos de tamanho parecido), então ele mede só a não regressão; o caso CRLV + manual é coberto em `tests/test_retrieval_quota.py` com vector store falso. **Medição com os PDFs reais (7.32, 4 de novembro de 2026):** a cota leva o CRLV ao contexto, mas **não** resolve o caso real. Numa pergunta mista que não cita o CRLV pelo nome ("Como capturar a tela no celular e qual é a placa do veículo?"), a placa saiu como "não encontrei" em 8 de 8 execuções, com cota 0 e com cota 1. O trecho reservado pela cota é o dos rótulos do formulário; o valor da placa está em outro chunk, porque a extração do `PyPDFLoader` separa os rótulos dos valores. Quando a pergunta cita o CRLV, ele já entra no top-8 sem a cota. Testar `MIN_CHUNKS_PER_DOCUMENT` de 2 a 5 tirou o "não encontrei", mas o modelo passou a dar o número do chassi como placa, então o padrão continua 1. Próximo passo, que depende do usuário: mudar a extração ou o chunking de documentos pequenos ou de formulário. Detalhes e números em `docs/eval.md` (7.32). A pergunta está em `pytest -m regression` como `xfail` não estrito. Alternativa rejeitada: aumentar `RETRIEVAL_K`, que não garante nada a um documento pequeno ao lado de um grande e aumenta o contexto de todas as consultas.
- **Documento pequeno em um único trecho (7.33, 4 de novembro de 2026):** um PDF de 1 página cujo texto extraído tenha até `SMALL_DOCUMENT_MAX_CHARS` caracteres (padrão 4.000; `0` desliga) é indexado como um só chunk (`chunk_index` 0, `page` 1), sem o `RecursiveCharacterTextSplitter`. Motivo: no CRLV, a extração do formulário põe o rótulo "PLACA" (caractere 352) longe do valor (caractere 1.167), e com `CHUNK_SIZE=500` os dois ficavam em chunks diferentes. Em perguntas mistas que não citam o CRLV, a cota da 7.29 trazia o chunk dos rótulos, e a placa saía como "não encontrei" (0/8). Com o CRLV inteiro (1.584 caracteres) num trecho, CM1, CM2 e CM3 acertaram a placa em 8/8 cada, sem nenhuma resposta com campo errado, e a parte do manual continuou certa (8/8). O score do trecho único cai no máximo 0,015 em relação ao melhor chunk de 500 (0,460 no CM2, com folga de 0,11 sobre o limiar). `pytest -m regression` passou 35/35, sem regressão nas 15 perguntas; o `xfail` do CM2 foi removido e o CM3 entrou na regressão. A regra vale só para documentos de **1 página**, para que o trecho único cite a página certa: juntar várias páginas num chunk exigiria escolher uma página para citar (ex.: a primeira), e a citação poderia apontar a página errada. O limite de 4.000 é cerca de 2,5 vezes o CRLV e o mesmo volume do contexto inteiro (8 × 500). Prompt (`ANSWER_PROMPT_V2`), formato persistido do SQLite e contrato da API não mudaram. **Documentos já indexados não mudam sozinhos:** para aplicar a regra a um PDF de 1 página enviado antes, remova-o e envie-o de novo. Limitações: o `excerpt` da fonte mostra os primeiros 500 caracteres do trecho (no CRLV, os rótulos, não o valor da placa), e um formulário de 2 páginas continua no splitter. Alternativa não implementada: parear rótulo e valor na extração, que depende do layout de cada formulário. Detalhes em `docs/eval.md` (7.33).

- **Toggle "Exibir fontes" (7.18):** o `<input type="checkbox">` nativo continua (`peer sr-only`, dentro do `<label>`), com `role="switch"` para que leitores de tela anunciem "ativado/desativado". A faixa e a bolinha são `<span aria-hidden>` estilizados com `peer-checked:`/`peer-focus-visible:`, só com tokens semânticos. Contraste ≥ 3:1 contra `surface` nos dois temas (desligado `control-border` 4,67/7,94; ligado `primary` 6,42/3,97; bolinha `on-primary` 6,42/4,71, claro/escuro). O deslizamento usa `motion-safe:`, então fica sem animação com `prefers-reduced-motion`.
- **Cards de documentos (7.19):** o card passou de `bg-surface` para `bg-canvas`, o mesmo padrão do `SourceCard`. No escuro ele fica um pouco mais claro que o painel (razão 1,23). No claro, `surface` era branco e o card ficava levemente mais escuro (razão 1,06). Por isso foi criado o token semântico `sidebar` (7.21), usado só no painel de documentos: no claro ele é `app-gray-100` e o card fica mais claro (razão 1,23); no escuro ele é `app-gray-900`, o mesmo valor de antes. Texto e controles sobre o painel passam em AA, mas cores de estado não devem ir como texto direto sobre `sidebar` (o verde fica em 4,19). O `AlertBanner` mantém o fundo `surface`. Não usei `surface-raised` porque, no escuro, o hover do "Remover" (`bg-border`) ficaria invisível sobre ele.
- **Ícone de envio (7.20):** novo ícone `send` no `BaseIcon` (SVG inline, `aria-hidden`), antes do rótulo "Enviar". Durante a geração, o `BaseButton` mostra só o spinner.
- **Bolha vazia após erro no streaming (7.27):** quando o stream falha ou é parado antes do primeiro delta, o `useChat` remove a entrada do assistente ainda vazia (`content === ''`); com texto parcial ela fica, e o erro (se houver) vem logo depois.
- **"Remover" só com ícone (7.28):** nova prop `iconOnly` no `BaseButton` (quadrado de 40 px, sem padding horizontal; em `loading` o spinner substitui o ícone) e novo ícone `trash` no `BaseIcon`. O botão fica `ghost`, com `aria-label` e `title` "Remover {nome}". Ocupa 40 px em vez de 92 px, e o espaço vai para o nome do arquivo. Mantive 40 px (e não 24 px) para seguir a altura mínima do `BaseButton`. A chave `documents.remove` saiu do locale por ficar sem uso.
- **Cards de documentos (7.30):** a pedido do usuário, o card fica levemente mais claro que o painel no escuro e levemente mais escuro no claro. O painel voltou para `bg-surface` e o token `sidebar` (7.21) foi removido; o card continua `bg-canvas` (1,23:1 no escuro, 1,06:1 no claro). Contrastes sobre o painel: os de `surface` (PRD §9.4).
