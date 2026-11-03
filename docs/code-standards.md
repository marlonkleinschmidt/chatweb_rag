# Padrões de código

## Idioma

| O quê | Idioma |
| --- | --- |
| Arquivos, módulos, classes, variáveis, funções, schemas, rotas, comentários técnicos | Inglês |
| Todo texto visível: rótulos, validações, mensagens (inclusive vindas da API), datas, `aria-label` | pt-BR |

No frontend, todos os textos da UI ficam em `src/locales/pt-BR.ts`, um objeto simples de strings, sem biblioteca de i18n.

## Aspas

Aspas simples em Python e TS/JS, exceto quando evitarem escape ou o formato exigir (JSON, HTML).

## Ferramentas

| Área | Ferramenta | Configuração mínima |
| --- | --- | --- |
| Python | Ruff (lint + format) | `line-length = 88`, `quote-style = 'single'`, regras `E`, `F`, `I`, `B` |
| TS/Vue | ESLint (`eslint-plugin-vue`) + Prettier | `singleQuote: true`, `semi: false`, `printWidth: 100` |
| Tipos | `vue-tsc` e type hints Python | Sem `any` e sem funções Python públicas sem tipo |

Python segue PEP 8.

## Configuração

Toda configuração é lida de `app/core/config.py` (Pydantic Settings). Nenhum valor mágico no código. Ver [configuration.md](configuration.md).

## Simplicidade

**Backend**

- Rotas validam HTTP e delegam a serviços; serviços não conhecem `Request`/`Response`.
- No máximo dois serviços (`document_service`, `rag_service`) e um módulo de acesso ao SQLite (`db.py`, com `sqlite3`).
- Sem interface genérica de provedor: chamadas OpenAI via `langchain-openai` direto no `rag_service`.
- Sem ORM; SQL escrito à mão em `db.py`.
- Tipos do LangChain não saem dos serviços; a API usa só schemas Pydantic.

**Frontend**

- Vue 3 com Composition API e `<script setup lang='ts'>`.
- Um composable por domínio (`useDocuments`, `useChat`) e um `services/api.ts` com `fetch`.
- Sem Vue Router e sem Pinia.
- Classes Tailwind ficam nos templates; extrair para componente só quando o mesmo padrão se repete em três ou mais lugares.
- Nenhuma cor hexadecimal fora da configuração do tema (ver [design-system.md](design-system.md)).

## Datas e páginas

- Armazenamento de datas: UTC, ISO 8601 com `Z`.
- Exibição de datas: fuso `America/Sao_Paulo`, formato `dd/MM/yyyy HH:mm`.
- Página de PDF: o `pypdf` usa base 0; gravar e exibir sempre em base 1.
