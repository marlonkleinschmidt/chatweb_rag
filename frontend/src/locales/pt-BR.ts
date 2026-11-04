// All user-visible UI strings (pt-BR), including aria-labels. Plain object, no i18n library.
// Texts with values are functions; everything else is a plain string.
export const ptBR = {
  app: {
    title: 'Assistente RAG para documentos',
  },
  theme: {
    toLight: 'Ativar tema claro',
    toDark: 'Ativar tema escuro',
  },
  tabs: {
    label: 'Seções',
    documents: 'Documentos',
    chat: 'Chat',
  },
  health: {
    checking: 'Servidor: verificando conexão...',
    connected: 'Servidor: conectado',
    unavailable: 'Servidor: indisponível',
    retry: 'Tentar novamente',
  },
  // Document states (PRD §5.2).
  status: {
    received: 'Recebido',
    processing: 'Processando',
    ready: 'Pronto',
    failed: 'Falhou',
  },
  documents: {
    heading: 'Documentos',
    listLabel: 'Documentos enviados',
    loading: 'Carregando documentos...',
    empty: 'Nenhum documento enviado ainda. Envie um PDF para começar.',
    sentAt: (date: string) => `Enviado em ${date}`,
    selectLabel: (filename: string) => `Selecionar ${filename}`,
    selectionCount: (count: number, max: number) => `${count} de ${max} selecionados`,
    selectionLimit: (max: number) => `Você pode selecionar até ${max} documentos por pergunta.`,
    removeLabel: (filename: string) => `Remover ${filename}`,
    removed: 'Documento removido.',
    embeddingModelChanged: 'O modelo de indexação mudou. Remova e envie os documentos novamente.',
  },
  upload: {
    label: 'Enviar PDF',
    hint: 'Um arquivo PDF por vez.',
    uploading: 'Enviando...',
    accepted: 'Arquivo enviado. O processamento começou.',
    // Notice required by PRD §7.3, shown next to the upload.
    openaiNotice: 'Os documentos enviados são processados pela OpenAI para gerar respostas.',
    // Client-side validation (same texts as the API codes file_not_pdf and file_empty).
    notPdf: 'Envie um arquivo PDF válido.',
    empty: 'O arquivo está vazio.',
  },
  removeDialog: {
    title: 'Remover documento',
    message: (filename: string) =>
      `O documento "${filename}" e os trechos indexados dele serão removidos. Essa ação não pode ser desfeita.`,
    confirm: 'Remover',
  },
  dialog: {
    cancel: 'Cancelar',
  },
  chat: {
    heading: 'Chat',
    logLabel: 'Conversa',
    empty: 'Nenhuma pergunta ainda. Selecione documentos prontos e faça uma pergunta.',
    noSelection: 'Selecione ao menos um documento pronto para fazer uma pergunta.',
    goToDocuments: 'Ir para Documentos',
    selectedCount: (count: number) =>
      count === 1 ? 'Perguntando sobre 1 documento.' : `Perguntando sobre ${count} documentos.`,
    questionLabel: 'Pergunta',
    questionPlaceholder: 'Pergunte algo sobre os documentos selecionados',
    questionHint: 'Enter envia. Shift+Enter quebra a linha.',
    questionLength: (min: number, max: number) =>
      `Escreva uma pergunta entre ${min} e ${max} caracteres.`,
    send: 'Enviar',
    generating: 'Gerando resposta...',
    stop: 'Parar',
    showSourcesLabel: 'Exibir fontes',
    showSourcesHint: 'Com as fontes desligadas, a resposta aparece aos poucos, sem citações.',
    userLabel: 'Você:',
    assistantLabel: 'Assistente:',
    sources: 'Fontes',
    citeLabel: (index: number) => `Ir para a fonte ${index}`,
  },
  sources: {
    label: (index: number) => `Fonte ${index}`,
    page: (page: number) => `Página ${page}`,
    showExcerpt: 'Mostrar trecho',
    hideExcerpt: 'Ocultar trecho',
    removed: 'Documento removido',
  },
  errors: {
    configMissing: 'A URL do servidor não está configurada (VITE_API_BASE_URL).',
    network: 'Não foi possível conectar ao servidor. Verifique se ele está em execução.',
    unexpected: 'Ocorreu um erro inesperado. Tente novamente.',
    // Fallbacks when the API error envelope is missing; normally the API message is shown.
    provider: 'O serviço de IA não respondeu corretamente. Tente novamente.',
    providerTimeout: 'O serviço de IA demorou demais para responder. Tente novamente.',
  },
} as const
