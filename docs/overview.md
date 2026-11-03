# Visão geral

## Propósito

Reduzir o tempo para localizar informação em manuais e documentos PDF, com respostas rastreáveis e sem conteúdo inventado.

**Público:** uma pessoa ou equipe pequena, em máquina ou rede controlada, consultando dezenas (não milhares) de PDFs com texto digital.

## Objetivos do MVP

1. Enviar, indexar, listar e remover PDFs pela interface.
2. Perguntar sobre um ou mais documentos prontos e receber resposta com fontes.
3. Declarar ausência de evidência em vez de inventar.
4. Interface responsiva, acessível por teclado e visualmente consistente.
5. Nenhum segredo no código ou no Git.

## Princípios

- Simplicidade antes de generalidade.
- Código em inglês, interface em pt-BR.
- Temas claro e escuro consistentes, escolhidos pelo usuário.
- Aspas simples; PEP 8 no Python.
- Testes automatizados e Docker só na Sprint 6.

## Fora do escopo

| Item | Situação |
| --- | --- |
| Autenticação, permissões, multiusuário | Fora do MVP |
| Histórico de chat persistente e memória conversacional | Fora do MVP |
| OCR, formatos além de PDF, CSV | Fora do MVP |
| Streaming de tokens, voz, agentes com ferramentas | Fora do MVP |
| Filas, microserviços, Kubernetes, alta disponibilidade | Fora do MVP |
| Testes automatizados e Docker | Sprint 6 |
| Exposição pública na internet | Não suportada |

## Stack

| Camada | Escolha |
| --- | --- |
| Frontend | Vue 3 (Composition API, `<script setup lang='ts'>`), Vite, Tailwind CSS, `fetch`. Sem Vue Router e sem Pinia (tela única) |
| Backend | Python 3.11 ou 3.12, FastAPI, Uvicorn, Pydantic Settings, `python-multipart`, `pypdf` |
| RAG | `langchain-core`, `langchain-openai`, `langchain-chroma`, `langchain-community`, `langchain-text-splitters` |
| Vetores | Chroma persistente local, coleção única com filtro por `document_id` |
| Catálogo | SQLite via `sqlite3`, sem ORM |

Versões são fixadas com `==` em `requirements.txt`, só com dependências diretas. Nenhuma dependência fora desta lista sem justificativa prévia.
