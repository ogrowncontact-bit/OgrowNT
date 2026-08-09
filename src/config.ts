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
  whatsapp: {
    appSecret: process.env.WHATSAPP_APP_SECRET ?? "",
    webhookVerifyToken: process.env.WHATSAPP_WEBHOOK_VERIFY_TOKEN ?? "",
    apiVersion: process.env.WHATSAPP_API_VERSION ?? "v21.0",
    // Template pre-aprovado no Meta Business Manager, usado para lembretes
    // proativos (mensagens fora da janela de 24h precisam de template).
    reminderTemplateName: process.env.WHATSAPP_REMINDER_TEMPLATE_NAME ?? "appointment_reminder",
    reminderTemplateLang: process.env.WHATSAPP_REMINDER_TEMPLATE_LANG ?? "pt_BR",
  },
  anthropic: {
    apiKey: process.env.ANTHROPIC_API_KEY ?? "",
    model: process.env.CLAUDE_MODEL ?? "claude-sonnet-4-5-20250929",
  },
  reminders: {
    checkIntervalMs: Number(process.env.REMINDER_CHECK_INTERVAL_MS ?? 300_000),
    // Janelas de lembrete antes do horario agendado
    offsetsMinutes: [24 * 60, 2 * 60],
  },
};
