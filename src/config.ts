import "dotenv/config";

function required(name: string): string {
  const value = process.env[name];
  if (!value) {
    throw new Error(`Variavel de ambiente obrigatoria ausente: ${name}`);
  }
  return value;
}

export const config = {
  port: Number(process.env.PORT ?? 3000),
  databaseUrl: required("DATABASE_URL"),
  masterEncryptionKey: required("MASTER_ENCRYPTION_KEY"),
  jwtSecret: required("JWT_SECRET"),
  jwtExpiresInSeconds: 60 * 60 * 24 * 7, // 7 dias
  // Origens do dashboard (Next.js, ver web/) autorizadas a chamar a API a
  // partir do navegador. Lista separada por virgula; vazio = nenhuma origem
  // liberada (a API continua acessivel via server-to-server sem CORS).
  corsOrigins: (process.env.CORS_ORIGINS ?? "")
    .split(",")
    .map((o) => o.trim())
    .filter(Boolean),
  whatsapp: {
    appSecret: process.env.WHATSAPP_APP_SECRET ?? "",
    webhookVerifyToken: process.env.WHATSAPP_WEBHOOK_VERIFY_TOKEN ?? "",
    apiVersion: process.env.WHATSAPP_API_VERSION ?? "v21.0",
    // Templates pre-aprovados no Meta Business Manager, usados por automacoes
    // proativas (Fase 9) - mensagens fora da janela de 24h de uma conversa
    // iniciada pelo cliente exigem um template aprovado, entao o texto NAO e
    // livre por empresa (ver Automation no schema): so o gatilho/offset sao
    // configuraveis, o template em si e global por tipo de automacao.
    reminderTemplateName: process.env.WHATSAPP_REMINDER_TEMPLATE_NAME ?? "appointment_reminder",
    reminderTemplateLang: process.env.WHATSAPP_REMINDER_TEMPLATE_LANG ?? "pt_BR",
    followupTemplateName: process.env.WHATSAPP_FOLLOWUP_TEMPLATE_NAME ?? "appointment_followup",
    followupTemplateLang: process.env.WHATSAPP_FOLLOWUP_TEMPLATE_LANG ?? "pt_BR",
  },
  anthropic: {
    apiKey: process.env.ANTHROPIC_API_KEY ?? "",
    model: process.env.CLAUDE_MODEL ?? "claude-sonnet-4-5-20250929",
  },
  automations: {
    checkIntervalMs: Number(process.env.AUTOMATION_CHECK_INTERVAL_MS ?? 300_000),
  },
};
