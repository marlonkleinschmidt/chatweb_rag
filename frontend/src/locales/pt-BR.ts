// All user-visible UI strings (pt-BR). Plain object, no i18n library.
export const ptBR = {
  app: {
    title: 'Assistente RAG para documentos',
  },
  health: {
    checking: 'Servidor: verificando conexão...',
    connected: 'Servidor: conectado',
    unavailable: 'Servidor: indisponível',
    retry: 'Tentar novamente',
  },
  errors: {
    configMissing: 'A URL do servidor não está configurada (VITE_API_BASE_URL).',
    network: 'Não foi possível conectar ao servidor. Verifique se o backend está em execução.',
    unexpected: 'Ocorreu um erro inesperado. Tente novamente.',
  },
} as const
