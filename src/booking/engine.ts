import { Prisma, type Booking } from "@prisma/client";
import { addDays, addMinutes } from "date-fns";
import { fromZonedTime, toZonedTime } from "date-fns-tz";
import { prisma } from "../db";
import { BookingConflictError, NotFoundError } from "./errors";

// Motor de reservas: fonte unica de verdade para disponibilidade e criacao/
// cancelamento/remarcacao. Tanto o fluxo guiado (botoes) quanto o agente de IA
// chamam estas mesmas funcoes, nunca logica duplicada - evita overbooking e
// divergencia de regras entre os dois caminhos.
//
// Simplificacao da Fase 1: uma unica agenda compartilhada por empresa (sem
// multiplos profissionais/recursos). Multi-staff e evolucao futura.

export interface Slot {
  start: Date;
  end: Date;
}

const MIN_LEAD_MINUTES = 30; // nao permite agendar em cima da hora atual

export async function getAvailableSlots(
  businessId: string,
  serviceId: string,
  opts: { fromDate?: Date; daysAhead?: number; limit?: number } = {}
): Promise<Slot[]> {
  const business = await prisma.business.findUniqueOrThrow({ where: { id: businessId } });
  const service = await prisma.service.findFirstOrThrow({
    where: { id: serviceId, businessId, active: true },
  });
  const hoursRows = await prisma.businessHours.findMany({ where: { businessId } });

  const timeZone = business.timezone;
  const daysAhead = opts.daysAhead ?? 7;
  const limit = opts.limit ?? 8;
  const now = opts.fromDate ?? new Date();
  const earliestStart = addMinutes(now, MIN_LEAD_MINUTES);
  const windowEnd = addDays(now, daysAhead + 1);

  const existingBookings = await prisma.booking.findMany({
    where: {
      businessId,
      status: { in: ["PENDING", "CONFIRMED"] },
      startsAt: { lt: windowEnd },
      endsAt: { gt: now },
    },
    select: { startsAt: true, endsAt: true },
  });

  const slots: Slot[] = [];
  const zonedNow = toZonedTime(now, timeZone);

  for (let dayOffset = 0; dayOffset <= daysAhead && slots.length < limit; dayOffset++) {
    const zonedDay = new Date(
      Date.UTC(zonedNow.getUTCFullYear(), zonedNow.getUTCMonth(), zonedNow.getUTCDate() + dayOffset)
    );
    const weekday = zonedDay.getUTCDay();
    const y = zonedDay.getUTCFullYear();
    const m = zonedDay.getUTCMonth();
    const d = zonedDay.getUTCDate();

    const dayRanges = hoursRows.filter((h) => h.weekday === weekday);

    for (const range of dayRanges) {
      const [openH, openM] = range.openTime.split(":").map(Number);
      const [closeH, closeM] = range.closeTime.split(":").map(Number);
      const closeMinutes = closeH * 60 + closeM;

      let cursorMinutes = openH * 60 + openM;

      while (cursorMinutes + service.durationMinutes <= closeMinutes && slots.length < limit) {
        const hh = String(Math.floor(cursorMinutes / 60)).padStart(2, "0");
        const mm = String(cursorMinutes % 60).padStart(2, "0");
        const wallClock = `${y}-${String(m + 1).padStart(2, "0")}-${String(d).padStart(2, "0")}T${hh}:${mm}:00`;
        const start = fromZonedTime(wallClock, timeZone);
        const end = addMinutes(start, service.durationMinutes);

        if (start >= earliestStart) {
          const overlaps = existingBookings.some((b) => start < b.endsAt && end > b.startsAt);
          if (!overlaps) {
            slots.push({ start, end });
          }
        }

        cursorMinutes += service.durationMinutes;
      }
    }
  }

  return slots.slice(0, limit);
}

export async function createBooking(params: {
  businessId: string;
  customerId: string;
  serviceId: string;
  startsAt: Date;
}): Promise<Booking> {
  const service = await prisma.service.findFirstOrThrow({
    where: { id: params.serviceId, businessId: params.businessId, active: true },
  });
  const endsAt = addMinutes(params.startsAt, service.durationMinutes);

  try {
    return await prisma.$transaction(
      async (tx) => {
        const conflict = await tx.booking.findFirst({
          where: {
            businessId: params.businessId,
            status: { in: ["PENDING", "CONFIRMED"] },
            startsAt: { lt: endsAt },
            endsAt: { gt: params.startsAt },
          },
        });
        if (conflict) {
          throw new BookingConflictError();
        }
        return tx.booking.create({
          data: {
            businessId: params.businessId,
            customerId: params.customerId,
            serviceId: params.serviceId,
            startsAt: params.startsAt,
            endsAt,
            status: "CONFIRMED",
          },
        });
      },
      { isolationLevel: Prisma.TransactionIsolationLevel.Serializable }
    );
  } catch (err) {
    // P2034 = falha de serializacao (conflito de escrita concorrente)
    if (err instanceof Prisma.PrismaClientKnownRequestError && err.code === "P2034") {
      throw new BookingConflictError();
    }
    throw err;
  }
}

export async function cancelBooking(businessId: string, bookingId: string): Promise<Booking> {
  const booking = await prisma.booking.findFirst({ where: { id: bookingId, businessId } });
  if (!booking) {
    throw new NotFoundError("Agendamento nao encontrado.");
  }
  if (booking.status === "CANCELLED") {
    return booking;
  }
  return prisma.booking.update({ where: { id: bookingId }, data: { status: "CANCELLED" } });
}

export async function rescheduleBooking(
  businessId: string,
  bookingId: string,
  newStartsAt: Date
): Promise<Booking> {
  const existing = await prisma.booking.findFirst({ where: { id: bookingId, businessId } });
  if (!existing) {
    throw new NotFoundError("Agendamento nao encontrado.");
  }
  const service = await prisma.service.findUniqueOrThrow({ where: { id: existing.serviceId } });
  const newEndsAt = addMinutes(newStartsAt, service.durationMinutes);

  try {
    return await prisma.$transaction(
      async (tx) => {
        const conflict = await tx.booking.findFirst({
          where: {
            businessId,
            id: { not: bookingId },
            status: { in: ["PENDING", "CONFIRMED"] },
            startsAt: { lt: newEndsAt },
            endsAt: { gt: newStartsAt },
          },
        });
        if (conflict) {
          throw new BookingConflictError();
        }
        return tx.booking.update({
          where: { id: bookingId },
          data: { startsAt: newStartsAt, endsAt: newEndsAt, status: "CONFIRMED" },
        });
      },
      { isolationLevel: Prisma.TransactionIsolationLevel.Serializable }
    );
  } catch (err) {
    if (err instanceof Prisma.PrismaClientKnownRequestError && err.code === "P2034") {
      throw new BookingConflictError();
    }
    throw err;
  }
}

export async function listUpcomingBookingsForCustomer(businessId: string, customerId: string) {
  return prisma.booking.findMany({
    where: {
      businessId,
      customerId,
      status: { in: ["PENDING", "CONFIRMED"] },
      startsAt: { gte: new Date() },
    },
    include: { service: true },
    orderBy: { startsAt: "asc" },
  });
}
