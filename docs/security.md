# Segurança e privacidade

## Segredos

- Segredos só no `.env`, que está no `.gitignore`.
- `.env.example` contém todas as variáveis com valores fictícios.
- Nenhuma chave no código. Verificação: `git grep -i 'sk-'` não deve encontrar nada.
- A chave OpenAI exposta nos scripts do protótipo deve ser revogada por uma pessoa (`[humano]`). Se ela entrou no histórico do Git, o histórico é considerado comprometido.

## `.gitignore`

Deve conter, no mínimo: `.env`, `data/`, `node_modules/`, `__pycache__/`.

## Logs

Registram apenas IDs, duração, contagens e `error_code`. **Nunca** conteúdo de PDF, pergunta, resposta ou chave. Com histórico, `query_done` traz só `history_turns`, `rewritten` e `rewrite_ms`, e `query_rewrite_failed` só `reason`, `error_code`, tipo da exceção e tamanho da saída: nunca o texto do histórico nem da pergunta reescrita.

## API

- Sem stack trace, caminho de arquivo ou mensagem crua do provedor nas respostas (ver [api.md](api.md#envelope-de-erro)).
- `storage_path` nunca é retornado.
- O nome original do arquivo nunca compõe caminho de disco; o arquivo é salvo pelo UUID.

## Rede

- Backend escuta em `127.0.0.1`, nunca `0.0.0.0` no MVP.
- CORS aceita apenas a origem do frontend (`http://localhost:5173`).
- Exposição pública na internet não é suportada.

## Dados enviados à OpenAI

A interface exibe, junto ao upload:

> Os documentos enviados são processados pela OpenAI para gerar respostas.

O histórico da conversa enviado com cada pergunta também vai à OpenAI, coberto pelo mesmo aviso. Nada do histórico é gravado no backend (SQLite, Chroma ou disco).

## Conversa no navegador

- A conversa exibida (perguntas, respostas e fontes) fica no `localStorage`, chave `chat_history`, formato versionado `{version: 1, entries: [...]}`, com até 50 entradas (as mais antigas saem primeiro).
- Fica na máquina até o usuário clicar em "Nova conversa", que limpa as mensagens e remove a chave.
- Versão desconhecida ou JSON corrompido são descartados em silêncio; storage bloqueado não quebra o app (a conversa fica só em memória).

## Prompt injection

O conteúdo dos PDFs é tratado como não confiável: os trechos vão delimitados por `<trecho>`, essas tags são removidas do texto antes de montar o prompt e o prompt instrui o modelo a ignorar instruções dentro deles (ver [rag-pipeline.md](rag-pipeline.md#prompt)).

O histórico também é não confiável: o usuário controla o payload e respostas anteriores podem conter texto vindo dos PDFs. Defesas (ver [rag-pipeline.md](rag-pipeline.md#histórico-da-conversa)):

- Limites validados antes de qualquer chamada ao modelo: acima de `2 × MAX_HISTORY_TURNS` mensagens ou `MAX_HISTORY_CHARS` caracteres, `role` inválido ou `content` vazio → `422 history_invalid`.
- O histórico vai entre tags `<historico>`; `<historico`/`</historico` e `<trecho`/`</trecho` são removidos de cada mensagem, e, com histórico, `<historico` também do texto dos trechos.
- Os marcadores `[n]` de respostas anteriores são removidos, para o modelo não reaproveitar numeração antiga.
- Os prompts de reescrita e de resposta tratam o histórico como dado, não instrução, e proíbem afirmar o que só aparece nele.
- O histórico nunca é evidência: a camada 1 e a validação de citações continuam decididas pelo código sobre os trechos da consulta atual.
