# Fluxo de trabalho

Regras para qualquer pessoa ou agente de código que implemente o projeto.

## Ordem de precedência

Em caso de conflito no PRD: §1 (instruções) → §3 (decisões padrão) → requisitos (§4–§7) → demais seções.

## Faça

1. Implemente uma tarefa por vez, na ordem das sprints, e marque `[X]` só quando o critério de verificação passar.
2. Use apenas as dependências da [stack](overview.md#stack). Precisa de outra? Pare e justifique antes de instalar.
3. Leia toda configuração de `app/core/config.py`. Nenhum valor mágico espalhado pelo código.
4. Código, identificadores, nomes de arquivo e comentários em inglês; texto visível ao usuário em pt-BR.
5. Use aspas simples (ver [code-standards.md](code-standards.md)).
6. Ao terminar uma tarefa, informe: arquivos alterados, como verificar manualmente e qualquer desvio do PRD.

## Não faça

- Não crie testes automatizados, Dockerfile, CI, autenticação, ORM, Pinia, Vue Router, filas ou camadas de abstração de provedor antes da Sprint 6 ou de decisão explícita.
- Não crie arquivos ou diretórios vazios "para o futuro".
- Não registre em log conteúdo de PDFs, perguntas, respostas ou chaves.
- Não exponha stack trace, caminho de arquivo ou mensagem crua do provedor na API.
- Não deixe tipos do LangChain atravessarem o contrato HTTP; converta para schemas Pydantic.

## Quando houver ambiguidade

- **Barato de desfazer:** adote a opção mais simples, registre em `README.md` na seção "Decisões" e siga.
- **Caro de desfazer** (formato de dado persistido, contrato de API, dependência nova): pare e pergunte.

## Sprints

As sprints são sequenciais; cada uma só começa quando a anterior cumpre sua Definition of Done (DoD). Tarefas marcadas `[humano]` exigem ação de uma pessoa e não podem ser feitas por agente. A lista completa de tarefas está no PRD, §10.

| Sprint | Foco | DoD |
| --- | --- | --- |
| 1 — Base local | Segredos, config, health, schemas, scaffolding, lint | `git grep -i 'sk-'` não encontra chave; `GET /api/v1/health` retorna `ok`; frontend exibe o health; lint passa nos dois lados |
| 2 — Catálogo e ingestão | SQLite, upload, indexação, listagem, remoção | Com `curl`: PDF real chega a `ready` com `chunk_count` > 0; PDF escaneado chega a `failed / pdf_no_text`; `.txt` renomeado recebe `422 file_not_pdf`; após `DELETE`, sem vetores daquele ID |
| 3 — Consulta RAG | Recuperação, prompt, evidência, `/chat/query`, avaliação | 4 perguntas fora do tema retornam a mensagem fixa; instrução maliciosa ignorada; ≥ 4 de 5 perguntas de página única citam a página certa |
| 4 — Design system e interface | Tokens, componentes, layout, integração | Fluxo completo em 1440 px e 360 px, só com teclado, sem string em inglês na interface |
| 5 — Revisão do MVP | Checklist, acessibilidade, logs, medições | Checklist 100% aprovado ou com desvios documentados; medições registradas |
| 6 — Testes e Docker | Pytest, Vitest, Dockerfile | `pytest` e `npm run test` passam; `docker compose up` sobe com dados persistindo |

## Verificação

Nas Sprints 1–5 não há testes automatizados. Cada requisito tem um critério "Verificar" manual (PRD, §4), registrado no checklist da sprint. Esses critérios viram testes na Sprint 6.
