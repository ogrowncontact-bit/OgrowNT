import { addMinutes } from "date-fns";
import { formatSlotLong } from "../conversation/format";
import { config } from "../config";
import { decryptSecret } from "../crypto";
import { prisma } from "../db";
import * as wa from "../whatsapp/client";

// Varre agendamentos confirmados e dispara lembretes (WhatsApp template
// message) nas janelas configuradas (padrao: 24h e 2h antes). ReminderLog
// evita reenvio duplicado do mesmo lembrete.

async function sendDueReminders(offsetMinutes: number, now: Date, bufferMinutes: number): Promise<void> {
  const windowStart = addMinutes(now, offsetMinutes);
  const windowEnd = addMinutes(now, offsetMinutes + bufferMinutes);

  const dueBookings = await prisma.booking.findMany({
    where: {
      status: "CONFIRMED",
      startsAt: { gte: windowStart, lt: windowEnd },
      reminderLogs: { none: { offsetMinutes } },
    },
    include: {
      service: true,
      customer: true,
      business: { include: { whatsAppAccount: true } },
    },
  });

  for (const booking of dueBookings) {
    const account = booking.business.whatsAppAccount;
    if (!account) continue; // empresa ainda nao conectou um numero de WhatsApp

    const waCtx = {
      phoneNumberId: account.phoneNumberId,
      accessToken: decryptSecret(account.encryptedAccessToken),
    };
    const customerLanguage =
      booking.customer.preferredLanguage !== "auto" ? booking.customer.preferredLanguage : booking.business.defaultLanguage;
    const label = formatSlotLong(booking.startsAt, booking.business.timezone, customerLanguage);

    // O NOME/IDIOMA do template em si (aprovado no Meta Business Manager) e
    // uma configuracao global por enquanto (config.whatsapp.reminderTemplate*)
    // - selecionar automaticamente um template por idioma do cliente exigiria
    // a empresa cadastrar um template aprovado por idioma, o que fica para
    // uma proxima fase. O texto interpolado (a data/hora) ja respeita o
    // idioma do cliente.
    try {
      await wa.sendTemplateMessage(
        waCtx,
        booking.customer.phoneNumber,
        config.whatsapp.reminderTemplateName,
        config.whatsapp.reminderTemplateLang,
        [
          {
            type: "body",
            parameters: [
              { type: "text", text: booking.service.name },
              { type: "text", text: label },
            ],
          },
        ]
      );
      await prisma.reminderLog.create({ data: { bookingId: booking.id, offsetMinutes } });
    } catch (err) {
      console.error(`[reminders] falha ao enviar lembrete do agendamento ${booking.id}:`, err);
    }
  }
}

export async function checkAndSendReminders(): Promise<void> {
  const now = new Date();
  const bufferMinutes = Math.ceil(config.reminders.checkIntervalMs / 60_000) + 1;

  for (const offsetMinutes of config.reminders.offsetsMinutes) {
    await sendDueReminders(offsetMinutes, now, bufferMinutes);
  }
}

export function startReminderScheduler(): NodeJS.Timeout {
  checkAndSendReminders().catch((err) => console.error("[reminders] erro no ciclo inicial:", err));
  return setInterval(() => {
    checkAndSendReminders().catch((err) => console.error("[reminders] erro no ciclo:", err));
  }, config.reminders.checkIntervalMs);
}
