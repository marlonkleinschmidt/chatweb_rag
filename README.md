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
- **Pendência (prompt, fora do escopo do frontend):** no teste ponta a ponta, as respostas reais vieram sem nenhum marcador `[n]`, embora com `sources` corretas. É o mesmo achado da Sprint 3. Por isso as citações clicáveis foram testadas com uma resposta simulada. As fontes aparecem mesmo sem marcador.

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

**Marcadores `[n]` acrescentados pelo código (RF-12)**

- **O problema:** cerca de 56% das respostas com evidência (sobretudo as de uma frase) vinham sem `[n]` no `answer`, embora `cited` e `sources` estivessem corretos (`docs/eval.md`, "Respostas sem marcador `[n]`"). Sem marcador, a UI não tinha o que tornar clicável.
- **A correção (decisão do usuário):** depois da camada 2 e só com evidência, se o `answer` não tiver nenhum `[n]` de um índice presente em `cited`, o `rag_service` acrescenta os marcadores de `cited` (mesma ordem e deduplicação de `sources`) colados ao fim, antes da pontuação final: "…é de 23 dBm." vira "…é de 23 dBm [1].". Um `[n]` com índice fora de `cited` não conta como marcador, porque a UI não o tornaria clicável.
- **Sem mudança** no `ANSWER_PROMPT_V1` nem no contrato da API. A resposta fixa não muda. O log registra só a contagem de marcadores acrescentados.
