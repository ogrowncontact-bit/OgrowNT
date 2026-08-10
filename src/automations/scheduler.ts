import type { Automation, Booking, Business, Customer, Service, WhatsAppAccount } from "@prisma/client";
import { addMinutes } from "date-fns";
import { createWhatsAppAdapter } from "../channels/whatsapp";
import { config } from "../config";
import { formatSlotLong } from "../conversation/format";
import { prisma } from "../db";

// Varre as automacoes ativas de todas as empresas (ver Automation no schema,
// Fase 9) e dispara lembretes/follow-ups via template do WhatsApp.
// AutomationLog evita reenvio duplicado do mesmo (automation, booking).
//
// Substitui o antigo src/reminders/scheduler.ts (offsets hardcoded em
// config.reminders) - agora cada empresa liga/desliga e ajusta o offset de
// cada automacao (ver src/routes/automations.routes.ts), mas o TEXTO
// continua vindo de um template pre-aprovado global por tipo, porque o
// WhatsApp exige isso fora da janela de 24h de conversa (nao da pra
// personalizar o texto por empresa sem um template aprovado por empresa,
// o que fica fora do escopo desta versao).

type BookingDue = Booking & {
  service: Service;
  customer: Customer;
  business: Business & { whatsAppAccount: WhatsAppAccount | null };
};

async function sendAndLog(kind: "reminder" | "followup", automation: Automation, booking: BookingDue): Promise<void> {
  const account = booking.business.whatsAppAccount;
  if (!account) return; // empresa ainda nao conectou um numero de WhatsApp

  const channel = createWhatsAppAdapter(account);
  const customerLanguage =
    booking.customer.preferredLanguage !== "auto" ? booking.customer.preferredLanguage : booking.business.defaultLanguage;
  const label = formatSlotLong(booking.startsAt, booking.business.timezone, customerLanguage);
  const templateName = kind === "reminder" ? config.whatsapp.reminderTemplateName : config.whatsapp.followupTemplateName;
  const templateLang = kind === "reminder" ? config.whatsapp.reminderTemplateLang : config.whatsapp.followupTemplateLang;

  try {
    await channel.sendTemplate(booking.customer.phoneNumber, templateName, templateLang, [
      {
        type: "body",
        parameters: [
          { type: "text", text: booking.service.name },
          { type: "text", text: label },
        ],
      },
    ]);
    await prisma.automationLog.create({ data: { automationId: automation.id, bookingId: booking.id } });
  } catch (err) {
    console.error(`[automations] falha ao enviar ${kind} do agendamento ${booking.id}:`, err);
  }
}

async function runReminderAutomation(automation: Automation, now: Date, bufferMinutes: number): Promise<void> {
  const windowStart = addMinutes(now, automation.offsetMinutes);
  const windowEnd = addMinutes(now, automation.offsetMinutes + bufferMinutes);

  const dueBookings = await prisma.booking.findMany({
    where: {
      businessId: automation.businessId,
      status: "CONFIRMED",
      startsAt: { gte: windowStart, lt: windowEnd },
      automationLogs: { none: { automationId: automation.id } },
    },
    include: { service: true, customer: true, business: { include: { whatsAppAccount: true } } },
  });

  for (const booking of dueBookings) {
    await sendAndLog("reminder", automation, booking);
  }
}

async function runFollowupAutomation(automation: Automation, now: Date, bufferMinutes: number): Promise<void> {
  const windowStart = addMinutes(now, -automation.offsetMinutes - bufferMinutes);
  const windowEnd = addMinutes(now, -automation.offsetMinutes);

  const dueBookings = await prisma.booking.findMany({
    where: {
      businessId: automation.businessId,
      status: { in: ["CONFIRMED", "COMPLETED"] },
      endsAt: { gte: windowStart, lt: windowEnd },
      automationLogs: { none: { automationId: automation.id } },
    },
    include: { service: true, customer: true, business: { include: { whatsAppAccount: true } } },
  });

  for (const booking of dueBookings) {
    await sendAndLog("followup", automation, booking);
  }
}

export async function checkAndRunAutomations(): Promise<void> {
  const now = new Date();
  const bufferMinutes = Math.ceil(config.automations.checkIntervalMs / 60_000) + 1;

  const automations = await prisma.automation.findMany({ where: { active: true } });

  for (const automation of automations) {
    if (automation.trigger === "BOOKING_REMINDER") {
      await runReminderAutomation(automation, now, bufferMinutes);
    } else {
      await runFollowupAutomation(automation, now, bufferMinutes);
    }
  }
}

export function startAutomationScheduler(): NodeJS.Timeout {
  checkAndRunAutomations().catch((err) => console.error("[automations] erro no ciclo inicial:", err));
  return setInterval(() => {
    checkAndRunAutomations().catch((err) => console.error("[automations] erro no ciclo:", err));
  }, config.automations.checkIntervalMs);
}
