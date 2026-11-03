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
- **`requirements.txt` só com o que é usado agora** (`fastapi`, `uvicorn`, `pydantic`, `pydantic-settings`). As dependências de RAG e o `python-multipart` entram nas sprints que as usam. O Ruff fica em `requirements-dev.txt`.
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
