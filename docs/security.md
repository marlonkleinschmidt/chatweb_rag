# Segurança e privacidade

## Segredos

- Segredos só no `.env`, que está no `.gitignore`.
- `.env.example` contém todas as variáveis com valores fictícios.
- Nenhuma chave no código. Verificação: `git grep -i 'sk-'` não deve encontrar nada.
- A chave OpenAI exposta nos scripts do protótipo deve ser revogada por uma pessoa (`[humano]`). Se ela entrou no histórico do Git, o histórico é considerado comprometido.

## `.gitignore`

Deve conter, no mínimo: `.env`, `data/`, `node_modules/`, `__pycache__/`.

## Logs

Registram apenas IDs, duração, contagens e `error_code`. **Nunca** conteúdo de PDF, pergunta, resposta ou chave.

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

## Prompt injection

O conteúdo dos PDFs é tratado como não confiável: os trechos vão delimitados por `<trecho>`, essas tags são removidas do texto antes de montar o prompt e o prompt instrui o modelo a ignorar instruções dentro deles (ver [rag-pipeline.md](rag-pipeline.md#prompt)).
