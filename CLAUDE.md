# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Estado do projeto

Ainda não há código: só o `PRD.md` (v2.1, fonte de verdade) e a pasta `docs/` (resumo do PRD por tema, com índice em `docs/README.md`). A implementação segue as sprints do PRD (§10), começando pela Sprint 1.

Por isso **não existem comandos de build, lint, execução ou teste**. Quando forem criados, devem ser documentados no `README.md` da raiz (tarefa 1.9) e acrescentados aqui. Não invente comandos.

## Como trabalhar neste repositório

- Implemente **uma tarefa do PRD §10 por vez, na ordem**. Marque `[X]` só quando o critério "Verificar"/DoD passar.
- Ao terminar uma tarefa, informe: arquivos alterados, como verificar manualmente e qualquer desvio do PRD.
- Conflito no PRD: §1 → §3 (decisões padrão) → §4–§7 (requisitos) → demais seções.
- Ambiguidade barata de desfazer: escolha a opção mais simples e registre em `README.md`, seção "Decisões". Cara de desfazer (formato persistido, contrato de API, dependência nova): pare e pergunte.
- Use só as dependências do PRD §8.1, com versões fixadas com `==` no `requirements.txt`.
- **Antes da Sprint 6 não crie:** testes automatizados, Dockerfile, CI, autenticação, ORM, Pinia, Vue Router, filas, camada de abstração de provedor. Também não crie arquivos/diretórios vazios "para o futuro".
- Tarefas marcadas `[humano]` (ex.: revogar a chave OpenAI exposta) não podem ser feitas por agente.

## Arquitetura prevista

Aplicação web local de tela única: o usuário envia PDFs, faz perguntas e recebe respostas em pt-BR com citações `[n]` para página e trecho.

- **Backend** (`backend/app/`, FastAPI): `api/` só valida HTTP e delega; a lógica fica em **dois serviços apenas**: `services/document_service.py` (ingestão e remoção) e `services/rag_service.py` (consulta). `db.py` acessa o SQLite com `sqlite3` e SQL escrito à mão. Toda configuração vem de `core/config.py` (Pydantic Settings), sem valores fixos espalhados pelo código.
- **Frontend** (`frontend/src/`, Vue 3 + TS + Vite + Tailwind): um composable por domínio (`useDocuments`, `useChat`), `services/api.ts` com `fetch`, `types/api.ts` espelhando os schemas Pydantic e todos os textos da UI em `locales/pt-BR.ts`.
- **Armazenamento:** SQLite guarda só a tabela `documents` (catálogo); os chunks vivem apenas no Chroma (coleção única `documents`, filtrada por `document_id`); os PDFs ficam em disco como `{document_id}.pdf`; o chat não é persistido. Tudo fica em `data/`, ignorado pelo Git.
- **Ingestão assíncrona:** `POST /api/v1/documents` retorna `202` e indexa via `BackgroundTasks`, um documento por vez (`threading.Lock`). O documento passa por `received → processing → ready/failed`, e a UI acompanha por polling. No startup, documentos em `received` ou `processing` viram `failed`.
- **Regra de evidência em duas camadas** (decidida no código, não só pelo modelo): se nenhum chunk passa de `RELEVANCE_THRESHOLD`, a resposta fixa é devolvida sem chamar o LLM. Depois do LLM (`with_structured_output` → `{claims: [{text, cited}], missing, has_evidence}`), o código monta o `answer` com os `[n]` de cada afirmação, descarta afirmação com citação inválida (avisando) e lista as partes não encontradas. Se `has_evidence` for falso ou não sobrar afirmação válida, volta a resposta fixa. Cada pergunta é independente, sem histórico.
- **Remoção:** sempre na ordem vetores → arquivo → registro, com passos idempotentes. IDs de vetor são `{document_id}:{chunk_index}`. Falha parcial deixa `delete_partial`, e um novo `DELETE` repete os três passos.
- **Prompt:** constante versionada `ANSWER_PROMPT_V2` em `services/prompts.py`. Qualquer mudança cria uma nova versão, registrada no README. Os trechos vão entre tags `<trecho>`, que devem ser removidas do texto do chunk antes de montar o prompt (defesa contra prompt injection).

## Convenções que não são óbvias

- Código, identificadores, nomes de arquivo e comentários em **inglês**. Todo texto visível ao usuário (incluindo `message` de erro da API e `aria-label`) em **pt-BR**.
- **Aspas simples** em Python e TS/JS. Ruff com `line-length = 88` e regras `E,F,I,B`; Prettier com `singleQuote: true`, `semi: false` e `printWidth: 100`; `vue-tsc` sem `any`.
- Erros da API sempre no envelope `{"error": {"code", "message"}}`, com `code` estável da tabela em `docs/api.md`. Nunca expor stack trace, caminho de arquivo, mensagem crua do provedor ou `storage_path`.
- Tipos do LangChain não podem atravessar o contrato HTTP; converta para os schemas Pydantic.
- Logs só com IDs, durações, contagens e `error_code`, nunca com conteúdo de PDF, pergunta, resposta ou chave.
- Páginas do `pypdf` começam em 0: grave e exiba sempre a partir de 1. Datas são gravadas em UTC (ISO 8601 com `Z`) e exibidas em `America/Sao_Paulo`.
- Backend só em `127.0.0.1`. CORS só para `http://localhost:5173`.
- Nenhuma cor hexadecimal fora da configuração do tema Tailwind (tokens em `docs/design-system.md`).

## Referências

- `docs/README.md`: índice da documentação (API, configuração, pipeline RAG, design system, segurança).
- `PRD.md` §3: defaults e variáveis de ambiente. §5: contratos da API. §6.3: texto completo do prompt. §10: tarefas e DoD.
